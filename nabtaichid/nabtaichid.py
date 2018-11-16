import sys, asyncio, datetime, random
from nabcommon import nabservice

class NabTaichid(nabservice.NabService):
  DAEMON_PIDFILE = '/var/run/nabtaichid.pid'

  def __init__(self):
    super().__init__()
    from . import models
    self.config = models.Config.load()
    self.loop_cv = asyncio.Condition()
    self.taichi_frequency = self.config.taichi_frequency

  async def reload_config(self):
    from django.core.cache import cache
    cache.clear()
    from . import models
    self.config = models.Config.load()
    async with self.loop_cv:
      self.loop_cv.notify()

  async def taichi_loop(self):
    try:
      async with self.loop_cv:
        while self.running:
          try:
            now = datetime.datetime.now(datetime.timezone.utc)
            next_taichi = self.config.next_taichi
            if next_taichi != None and next_taichi <= now:
              self.do_taichi(next_taichi + datetime.timedelta(minutes=1))
              next_taichi = None
            if self.taichi_frequency != self.config.taichi_frequency or next_taichi == None:
              next_taichi = self.compute_next_taichi(self.config.taichi_frequency)
            if next_taichi != self.config.next_taichi:
              self.config.next_taichi = next_taichi
              self.config.save()
            self.taichi_frequency = self.config.taichi_frequency
            if next_taichi == None:
              sleep_amount = None
            else:
              sleep_amount = (next_taichi - now).total_seconds()
            await asyncio.wait_for(self.loop_cv.wait(), sleep_amount)
          except asyncio.TimeoutError:
            pass
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        asyncio.get_event_loop().stop()

  def do_taichi(self, expiration):
    packet = '{"type":"command","sequence":[{"choreography":"nabtaichid/taichi.chor"}],"expiration":"' + expiration.isoformat() + '"}\r\n'
    self.writer.write(packet.encode('utf8'))

  def compute_next_taichi(self, frequency):
    if frequency == 0:
      return None
    now = datetime.datetime.now(datetime.timezone.utc)
    next_taichi_delta = (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128
    return now + datetime.timedelta(seconds = next_taichi_delta)

  async def stop_taichi_loop(self):
    async with self.loop_cv:
      self.running = False  # signal to exit
      self.loop_cv.notify()

  def run(self):
    super().connect()
    taichi_task = self.loop.create_task(self.taichi_loop())
    try:
      self.loop.run_forever()
      if taichi_task.done():
        ex = clock_task.exception()
        if ex:
          raise ex
    except KeyboardInterrupt:
      pass
    finally:
      self.writer.close()
      self.loop.run_until_complete(self.stop_taichi_loop())
      if sys.version_info >= (3,7):
        tasks = asyncio.all_tasks(self.loop)
      else:
        tasks = asyncio.Task.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      self.loop.close()

if __name__ == '__main__':
  NabTaichid.main(sys.argv[1:])
