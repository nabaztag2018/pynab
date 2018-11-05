import sys, signal, asyncio, json, datetime
from nabcommon import nabservice

class NabClockd(nabservice.NabService,asyncio.Protocol):
  NABD_PORT = 10543

  def __init__(self):
    super().__init__()
    from . import models
    self.config = models.Config.load()
    self.loop_cv = asyncio.Condition()
    self.asleep = None
    self.last_chime = None
    signal.signal(signal.SIGUSR1, self.signal_handler)

  def signal_handler(sig, frame):
    from django.core.cache import cache
    cache.clear()
    self.config = models.Config.load()
  
  def valid_time(self, now):
    now > datetime.datetime(2018,11,1)
  
  def chime(self, hour):
    now = datetime.datetime.now()
    expiration = now + datetime.timedelta(minutes=3)
    # TODO : audio sequence for hour.
    self.writer.write('{"type":"command","sequence":[{"audio":[],"choregraphy":"streaming"}],"expiration":' + expiration.isoformat() + '\r\n')

  async def clock_loop(self):
    try:
      async with self.loop_cv:
        while self.running:
          try:
            now = datetime.datetime.now()
            if self.valid_time(now):
              should_sleep = None
              if self.config.wakeup_hour and self.config.sleep_hour and self.config.wakeup_min and self.config.sleep_min:
                if (self.config.wakeup_hour, self.config.wakeup_min) < (self.config.sleep_hour, self.config.sleep_min):
                  should_sleep = (now.hour, now_min) <= (self.config.wakeup_hour, self.config.wakeup_min) or (now.hour, now_min) >= (self.config.sleep_hour, self.config.sleep_min)
                else:
                  should_sleep = (now.hour, now_min) <= (self.config.wakeup_hour, self.config.wakeup_min) and (now.hour, now_min) >= (self.config.sleep_hour, self.config.sleep_min)
              if should_sleep != None and asleep != None and should_sleep != asleep:
                if should_sleep:
                  self.writer.write('{"type":"sleep"}\r\n')
                else:
                  self.writer.write('{"type":"wakeup"}\r\n')
              if should_sleep == None or should_sleep == False and now.min == 0 and self.config.chime_hour:
                if self.last_chime != now.hour:
                  chime(now.hour)
                  self.last_chime = now.hour
              if now.min > 5: # account for time drifts
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
    loop = asyncio.get_event_loop()
    clock_task = loop.create_task(self.clock_loop())
    try:
      loop.run_forever()
      if clock_task.done():
        ex = clock_task.exception()
        if ex:
          raise ex
    except KeyboardInterrupt:
      pass
    finally:
      self.writer.close()
      loop.run_until_complete(self.stop_clock_loop())
      tasks = asyncio.all_tasks(loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        loop.run_until_complete(t)    # give canceled tasks the last chance to run
      loop.close()

if __name__ == '__main__':
  service = NabClockd()
  service.run()
