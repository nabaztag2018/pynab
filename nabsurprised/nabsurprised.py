import sys
import datetime
import random
from nabcommon.nabservice import NabRandomService


class NabSurprised(NabRandomService):
    def get_config(self):
        from . import models

        config = models.Config.load()
        return (config.next_surprise, None, config.surprise_frequency)

    def update_next(self, next_date, next_args):
        from . import models

        config = models.Config.load()
        config.next_surprise = next_date
        config.save()

    async def perform(self, expiration, args, config):
        packet = (
            '{"type":"message",'
            '"signature":{"audio":["nabsurprised/respirations/*.mp3"]},'
            '"body":[{"audio":["nabsurprised/*.mp3"]}],'
            '"expiration":"' + expiration.isoformat() + '"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    def compute_random_delta(self, frequency):
        return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

    async def process_nabd_packet(self, packet):
        if packet["type"] == "asr_event":
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            if packet["nlu"]["intent"] == "surprise":
                await self.perform(expiration, None, None)
            if packet["nlu"]["intent"] == "carrot":
                packet = (
                    '{"type":"message","signature":{'
                    '"audio":["nabsurprised/respirations/*.mp3"]},'
                    '"body":[{"audio":["nabsurprised/carrot/*.mp3"]}],'
                    '"expiration":"' + expiration.isoformat() + '"}\r\n'
                )
                self.writer.write(packet.encode("utf8"))
                await self.writer.drain()
            if packet["nlu"]["intent"] == "autopromo":
                packet = (
                  '{"type":"message","signature":{'
                  '"audio":["nabsurprised/respirations/*.mp3"]},'
                  '"body":[{"audio":["nabsurprised/autopromo/*.mp3"]}],'
                  '"expiration":"' + expiration.isoformat() + '"}\r\n'
                )
                self.writer.write(packet.encode("utf8"))
                await self.writer.drain()


if __name__ == "__main__":
    NabSurprised.main(sys.argv[1:])
