import datetime
import random
import sys

from nabcommon.nabservice import NabRandomService

from . import rfid_data


class NabSurprised(NabRandomService):
    RARELY, SOMETIMES, OFTEN, VERY_OFTEN = 30, 50, 125, 250
    FREQUENCY_SECONDS = {
        RARELY: 10800,
        SOMETIMES: 7200,
        OFTEN: 3600,
        VERY_OFTEN: 1200,
    }

    NLU_INTENTS = [
        "nabsurprised/surprise",
        "nabsurprised/carrot",
        "nabsurprised/autopromo",
        "nabsurprised/birthday",
    ]

    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (config.next_surprise, None, config.surprise_frequency)

    async def update_next(self, next_date, next_args):
        from . import models

        config = await models.Config.load_async()
        config.next_surprise = next_date
        await config.save_async()

    async def perform(self, expiration, args, config):
        await self._do_perform(expiration, None, None)

    async def _do_perform(self, expiration, lang, type):
        if lang is None or lang == "default":
            lang_prefix = ""
        else:
            lang_prefix = lang + "/"
        if type is None:
            today = datetime.date.today()
            today_with_style = today.strftime("%m-%d")
            today_path = f"{lang_prefix}nabsurprised/{today_with_style}/*.mp3"
            regular_path = f"{lang_prefix}nabsurprised/*.mp3"
            path = today_path + ";" + regular_path
        else:
            if type == "surprise":
                type_subdir = ""
            else:
                type_subdir = type + "/"
            path = f"{lang_prefix}nabsurprised/{type_subdir}*.mp3"
        if expiration is None:
            now = datetime.datetime.now(datetime.timezone.utc)
            expiration = now + datetime.timedelta(minutes=1)
        packet = (
            f'{{"type":"message",'
            f'"signature":{{"audio":["nabsurprised/respirations/*.mp3"]}},'
            f'"body":[{{"audio":["{path}"]}}],'
            f'"expiration":"{expiration.isoformat()}"}}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    def compute_random_delta(self, frequency):
        if frequency == NabSurprised.VERY_OFTEN:
            return random.uniform(
                0, NabSurprised.FREQUENCY_SECONDS[NabSurprised.VERY_OFTEN]
            )  # nosec B311
        elif frequency == NabSurprised.OFTEN:
            return random.uniform(
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.VERY_OFTEN],
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.OFTEN],
            )  # nosec B311
        elif frequency == NabSurprised.SOMETIMES:
            return random.uniform(
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.OFTEN],
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.SOMETIMES],
            )  # nosec B311
        else:
            return random.uniform(
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.SOMETIMES],
                NabSurprised.FREQUENCY_SECONDS[NabSurprised.RARELY],
            )  # nosec B311

    async def process_nabd_packet(self, packet):
        if packet["type"] == "asr_event":
            intent = packet["nlu"]["intent"]
            if intent in NabSurprised.NLU_INTENTS:
                _, type = intent.split("/")
                await self._do_perform(None, None, type)
        elif (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabsurprised"
            and packet["event"] == "detected"
        ):
            if "data" in packet:
                lang, type = rfid_data.unserialize(
                    packet["data"].encode("utf8")
                )
            else:
                lang = "default"
                type = "surprise"
            await self._do_perform(None, lang, type)


if __name__ == "__main__":
    NabSurprised.main(sys.argv[1:])
