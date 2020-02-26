import sys
import json
import logging
import requests
from nabcommon.nabservice import NabService


class NabRfid2server(NabService):
    DAEMON_PIDFILE = "/run/nabrfid2server.pid"

    def __init__(self):
        super().__init__()
        from . import models

        self.config = models.Config.load()

    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (None, None, config.rfid_2_server_mode,config.rfid_2_server_url)

    async def reload_config(self):
        from . import models

        await self.setup_listener()

    async def process_nabd_packet(self, packet):
        if ( self.config.rfid_2_server_mode==0 ): return # Never send url
        if (packet["type"] == "state")or(packet["type"] == "response"): return
        if (packet["type"] != "rfid_event"):
            self.send_rfid_2_url(packet["type"],"Setting Test","No","--")
            return
        if "app" not in packet: app = "none"
        else: app = packet["app"]
        if "support" not in packet: supp = "support unknown"
        else: supp = packet["support"]
        if "event" not in packet: _event = "no event"
        else: _event = packet["event"]
        if (self.config.rfid_2_server_mode==1) and (supp=="formatted") and (app=="none") : return # Send only unknown tags
        self.send_rfid_2_url(packet["uid"],_event,app,supp)

    def send_rfid_2_url(self, uid,_event,app,supp):
        url_message = self.config.rfid_2_server_url.replace("#RFID_TAG#",uid)
        url_message = url_message.replace("#RFID_APP#",app)
        url_message = url_message.replace("#RFID_FLAGS#",supp)
        url_message = url_message.replace("#RFID_STATE#",_event)
        f = requests.get(url_message)

    async def client_loop(self):
        try:
            idle_packet = '{"type":"mode","mode":"idle","events":["rfid/*"]}\r\n'
            self.writer.write(idle_packet.encode())
            while self.running and not self.reader.at_eof():
                line = await self.reader.readline()
                if line != b"" and line != b"\r\n":
                    try:
                        packet = json.loads(line.decode("utf8"))
                        logging.debug(f"process nabd packet: {packet}")
                        await self.process_nabd_packet(packet)
                    except json.decoder.JSONDecodeError as e:
                        logging.error(
                            f"Invalid JSON packet from nabd: {line}\n{e}"
                        )
            self.writer.close()
            await self.writer.wait_closed()
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                self.loop.stop()

if __name__ == "__main__":
    NabRfid2server.main(sys.argv[1:])
