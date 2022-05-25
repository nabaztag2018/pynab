import logging
import sys

import requests

from nabcommon.nabservice import NabService

from . import rfid_data


class NabIftttd(NabService):
    def __init__(self):
        super().__init__()
        self.__email = None

    async def reload_config(self):
        pass

    async def _call_ifttt(self, event_name, uid):
        from . import models

        config = await models.Config.load_async()

        ifttt_url = (
            "https://maker.ifttt.com/trigger/"
            + event_name
            + "/with/key/"
            + config.ifttt_key
            + "?value1="
            + uid
            + "&value2=❤️&value3=🐇"
        )
        logging.info("Calling IFTTT " + ifttt_url)
        result = requests.get(ifttt_url, timeout=10)
        print(result.text)

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabiftttd"
            and packet["event"] == "detected"
        ):
            event_name = await rfid_data.read_data_ui(packet["uid"])
            await self._call_ifttt(event_name, packet["uid"])


if __name__ == "__main__":
    NabIftttd.main(sys.argv[1:])
