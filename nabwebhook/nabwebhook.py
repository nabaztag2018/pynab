import logging
import sys

import requests

from nabcommon.nabservice import NabService

from . import rfid_data


class NabWebhook(NabService):
    def __init__(self):
        super().__init__()
        print("launch")

    async def reload_config(self):
        pass

    async def _call_webhook(self, webhook_url, uid):
        logging.info("Call URL " + webhook_url)
        try:
            result = requests.get(webhook_url, timeout=10)
            logging.info("Result  " + result.text)
        except Exception:
            logging.error("Webhook exception (probably bad url)")

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabwebhook"
            and packet["event"] == "detected"
        ):
            webhook_url = await rfid_data.read_data_ui(packet["uid"])
            await self._call_webhook(webhook_url, packet["uid"])


if __name__ == "__main__":
    NabWebhook.main(sys.argv[1:])
