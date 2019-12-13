import sys
import datetime
import random
from nabcommon.nabservice import NabRandomService


class NabTaichid(NabRandomService):
    DAEMON_PIDFILE = "/var/run/nabtaichid.pid"

    def get_config(self):
        from . import models

        config = models.Config.load()
        return (config.next_taichi, None, config.taichi_frequency)

    def update_next(self, next_date, next_args):
        from . import models

        config = models.Config.load()
        config.next_taichi = next_date
        config.save()

    def perform(self, expiration, args, config):
        packet = (
            '{"type":"command",'
            '"sequence":[{"choreography":"nabtaichid/taichi.chor"}],'
            '"expiration":"' + expiration.isoformat() + '"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))

    def compute_random_delta(self, frequency):
        return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "asr_event"
            and packet["nlu"]["intent"] == "taichi"
        ):
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            self.perform(expiration, None, None)


if __name__ == "__main__":
    NabTaichid.main(sys.argv[1:])
