import sys, asyncio, datetime, random
from nabcommon.nabservice import NabRandomService

class NabTaichid(NabRandomService):
  DAEMON_PIDFILE = '/var/run/nabtaichid.pid'

  def get_config(self):
    from . import models
    config = models.Config.load()
    return (config.next_taichi, config.taichi_frequency)

  def update_next(self, next):
    from . import models
    config = models.Config.load()
    config.next_taichi = next
    config.save()

  def perform(self, expiration):
    packet = '{"type":"command","sequence":[{"choreography":"nabtaichid/taichi.chor"}],"expiration":"' + expiration.isoformat() + '"}\r\n'
    self.writer.write(packet.encode('utf8'))

  def compute_random_delta(self, frequency):
    return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

if __name__ == '__main__':
  NabTaichid.main(sys.argv[1:])
