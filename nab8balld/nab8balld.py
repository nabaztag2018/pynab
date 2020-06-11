import sys
import asyncio
from nabcommon.nabservice import NabService


class Nab8Balld(NabService):
    DAEMON_PIDFILE = "/run/nab8balld.pid"

    def __init__(self):
        super().__init__()
        self._interactive = False
        self._timeout_task = None

    async def __config(self):
        from . import models

        config = await models.Config.load_async()
        return config

    async def reload_config(self):
        from . import models

        await self.setup_listener()

    async def setup_listener(self):
        config = await self.__config()
        if config.enabled:
            packet = (
                '{"type":"mode","mode":"idle","events":["button","asr/nab8balld"],'
                '"request_id":"idle-button"}\r\n'
            )
        else:
            packet = (
                '{"type":"mode","mode":"idle","events":["asr/nab8balld"],'
                '"request_id":"idle-disabled"}\r\n'
            )
        self.writer.write(packet.encode("utf8"))

    async def perform(self):
        packet = (
            '{"type":"message",'
            '"body":[{"audio":["nab8balld/answers/*.mp3"]}],'
            '"request_id":"play-answer"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    async def process_nabd_packet(self, packet):
        if "type" in packet:
            processors = {
                "button_event": self.process_button_event_packet,
                "asr_event": self.process_asr_event_packet,
                "response": self.process_response_packet,
            }
            if packet["type"] in processors:
                await processors[packet["type"]](packet)

    async def process_button_event_packet(self, packet):
        if not self._interactive:
            if packet["event"] == "click_and_hold":
                await self.enter_interactive()
                self._timeout_task = asyncio.ensure_future(self.timeout_job())
        else:
            if packet["event"] == "up":
                if self._timeout_task:
                    self._timeout_task.cancel()
                    self._timeout_task = None
                await self.exit_interactive()

    async def enter_interactive(self):
        packet = (
            '{"type":"mode","mode":"interactive",'
            '"events":["button"],'
            '"request_id":"set-interactive"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    async def entered_interactive(self):
        self._interactive = True
        resp = (
            '{"type":"command",'
            '"sequence":[{"audio":["nab8balld/listen.mp3"],'
            '"choreography":"data:application/x-nabaztag-mtl-choreography;'
            'base64,AAcA/wD/AAAABwEAAAAAAAAHAgAAAAAAAAcDAAAAAAA="'
            "}],"
            '"request_id":"play-listen"}\r\n'
        )
        self.writer.write(resp.encode("utf8"))
        await self.writer.drain()

    async def exit_interactive(self):
        packet = (
            '{"type":"command",'
            '"sequence":[{"audio":["nab8balld/acquired.mp3"]}],'
            '"request_id":"play-acquired"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.perform()
        self._interactive = False
        await self.setup_listener()

    async def timeout_job(self):
        await asyncio.sleep(10)
        self._timeout_task = None
        self.exit_interactive()

    async def process_response_packet(self, packet):
        if (
            "request_id" in packet
            and packet["request_id"] == "set-interactive"
        ):
            await self.entered_interactive()

    async def process_asr_event_packet(self, packet):
        if packet["nlu"]["intent"] == "nab8balld/8ball":
            await self.perform()

    def run(self):
        super().connect()
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.setup_listener())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False  # signal to exit
            self.writer.close()
            tasks = asyncio.all_tasks(self.loop)
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                # give canceled tasks the last chance to run
                self.loop.run_until_complete(t)
            self.loop.close()


if __name__ == "__main__":
    Nab8Balld.main(sys.argv[1:])
