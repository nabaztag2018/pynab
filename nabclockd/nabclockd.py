import sys, asyncio, json, datetime, sys
from nabcommon import nabservice

class NabClockd(nabservice.NabService,asyncio.Protocol):
  def __init__(self):
    super().__init__()
    from . import models
    self.config = models.Config.load()
    self.loop_cv = asyncio.Condition()
    self.asleep = None
    self.last_chime = None

  async def reload_config(self):
    from django.core.cache import cache
    cache.clear()
    from . import models
    self.config = models.Config.load()
    async with self.loop_cv:
      self.loop_cv.notify()
  
  def valid_time(self, now):
    return now > datetime.datetime(2018,11,1)
  
  def chime(self, hour):
    now = datetime.datetime.now()
    expiration = now + datetime.timedelta(minutes=3)
    # TODO : audio sequence for hour.
    packet = '{"type":"command","sequence":[{"audio":[],"choregraphy":"streaming"}],"expiration":"' + expiration.isoformat() + '"}\r\n'
    self.writer.write(packet.encode('utf8'))

  def clock_response(self, now):
    response = []
    if self.valid_time(now):
      should_sleep = None
      if self.config.wakeup_hour != None and \
         self.config.sleep_hour != None and \
         self.config.wakeup_min != None and \
         self.config.sleep_min != None:
        if (self.config.wakeup_hour, self.config.wakeup_min) < (self.config.sleep_hour, self.config.sleep_min):
          should_sleep = (now.hour, now.minute) < (self.config.wakeup_hour, self.config.wakeup_min) or (now.hour, now.minute) >= (self.config.sleep_hour, self.config.sleep_min)
        else:
          should_sleep = (now.hour, now.minute) < (self.config.wakeup_hour, self.config.wakeup_min) and (now.hour, now.minute) >= (self.config.sleep_hour, self.config.sleep_min)
      if should_sleep != None and self.asleep != None and should_sleep != self.asleep:
        if should_sleep:
          response.append('sleep')
        else:
          response.append('wakeup')
      if (should_sleep == None or should_sleep == False) and now.minute == 0 and self.config.chime_hour:
        if self.last_chime != now.hour:
          response.append('chime')
      if now.minute > 5: # account for time drifts
        response.append('reset_last_chime')
    return response

  async def clock_loop(self):
    try:
      async with self.loop_cv:
        while self.running:
          try:
            now = datetime.datetime.now()
            response = self.clock_response(now)
            for r in response:
              if r == 'sleep':
                self.writer.write(b'{"type":"sleep"}\r\n')
                self.asleep = None
              elif r == 'wakeup':
                self.writer.write(b'{"type":"wakeup"}\r\n')
                self.asleep = None
              elif r == 'chime':
                self.chime(now.hour)
                self.last_chime = now.hour
              elif r == 'reset_last_chime':
                self.last_chime = None
            sleep_amount = 60 - now.second
            await asyncio.wait_for(self.loop_cv.wait(), sleep_amount)
          except asyncio.TimeoutError:
            pass
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        asyncio.get_event_loop().stop()

  async def process_nabd_packet(self, packet):
    if 'type' in packet and packet['type'] == 'state' and 'state' in packet:
      self.asleep = packet['state'] == 'asleep'

  async def stop_clock_loop(self):
    async with self.loop_cv:
      self.running = False  # signal to exit
      self.loop_cv.notify()

  def run(self):
    super().connect()
    clock_task = self.loop.create_task(self.clock_loop())
    try:
      self.loop.run_forever()
      if clock_task.done():
        ex = clock_task.exception()
        if ex:
          raise ex
    except KeyboardInterrupt:
      pass
    finally:
      self.writer.close()
      self.loop.run_until_complete(self.stop_clock_loop())
      if sys.version_info >= (3,7):
        tasks = asyncio.all_tasks(self.loop)
      else:
        tasks = asyncio.Task.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      self.loop.close()

if __name__ == '__main__':
  NabClockd.main(sys.argv[1:])
