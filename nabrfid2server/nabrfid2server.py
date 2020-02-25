import sys
import requests
from nabcommon.nabservice import NabService



class NabRfid2server(NabService):
    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (None, None, config.rfid_2_server_mode,config.rfid_2_server_url)

    async def process_nabd_packet(self, packet):
        if (packet["type"] != "rfid_event"):
            self.send_rfid_2_url("0001020304050607","Setting Test","No")
            return
        if ( packet["event"] != "detected" or self.rfid_2_url_mode==0 ): return # Never send url
        if (self.rfid_2_url_mode==1) and packet["supported"] and (packet["app"]==255) : return # Send only unknown tags
        uid = packet["uid"]
        app = packet["app"]
        supp= packet["supported"]
        self.send_rfid_2_url(uid,app,supported)

    def send_rfid_2_url(self, uid,app,supported):
        str_uid = uid
        url_message = self.rfid_2_url_url.replace("#RFID_TAG#",uid)
        url_message = url_message.replace("#RFID_APP#",app)
        url_message = url_message.replace("#RFID_FLAGS#",supported)
        #url_message = url_message.replace("#RFID_STATE#",self.__state.name)
        f = requests.get(url_message)

if __name__ == "__main__":
    NabRfid2server.main(sys.argv[1:])
