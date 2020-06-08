import sys
import datetime
import random
from nabcommon.nabservice import NabRandomService


class NabTaichid(NabRandomService):
    DAEMON_PIDFILE = "/run/nabtaichid.pid"

    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (config.next_taichi, None, config.taichi_frequency)

    async def update_next(self, next_date, next_args):
        from . import models

        config = await models.Config.load_async()
        config.next_taichi = next_date
        await config.save_async()

    async def perform(self, expiration, args, config):
        packet = (
            '{"type":"command",'
            '"sequence":[{"choreography":"nabtaichid/taichi.chor"}],'
            '"expiration":"' + expiration.isoformat() + '"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    def compute_random_delta(self, frequency):
        return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "asr_event"
            and packet["nlu"]["intent"] == "nabtaichid/taichi"
        ):
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            await self.perform(expiration, None, None)
        elif (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabtaichid"
            and packet["event"] == "detected"
        ):
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            await self.perform(expiration, None, None)


if __name__ == "__main__":
    NabTaichid.main(sys.argv[1:])
