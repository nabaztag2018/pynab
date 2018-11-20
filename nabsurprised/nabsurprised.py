import sys, asyncio, datetime, random
from nabcommon.nabservice import NabRandomService

class NabSurprised(NabRandomService):
  DAEMON_PIDFILE = '/var/run/nabsurprised.pid'

  def get_config(self):
    from . import models
    config = models.Config.load()
    print('loading surprise config, next = {next}'.format(next = config.next_surprise))
    return (config.next_surprise, config.surprise_frequency)

  def update_next(self, next):
    from . import models
    config = models.Config.load()
    print('updating surprise config, next = {next}'.format(next = next))
    config.next_surprise = next
    config.save()

  def perform(self, expiration):
    print('performing surprise !')
    packet = '{"type":"message","signature":{"audio":"nabsurprised/respirations/*.mp3"},"body":[{"audio":["nabsurprised/*.mp3"]}],"expiration":"' + expiration.isoformat() + '"}\r\n'
    self.writer.write(packet.encode('utf8'))

  def compute_random_delta(self, frequency):
    return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

if __name__ == '__main__':
  NabSurprised.main(sys.argv[1:])
