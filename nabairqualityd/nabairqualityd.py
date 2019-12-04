import sys
import datetime
import dateutil.parser
from nabcommon.nabservice import NabRecurrentService
import logging
from . import aqicn


class NabAirqualityd(NabRecurrentService):

    MESSAGES = ["bad", "moderate", "good"]
    ANIMATION_1 = (
        '{"tempo":42,"colors":['
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )
    ANIMATION_2 = (
        '{"tempo":14,"colors":['
        '{"left":"000000","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"000000"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"000000","right":"00ffff"},'
        '{"left":"000000","center":"000000","right":"00ffff"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"000000"},'
        '{"left":"00ffff","center":"000000","right":"00ffff"},'
        '{"left":"000000","center":"00ffff","right":"00ffff"}]}'
    )
    ANIMATION_3 = (
        '{"tempo":14,"colors":['
        '{"left":"000000","center":"00ffff","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"00ffff","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"00ffff"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"00ffff","center":"00ffff","right":"000000"},'
        '{"left":"00ffff","center":"00ffff","right":"00ffff"},'
        '{"left":"000000","center":"000000","right":"00ffff"},'
        '{"left":"00ffff","center":"000000","right":"000000"},'
        '{"left":"000000","center":"00ffff","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"00ffff","center":"000000","right":"00ffff"},'
        '{"left":"000000","center":"00ffff","right":"000000"}]}'
    )

    ANIMATIONS = [ANIMATION_3, ANIMATION_2, ANIMATION_1]

    def __init__(self):
        self.index_airquality = 0
        super().__init__()

    def get_config(self):
        from . import models

        config = models.Config.load()
        # On boot or config update, update air quality info
        if (
            self.index_airquality is None
            or self.index_airquality != config.index_airquality
        ):
            self.index_airquality = config.index_airquality
            return (
                datetime.datetime.now(datetime.timezone.utc),
                "info",
                None,
            )
        else:
            return (
                config.next_performance_date,
                "today",
                None,
            )

    def update_next(self, next_date, next_args):
        from . import models

        config = models.Config.load()
        config.next_performance_date = next_date
        config.save()

    def compute_next(self, freq_config):
        # on veut la maj des data toutes les heures + info (=leds)
        now = datetime.datetime.now(datetime.timezone.utc)
        next_hour = now + datetime.timedelta(seconds=3600)
        return (next_hour, "info")

    def perform(self, expiration, type):

        self.update_airquality()

        info_animation = NabAirqualityd.ANIMATIONS[self.airquality]
        packet = (
            '{"type":"info","info_id":"airquality","animation":'
            + info_animation
            + "}\r\n"
        )
        self.writer.write(packet.encode("utf8"))

        if type == "today":
            message = NabAirqualityd.MESSAGES[self.airquality]
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabairqualityd/signature.mp3"]},'
                '"body":[{"audio":["nabairqualityd/' + message + '.mp3"]}],'
                '"expiration":"' + expiration.isoformat() + '"}\r\n'
            )
            self.writer.write(packet.encode("utf8"))

    def update_airquality(self):
        from . import models

        client = aqicn.aqicnClient(self.index_airquality)
        client.update()
        self.airquality = client.get_data()

        config = models.Config.load()
        config.localisation = client.get_city()
        config.save()

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "asr_event"
            and packet["nlu"]["intent"] == "airquality_forecast"
        ):
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
            self.perform(expiration, "today")


if __name__ == "__main__":
    NabAirqualityd.main(sys.argv[1:])
