import asyncio, json, datetime, collections, sys, getopt
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from pydoc import locate
from .nabio_virtual import NabIOVirtual

class Nabd:
  PORT_NUMBER = 10543
  INFO_TIMEOUT = 15.0
  SLEEP_EAR_POSITION = 8
  INIT_EAR_POSITION = 0

  def __init__(self, nabio):
    self.nabio = nabio
    self.idle_cv = asyncio.Condition()
    self.idle_queue = collections.deque()
    # Current position of ears in idle mode
    self.ears = {'left': Nabd.INIT_EAR_POSITION, 'right': Nabd.INIT_EAR_POSITION}
    self.info = {}                      # Info persists across service connections.
    self.state = 'idle'                 # 'asleep'/'idle'/'interative'/'playing'
    self.service_writers = []           # List of writers, i.e. connected services.
    self.interactive_service_writer = None
    self.running = True
    self.loop = None

  def idle_setup(self):
    self.nabio.set_ears(self.ears['left'], self.ears['right'])
    self.nabio.set_leds(None, None, None, None, None)

  def sleep_setup(self):
    self.nabio.set_ears(Nabd.SLEEP_EAR_POSITION, Nabd.SLEEP_EAR_POSITION)
    self.nabio.set_leds(None, None, None, None, None)

  async def idle_worker_loop(self):
    try:
      async with self.idle_cv:
        while self.running:
          # Check if we have something to do.
          if self.state == 'idle' and len(self.idle_queue) > 0:
            item = self.idle_queue.popleft()
            await self.process_idle_item(item)
          else:
            try:
              if self.state == 'idle':
                for key, value in self.info.items():
                  await self.nabio.play_info(value['tempo'], value['colors'])
                await asyncio.wait_for(self.idle_cv.wait(), Nabd.INFO_TIMEOUT)
              else:
                await self.idle_cv.wait()
            except asyncio.TimeoutError:
              pass
    except KeyboardInterrupt:
      pass
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
          self.set_state('idle')
          break
        else:
          item = self.idle_queue.popleft()
      else:
        if item[0]['type'] == 'command':
          self.set_state('playing')
          await self.perform_command(item[0])
          self.write_response_packet(item[0], {'status':'ok'}, item[1])
          if len(self.idle_queue) == 0:
            self.set_state('idle')
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
            self.set_state('asleep')
            self.sleep_setup()
            break
        elif item[0]['type'] == 'mode' and item[0]['mode'] == 'interactive':
          self.write_response_packet(item[0], {'status':'ok'}, item[1])
          self.set_state('interactive')
          self.interactive_service_writer = item[1]
          break
        else:
          raise RuntimeError(f'Unexpected packet {item[0]}')

  async def transition_to_idle(self):
    """
    Transition to idle from asleep.
    """
    async with self.idle_cv:
      if len(self.idle_queue) == 0:
        self.set_state('idle')
      else:
        item = self.idle_queue.popleft()
        self.process_idle_item(item)

  def set_state(self, new_state):
    if new_state != self.state:
      if new_state == 'idle':
        self.idle_setup()
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
      async with self.idle_cv:
        self.idle_cv.notify()
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required info_id slot'}, writer)

  async def process_ears_packet(self, packet, writer):
    """ Process an ears packet """
    if 'left' in packet:
      ears['left'] = packet['left']
    if 'right' in packet:
      ears['right'] = packet['right']
    self.write_response_packet(packet, {'status':'ok'}, writer)
    if self.state == "idle":
      self.nabio.set_ears(ears['left'], ears['right'])

  async def process_command_packet(self, packet, writer):
    """ Process a command packet """
    if 'sequence' in packet:
      if self.interactive_service_writer == writer:
        # interactive => play command immediately
        await self.perform_command(packet)
        self.write_response_packet(item[0], {'status':'ok'}, item[1])
      else:
        async with self.idle_cv:
          self.idle_queue.append((packet, writer))
          self.idle_cv.notify()
    else:
      self.write_response_packet(packet, {'status':'error','class':'MalformedPacket','message':'Missing required sequence slot'}, writer)

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
    self.write_response_packet(packet, {'status':'error','class':'Unimplemented','message':'unimplemented'}, writer)

  async def process_packet(self, packet, writer):
    """ Process a packet from a service """
    if 'type' in packet:
      processors = {
        'info': self.process_info_packet,
        'ears': self.process_ears_packet,
        'command': self.process_command_packet,
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
    self.service_writers.append(writer)
    try:
      while not reader.at_eof():
        line = await reader.readline()
        if line != b'' and line != b'\r\n':
          try:
            packet = json.loads(line)
            await self.process_packet(packet, writer)
          except UnicodeDecodeError as e:
            self.write_packet({'type':'response','status':'error','class':'UnicodeDecodeError','message':str(e)}, writer)
          except json.decoder.JSONDecodeError as e:
            self.write_packet({'type':'response','status':'error','class':'JSONDecodeError','message':str(e)}, writer)
      writer.close()
      await writer.wait_closed()
    except ConnectionResetError:
      pass
    finally:
      if self.interactive_service_writer == writer:
        self.exit_interactive()
      self.service_writers.remove(writer)

  async def perform_command(self, packet):
    await self.nabio.play_sequence(packet['sequence'])

  def button_callback(self, button_event):
    pass

  def ears_callback(self, left_ear, right_ear):
    pass

  def run(self):
    self.idle_setup()
    self.loop = asyncio.get_event_loop()
    self.nabio.bind_button_event(self.loop, self.button_callback)
    self.nabio.bind_ears_event(self.loop, self.ears_callback)
    idle_task = self.loop.create_task(self.idle_worker_loop())
    server_task = self.loop.create_task(asyncio.start_server(self.service_loop, 'localhost', Nabd.PORT_NUMBER))
    try:
      self.loop.run_forever()
      if idle_task.done():
        idle_ex = idle_task.exception()
        if idle_ex:
          raise idle_ex
    except KeyboardInterrupt:
      pass
    finally:
      self.loop.run_until_complete(self.stop_idle_worker())
      tasks = asyncio.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      server = server_task.result()
      server.close()
      for writer in self.service_writers:
        writer.close()
        self.loop.run_until_complete(writer.wait_closed())
      self.loop.close()

  def stop(self):
    if not self.loop.is_closed():
      self.loop.call_soon_threadsafe(lambda : self.loop.stop())

  @staticmethod
  def main(argv):
    pidfilepath = "/var/run/nabd.pid"
    nabiocls = NabIOVirtual
    usage = f'nabd [options]\n' \
     + ' -h                   display this message\n' \
     + f' --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n' \
     + f' --nabio=nabio_class  define nabio implementation (default = {nabiocls.__module__}.{nabiocls.__name__})'
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
      elif opt == '--nabio':
        nabiocls = locate(arg)
    pidfile = PIDLockFile(pidfilepath, timeout=-1)
    try:
      with pidfile:
        nabio = nabiocls()
        nabd = Nabd(nabio)
        nabd.run()
    except AlreadyLocked:
      print(f'nabd already running? (pid={pidfile.read_pid()})')
      exit(1)
    except LockFailed:
      print(f'Cannot write pid file to {pidfilepath}, please fix permissions')
      exit(1)

if __name__ == '__main__':
  Nabd.main(sys.argv[1:])
