import sys
import datetime
import random
from nabcommon.nabservice import NabRandomService
from . import rfid_data


class NabSurprised(NabRandomService):
    NLU_INTENTS = ["nabsurprised/surprise", "nabsurprised/carrot", "nabsurprised/autopromo", "nabsurprised/birthday"]

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
        return (256 - frequency) * 60 * (random.uniform(0, 255) + 64) / 128

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
