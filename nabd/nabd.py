import asyncio, json, datetime, collections, sys, getopt, os
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from pydoc import locate
from .leds import Leds
from django.conf import settings
from django.apps import apps
from nabcommon.nabservice import NabService

import time
import traceback

class Nabd:
  SLEEP_EAR_POSITION = 8
  INIT_EAR_POSITION = 0
  EAR_MOVEMENT_TIMEOUT = 0.5

  def __init__(self, nabio):
    if not settings.configured:
      conf = {
        'INSTALLED_APPS': [
          type(self).__name__.lower()
        ],
        'USE_TZ': True,
        'DATABASES': {
          'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'pynab',
            'USER': 'pynab',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
          }
        }
      }
      settings.configure(**conf)
      apps.populate(settings.INSTALLED_APPS)
    self.nabio = nabio
    self.idle_cv = asyncio.Condition()
    self.idle_queue = collections.deque()
    # Current position of ears in idle mode
    self.ears = {'left': Nabd.INIT_EAR_POSITION, 'right': Nabd.INIT_EAR_POSITION}
    self.info = {}                      # Info persists across service connections.
    self.state = 'idle'                 # 'asleep'/'idle'/'interactive'/'playing'/'recording'
    self.service_writers = {}           # Dictionary of writers, i.e. connected services
                                        # For each writer, value is the list of registered events
    self.interactive_service_writer = None
    self.interactive_service_events = [] # Events registered in interactive mode
    self.running = True
    self.loop = None
    self._ears_moved_task = None
    Nabd.leds_boot(self.nabio, 2)
    if self.nabio.has_sound_input():
      from .asr import ASR
      self.asr = ASR('fr_FR')
      Nabd.leds_boot(self.nabio, 3)
      from .nlu import NLU
      self.nlu = NLU('fr_FR')
      Nabd.leds_boot(self.nabio, 4)

  async def idle_setup(self):
    self.nabio.set_leds(None, None, None, None, None)
    self.nabio.pulse(Leds.LED_BOTTOM, (255, 0, 255))
    await self.nabio.move_ears(self.ears['left'], self.ears['right'])

  async def sleep_setup(self):
    self.nabio.set_leds(None, None, None, None, None)
    await self.nabio.move_ears(Nabd.SLEEP_EAR_POSITION, Nabd.SLEEP_EAR_POSITION)

  async def idle_worker_loop(self):
    """
    Idle worker loop is responsible for playing enqueued messages and displaying
    info items.
    """
    try:
      async with self.idle_cv:
        while self.running:
          # Check if we have something to do.
          if self.state == 'idle' and len(self.idle_queue) > 0:
            item = self.idle_queue.popleft()
            await self.process_idle_item(item)
          else:
            if self.state == 'idle' and len(self.info.items()) > 0:
              for key, value in self.info.items():
                await self.nabio.play_info(self.idle_cv, value['tempo'], value['colors'])
            else:
              await self.idle_cv.wait()
    except KeyboardInterrupt:
      pass
    except Exception:
      print(traceback.format_exc())
    finally:
      if self.running:
        self.loop.stop()

  async def stop_idle_worker(self):
    async with self.idle_cv:
      self.running = False  # signal to exit
      self.idle_cv.notify()

  async def exit_interactive(self):
    """
    Exit interactive mode.
    Restarts idle loop worker.
    """
    # interactive -> playing or interactive -> idle depending on the command queue
    self.interactive_service_writer = None
    await self.transition_to_idle()

  async def process_idle_item(self, item):
    """
    Process an item from the idle queue.
    The lock is acquired when this function is called.
    """
    while True:
      if 'expiration_date' in item[0] and item[0]['expiration_date'] < datetime.now():
        self.write_response_packet(item[0], {'status':'expired'}, item[1])
        if len(self.idle_queue) == 0:
          await self.set_state('idle')
          break
        else:
          item = self.idle_queue.popleft()
      else:
        if item[0]['type'] == 'command':
          await self.set_state('playing')
          await self.perform_command(item[0])
          self.write_response_packet(item[0], {'status':'ok'}, item[1])
          if len(self.idle_queue) == 0:
            await self.set_state('idle')
            break
          else:
            item = self.idle_queue.popleft()
        elif item[0]['type'] == 'message':
          await self.set_state('playing')
          await self.perform_message(item[0])
          self.write_response_packet(item[0], {'status':'ok'}, item[1])
          if len(self.idle_queue) == 0:
            await self.set_state('idle')
            break
          else:
            item = self.idle_queue.popleft()
        elif item[0]['type'] == 'sleep':
          # Check idle_queue doesn't only include 'sleep' items.
          has_non_sleep = False
          for other_item in self.idle_queue:
            if other_item[0]['type'] != 'sleep':
              has_non_sleep = True
              break
          if has_non_sleep:
            self.idle_queue.append(item)
          else:
            self.write_response_packet(item[0], {'status':'ok'}, item[1])
            await self.set_state('asleep')
            break
        elif item[0]['type'] == 'mode' and item[0]['mode'] == 'interactive':
          self.write_response_packet(item[0], {'status':'ok'}, item[1])
          await self.set_state('interactive')
          self.interactive_service_writer = item[1]
          if 'events' in item[0]:
            self.interactive_service_events = item[0]['events']
          else:
            self.interactive_service_events = ['ears', 'button']
          break
        else:
          raise RuntimeError('Unexpected packet {packet}'.format(packet=item[0]))

  async def transition_to_idle(self):
    """
    Transition to idle from asleep.
    """
    async with self.idle_cv:
      if len(self.idle_queue) == 0:
        await self.set_state('idle')
      else:
        item = self.idle_queue.popleft()
        await self.process_idle_item(item)

  async def set_state(self, new_state):
    if new_state != self.state:
      if new_state == 'idle':
        await self.idle_setup()
      if new_state == 'asleep':
        await self.sleep_setup()
      self.state = new_state
      self.broadcast_state()

  async def process_info_packet(self, packet, writer):
    """ Process an info packet """
    if 'info_id' in packet:
      if 'animation' in packet:
        if not 'tempo' in packet['animation'] or not 'colors' in packet['animation']:
          self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required tempo & colors slots in animation'}, writer)
        else:
          self.info[packet['info_id']] = packet['animation']
      else:
        del self.info[packet['info_id']]
      self.write_response_packet(packet, {'status':'ok'}, writer)
      # Signal idle loop to make sure we display updated info
      async with self.idle_cv:
        self.idle_cv.notify()
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required info_id slot'}, writer)

  async def process_ears_packet(self, packet, writer):
    """ Process an ears packet """
    if 'left' in packet:
      self.ears['left'] = packet['left']
    if 'right' in packet:
      self.ears['right'] = packet['right']
    if self.state == 'idle':
      await self.nabio.move_ears(self.ears['left'], self.ears['right'])
    self.write_response_packet(packet, {'status':'ok'}, writer)

  async def process_command_packet(self, packet, writer):
    """ Process a command packet """
    if 'sequence' in packet:
      if self.interactive_service_writer == writer:
        # interactive => play command immediately
        await self.perform_command(packet)
        self.write_response_packet(packet, {'status':'ok'}, writer)
      else:
        async with self.idle_cv:
          self.idle_queue.append((packet, writer))
          self.idle_cv.notify()
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required sequence slot'}, writer)

  async def process_message_packet(self, packet, writer):
    """ Process a message packet """
    if 'body' in packet:
      if self.interactive_service_writer == writer:
        # interactive => play command immediately
        await self.perform_message(packet)
        self.write_response_packet(packet, {'status':'ok'}, writer)
      else:
        async with self.idle_cv:
          self.idle_queue.append((packet, writer))
          self.idle_cv.notify()
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required body slot'}, writer)

  async def process_cancel_packet(self, packet, writer):
    """ Process a cancel packet """
    self.write_response_packet(packet, {'status':'error','class':'Unimplemented','message':'unimplemented'}, writer)

  async def process_wakeup_packet(self, packet, writer):
    """ Process a wakeup packet """
    self.write_response_packet(packet, {'status':'ok'}, writer)
    if self.state == 'asleep':
      await self.transition_to_idle()

  async def process_sleep_packet(self, packet, writer):
    """ Process a sleep packet """
    if self.state == 'asleep':
      self.write_response_packet(packet, {'status':'ok'}, writer)
    else:
      async with self.idle_cv:
        self.idle_queue.append((packet, writer))
        self.idle_cv.notify()

  async def process_mode_packet(self, packet, writer):
    """ Process a mode packet """
    if 'mode' in packet and packet['mode'] == 'interactive':
      async with self.idle_cv:
        self.idle_queue.append((packet, writer))
        self.idle_cv.notify()
    elif 'mode' in packet and packet['mode'] == 'idle':
      if 'events' in packet:
        self.service_writers[writer] = packet['events']
      else:
        self.service_writers[writer] = ['asr']
      if writer == self.interactive_service_writer:
        # exit interactive mode.
        await self.exit_interactive()
      self.write_response_packet(packet, {'status':'ok'}, writer)
    else:
      self.write_response_packet(packet, {'status':'error','class':'UnknownPacket','message':'Unknown or malformed mode packet'}, writer)

  async def process_packet(self, packet, writer):
    """ Process a packet from a service """
    if 'type' in packet:
      processors = {
        'info': self.process_info_packet,
        'ears': self.process_ears_packet,
        'command': self.process_command_packet,
        'message': self.process_message_packet,
        'cancel': self.process_cancel_packet,
        'wakeup': self.process_wakeup_packet,
        'sleep': self.process_sleep_packet,
        'mode': self.process_mode_packet,
      }
      if packet['type'] in processors:
        await processors[packet['type']](packet, writer)
      else:
        self.write_response_packet(packet, {'status':'error','class':'UnknownPacket','message':'Unknown type ' + str(packet['type'])}, writer)
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing type slot'}, writer)

  def write_packet(self, response, writer):
    writer.write((json.dumps(response) + '\r\n').encode('utf8'))

  def broadcast_event(self, event_type, response):
    for sw, events in self.service_writers.items():
      if event_type in events:
        self.write_packet(response, sw)

  def write_response_packet(self, original_packet, template, writer):
    response_packet = template
    if 'request_id' in original_packet:
      response_packet['request_id'] = original_packet['request_id']
    response_packet['type'] = 'response'
    self.write_packet(response_packet, writer)

  def broadcast_state(self):
    for sw in self.service_writers:
      self.write_state_packet(sw)

  def write_state_packet(self, writer):
    self.write_packet({'type':'state','state':self.state}, writer)

  # Handle service through TCP/IP protocol
  async def service_loop(self, reader, writer):
    self.write_state_packet(writer)
    self.service_writers[writer] = ['asr']
    try:
      while not reader.at_eof():
        line = await reader.readline()
        if line != b'' and line != b'\r\n':
          try:
            packet = json.loads(line.decode('utf8'))
            await self.process_packet(packet, writer)
          except UnicodeDecodeError as e:
            self.write_packet({'type':'response','status':'error','class':'UnicodeDecodeError','message':str(e)}, writer)
          except json.decoder.JSONDecodeError as e:
            self.write_packet({'type':'response','status':'error','class':'JSONDecodeError','message':str(e)}, writer)
      writer.close()
      if sys.version_info >= (3,7):
        await writer.wait_closed()
    except ConnectionResetError:
      pass
    except Exception:
      print(traceback.format_exc())
    finally:
      if self.interactive_service_writer == writer:
        await self.exit_interactive()
      del self.service_writers[writer]

  async def perform_command(self, packet):
    await self.nabio.play_sequence(packet['sequence'])

  async def perform_message(self, packet):
    signature = {}
    if 'signature' in packet:
      signature = packet['signature']
    await self.nabio.play_message(signature, packet['body'])

  def button_callback(self, button_event, event_time):
    if button_event == 'hold' and self.state == 'idle':
      asyncio.ensure_future(self.start_asr())
    if button_event == 'up' and self.state == 'recording':
      asyncio.ensure_future(self.stop_asr())
    elif button_event == 'triple_click':
      asyncio.ensure_future(self._shutdown())
    else:
      self.broadcast_event('button', {'type':'button_event', 'event': button_event, 'time': event_time})

  async def start_asr(self):
    await self.set_state('recording')
    await self.nabio.start_acquisition(self.asr.decode_chunk)

  async def stop_asr(self):
    await self.nabio.end_acquisition()
    now = time.time()
    decoded_str = await self.asr.get_decoded_string(True)
    # ASR model needs to be improved, log outcome.
    print("asr => %s" % decoded_str)
    response = await self.nlu.interpret(decoded_str)
#   print("nlu => %s" % str(response))
    await self.set_state('idle')
    if response == None:
      # Did not understand
      await self.nabio.asr_failed()
    else:
      self.broadcast_event('asr', {'type':'asr_event', 'nlu': response, 'time': now})

  async def _shutdown(self):
    await self.sleep_setup()
    os.system('/sbin/halt')

  def ears_callback(self, ear):
    if self.interactive_service_writer:
      # Cancel any previously registered timer
      if self._ears_moved_task:
        self._ears_moved_task.cancel()
      # Tell services
      if ear == Ears.LEFT_EAR:
        ear_str = 'left'
      else:
        ear_str = 'right'
      self.write_packet({'type':'ear_event', 'ear':ear_str})
    else:
      # Wait a little bit for user to continue moving the ears
      # Then we'll run a detection and tell services if we're not sleeping.
      if self._ears_moved_task:
        self._ears_moved_task.cancel()
      self._ears_moved_task = asyncio.ensure_future(self._ears_moved())

  async def _ears_moved(self):
    await asyncio.sleep(Nabd.EAR_MOVEMENT_TIMEOUT)
    if self.interactive_service_writer == None:
      (left, right) = await self.nabio.detect_ears_positions()
      self.ears['left'] = left
      self.ears['right'] = right
      if self.state != 'asleep':
        self.broadcast_event('ears', {'type':'ears_event', 'left': left, 'right': right})

  def run(self):
    self.loop = asyncio.get_event_loop()
    self.nabio.bind_button_event(self.loop, self.button_callback)
    self.nabio.bind_ears_event(self.loop, self.ears_callback)
    setup_task = self.loop.create_task(self.idle_setup())
    idle_task = self.loop.create_task(self.idle_worker_loop())
    server_task = self.loop.create_task(asyncio.start_server(self.service_loop, 'localhost', NabService.PORT_NUMBER))
    try:
      self.loop.run_forever()
      for t in [setup_task, idle_task, server_task]:
        if t.done():
          t_ex = t.exception()
          if t_ex:
            raise t_ex
    except KeyboardInterrupt:
      pass
    except Exception:
      print(traceback.format_exc())
    finally:
      self.loop.run_until_complete(self.stop_idle_worker())
      for writer in self.service_writers.copy():
        writer.close()
        if sys.version_info >= (3,7):
          self.loop.run_until_complete(writer.wait_closed())
      if sys.version_info >= (3,7):
        tasks = asyncio.all_tasks(self.loop)
      else:
        tasks = asyncio.Task.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      server = server_task.result()
      server.close()
      self.loop.close()

  def stop(self):
    if not self.loop.is_closed():
      self.loop.call_soon_threadsafe(lambda : self.loop.stop())

  @staticmethod
  def leds_boot(nabio, step):
    """
    Animation to indicate boot progress.
    Useful as loading ASR/NLU model takes some time.
    """
    if step == 1:
      nabio.set_leds((0, 255, 0), (255, 128, 0), (255, 128, 0), (255, 128, 0), (255, 128, 0))
    if step == 2:
      nabio.set_leds((0, 255, 0), (0, 255, 0), (255, 128, 0), (255, 128, 0), (255, 128, 0))
    if step == 3:
      nabio.set_leds((0, 255, 0), (0, 255, 0), (0, 255, 0), (255, 128, 0), (255, 128, 0))
    if step == 4:
      nabio.set_leds((0, 255, 0), (0, 255, 0), (0, 255, 0), (0, 255, 0), (255, 128, 0))

  @staticmethod
  def main(argv):
    pidfilepath = "/var/run/nabd.pid"
    usage = 'nabd [options]\n' \
     + ' -h                   display this message\n' \
     + ' --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n'.format(pidfilepath=pidfilepath)
    try:
      opts, args = getopt.getopt(argv,"h",["pidfile=","nabio="])
    except getopt.GetoptError:
      print(usage)
      exit(2)
    for opt, arg in opts:
      if opt == '-h':
        print(usage)
        exit(0)
      elif opt == '--pidfile':
        pidfilepath = arg
    pidfile = PIDLockFile(pidfilepath, timeout=-1)
    try:
      with pidfile:
        from .nabio_hw import NabIOHW
        nabio = NabIOHW()
        Nabd.leds_boot(nabio, 1)
        nabd = Nabd(nabio)
        nabd.run()
    except AlreadyLocked:
      print('nabd already running? (pid={pid})'.format(pid=pidfile.read_pid()))
      exit(1)
    except LockFailed:
      print('Cannot write pid file to {pidfilepath}, please fix permissions'.format(pidfilepath=pidfilepath))
      exit(1)

if __name__ == '__main__':
  Nabd.main(sys.argv[1:])
