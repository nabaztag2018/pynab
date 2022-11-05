import datetime
import logging
import sys

from nabcommon.nabservice import NabService

from . import rfid_data


class NabRadio(NabService):
    def __init__(self):
        super().__init__()
        print("launch")

    async def reload_config(self):
        pass

    async def _launch_radio(self, streaming_url, uid):
        logging.info("Launching radio " + streaming_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        expiration = now + datetime.timedelta(minutes=1)
        packet = (
            f'{{"type":"message",'
            f'"signature":{{"audio":["nabradio/*.mp3"]}},'
            f'"body":[{{"audio":["{streaming_url}"]}}],'
            f'"expiration":"{expiration.isoformat()}"}}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabradio"
            and packet["event"] == "detected"
        ):
            streaming_url = await rfid_data.read_data_ui(packet["uid"])
            await self._launch_radio(streaming_url, packet["uid"])


if __name__ == "__main__":
    NabRadio.main(sys.argv[1:])
