import asyncio
import re
import sys
from operator import attrgetter
import logging
import json

from nabcommon.nabservice import NabService
from nabcommon.typing import NabdPacket
import asyncio_mqtt as aiomqtt
import paho.mqtt as mqtt

class Nabmqttd(NabService):
    DAEMON_PIDFILE = "/run/nabmqttd.pid"

    RETRY_DELAY = 15 * 60  # Retry to reconnect every 15 minutes.
    NABPAIRING_MESSAGE_RE = (
        r"NabPairing (?P<cmd>Proposal|Acceptation|Rejection|Divorce|Ears "
        r'(?P<left>[0-9]+) (?P<right>[0-9]+)) - (?:<a href=")?'
        r"https://github.com/nabaztag2018/pynab"
    )
    PROTOCOL_MESSAGES = {
        "proposal": "Would you accept to be my spouse? "
        "(NabPairing Proposal - https://github.com/nabaztag2018/pynab)",
        "acceptation": "Oh yes, I do accept to be your spouse "
        "(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)",
        "rejection": "Sorry, I cannot be your spouse right now "
        "(NabPairing Rejection - https://github.com/nabaztag2018/pynab)",
        "divorce": "I think we should split. Can we skip the lawyers? "
        "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)",
        "ears": "Let's dance (NabPairing Ears {left} {right} - "
        "https://github.com/nabaztag2018/pynab)",
    }

    def __init__(self):
        super().__init__()
        self.mqtt_client = None
        self.current_access_token=None
        self.listening = False
        self.status_left_ear_position = None
        self.status_right_ear_position = None

    async def __config(self):
        from . import models

        return await models.Config.load_async()

    async def reload_config(self):
        await self.setup_initial_state()

    def close_streaming(self):
        self.current_access_token=None
        print("mqtt closed")

    

    async def rx_loop(self):  
        try:
            while self.running:
                config = await self.__config()
                async with aiomqtt.Client(
                                 hostname=config.mqtt_host,
                                 port=int(config.mqtt_port),
                                 username=config.mqtt_user,
                                 password=config.mqtt_pw
                             ) as mqtt_client:
                    async with mqtt_client.messages() as messages:
                            await mqtt_client.subscribe(f"{config.mqtt_topic}/rcv/#")
                            async for message in messages:
                                print(f"{message.payload.decode()}\r\n")
                                self.writer.write(f"{message.payload.decode()}\r\n".encode("utf8"))
                                await self.writer.drain()
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                asyncio.get_event_loop().stop()
        







    async def play_message(self, message, sender_name):
        """
        Play pairing protocol message
        """
        if message == "ears":
            packet = (
                '{"type":"command",'
                '"sequence":[{"audio":["nabmqttd/communion.wav"]}]}\r\n'
            )
        elif message == "proposal_received":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmqttd/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmqttd/proposal_received.mp3"]}]}'
                "\r\n"
            )
        elif message == "proposal_refused":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmqttd/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmqttd/proposal_refused.mp3"]}]}'
                "\r\n"
            )
        elif message == "proposal_accepted":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmqttd/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmqttd/proposal_accepted.mp3"]}]}'
                "\r\n"
            )
        elif message == "pairing_cancelled":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmqttd/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmqttd/pairing_cancelled.mp3"]}]}'
                "\r\n"
            )
        elif message == "setup":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmqttd/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmqttd/setup.mp3"]}]}'
                "\r\n"
            )
        else:
            return
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    async def send_start_listening(self):
        if self.listening is False:
            packet = '{"type":"mode","mode":"idle","events":["asr/*","button","ears","rfid/*"]}\r\n'
            self.writer.write(packet.encode("utf8"))
            await self.writer.drain()
            self.listening = True

    async def send_stop_listening(self):
        if self.listening:
            packet = '{"type":"mode","mode":"idle","events":[]}\r\n'
            self.writer.write(packet.encode("utf8"))
            await self.writer.drain()
            self.listening = False

    async def send_ears(self, left_ear, right_ear):
        packet = f'{{"type":"ears","left":{left_ear},"right":{right_ear}}}\r\n'
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()



   

    async def process_nabd_packet(self, packet: NabdPacket):
        config = await self.__config()
        print(packet)
        async with aiomqtt.Client(
                                 hostname=config.mqtt_host,
                                 port=int(config.mqtt_port),
                                 username=config.mqtt_user,
                                 password=config.mqtt_pw
                             ) as mqtt_client:
            await mqtt_client.publish(f"{config.mqtt_topic}/TX", payload=json.dumps(packet))


    async def setup_initial_state(self):
        config = await self.__config()
        await self.send_start_listening()
        if self.status_left_ear_position is not None:
            await self.send_ears(
                self.status_left_ear_position,
                self.status_right_ear_position,
            )


    def run(self):
        print("start")
        super().connect()
        self.loop = asyncio.get_event_loop()
        
        self.loop.run_until_complete(self.setup_initial_state())
        self.loop.run_until_complete(self.rx_loop())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False  # signal to exit
            self.writer.close()
            self.close_streaming()
            tasks = asyncio.all_tasks(self.loop)
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                self.loop.run_until_complete(
                    t
                )  # give canceled tasks the last chance to run
            self.loop.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Nabmqttd.main(sys.argv[1:])
