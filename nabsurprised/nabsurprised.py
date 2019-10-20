import sys
import datetime
import random
from nabcommon.nabservice import NabRandomService


class NabSurprised(NabRandomService):
    def get_config(self):
        from . import models

        config = models.Config.load()
        return (config.next_surprise, config.surprise_frequency)

    def update_next(self, next_date, next_args):
        from . import models

        config = models.Config.load()
        config.next_surprise = next_date
        config.save()

    def perform(self, expiration, args):
        packet = (
            '{"type":"message",'
            '"signature":{"audio":["nabsurprised/respirations/*.mp3"]},'
            '"body":[{"audio":["nabsurprised/*.mp3"]}],'
            '"expiration":"' + expiration.isoformat() + '"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))

    def compute_random_delta(self, frequency):
        return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

    async def process_nabd_packet(self, packet):
        if packet["type"] == "asr_event":
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            if packet["nlu"]["intent"] == "surprise":
                self.perform(expiration, None)
            if packet["nlu"]["intent"] == "carot":
                packet = (
                    '{"type":"message","signature":{'
                    '"audio":["nabsurprised/respirations/*.mp3"]},'
                    '"body":[{"audio":["nabsurprised/carot/*.mp3"]}],'
                    '"expiration":"' + expiration.isoformat() + '"}\r\n'
                )
                self.writer.write(packet.encode("utf8"))


if __name__ == "__main__":
    NabSurprised.main(sys.argv[1:])
