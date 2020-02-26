import asyncio
from functools import partial
import json
from nabbookd.nabbookd import NabBookd
from nabd.tests.mock import NabdMockTestCase


class TestNabbookd(NabdMockTestCase):
    def test_connect(self):
        self.do_test_connect(NabBookd)

    async def packet_list_handler(self, packets, reader, writer):
        await writer.drain()
        self.packet_list_handler_called += 1
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode())
                self.packet_list_handler_packets.append(packet)
                if hasattr(self, "packet_handler"):
                    await self.packet_handler(packet, writer)
                if packets:
                    for packet in packets:
                        writer.write((json.dumps(packet) + "\r\n").encode())
                    packets = None

    async def send_responses_packet_handler(self, packet, writer):
        if (
            "type" in packet
            and packet["type"] == "command"
            and self.state == "idle"
        ):
            playing_state = {"type": "state", "state": "playing"}
            writer.write((json.dumps(playing_state) + "\r\n").encode())
        elif (
            "type" in packet
            and packet["type"] == "mode"
            and packet["mode"] == "idle"
        ):
            self.state = "idle"
            new_state = {"type": "state", "state": "idle"}
            writer.write((json.dumps(new_state) + "\r\n").encode())
        elif (
            "type" in packet
            and packet["type"] == "mode"
            and packet["mode"] == "interactive"
        ):
            self.state = "interactive"
            new_state = {"type": "state", "state": "interactive"}
            writer.write((json.dumps(new_state) + "\r\n").encode())
        response = {"type": "response", "status": "ok"}
        if "request_id" in packet:
            response["request_id"] = packet["request_id"]
        writer.write((json.dumps(response) + "\r\n").encode())

    def test_play_sequence_default(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        self.packet_handler = self.send_responses_packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 24)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/2.mp3",
        )
        self.assertEqual(received_packets[5]["type"], "command")
        self.assertEqual(
            received_packets[5]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/3.mp3",
        )
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/4.mp3",
        )
        self.assertEqual(received_packets[7]["type"], "command")
        self.assertEqual(
            received_packets[7]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/5.mp3",
        )
        self.assertEqual(received_packets[8]["type"], "command")
        self.assertEqual(
            received_packets[8]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/6.mp3",
        )
        self.assertEqual(received_packets[9]["type"], "command")
        self.assertEqual(
            received_packets[9]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/7.mp3",
        )
        self.assertEqual(received_packets[10]["type"], "command")
        self.assertEqual(
            received_packets[10]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/8.mp3",
        )
        self.assertEqual(received_packets[11]["type"], "command")
        self.assertEqual(
            received_packets[11]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/9.mp3",
        )
        self.assertEqual(received_packets[12]["type"], "command")
        self.assertEqual(
            received_packets[12]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/10.mp3",
        )
        self.assertEqual(received_packets[13]["type"], "command")
        self.assertEqual(
            received_packets[13]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/11.mp3",
        )
        self.assertEqual(received_packets[14]["type"], "command")
        self.assertEqual(
            received_packets[14]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/12.mp3",
        )
        self.assertEqual(received_packets[15]["type"], "command")
        self.assertEqual(
            received_packets[15]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/13.mp3",
        )
        self.assertEqual(received_packets[16]["type"], "command")
        self.assertEqual(
            received_packets[16]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/14.mp3",
        )
        self.assertEqual(received_packets[17]["type"], "command")
        self.assertEqual(
            received_packets[17]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/15.mp3",
        )
        self.assertEqual(received_packets[18]["type"], "command")
        self.assertEqual(
            received_packets[18]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/16.mp3",
        )
        self.assertEqual(received_packets[19]["type"], "command")
        self.assertEqual(
            received_packets[19]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/17.mp3",
        )
        self.assertEqual(received_packets[20]["type"], "command")
        self.assertEqual(
            received_packets[20]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/18.mp3",
        )
        self.assertEqual(received_packets[21]["type"], "command")
        self.assertEqual(
            received_packets[21]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/19.mp3",
        )
        self.assertEqual(received_packets[22]["type"], "command")
        self.assertEqual(
            received_packets[22]["sequence"][0]["audio"],
            "nabbookd/outro-alt.mp3",
        )
        self.assertEqual(
            received_packets[22]["sequence"][0]["choreography"],
            "nabbookd/outro-alt.chor",
        )
        self.assertEqual(received_packets[23]["type"], "mode")
        self.assertEqual(received_packets[23]["mode"], "idle")
        self.assertEqual(received_packets[23]["events"], ["rfid/nabbookd"])

    def test_play_sequence_altvoice(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "nabaztag/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        self.packet_handler = self.send_responses_packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 14)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/2.mp3",
        )
        self.assertEqual(received_packets[5]["type"], "command")
        self.assertEqual(
            received_packets[5]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/3.mp3",
        )
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/4.mp3",
        )
        self.assertEqual(received_packets[7]["type"], "command")
        self.assertEqual(
            received_packets[7]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/5.mp3",
        )
        self.assertEqual(received_packets[8]["type"], "command")
        self.assertEqual(
            received_packets[8]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/6.mp3",
        )
        self.assertEqual(received_packets[9]["type"], "command")
        self.assertEqual(
            received_packets[9]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/7.mp3",
        )
        self.assertEqual(received_packets[10]["type"], "command")
        self.assertEqual(
            received_packets[10]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/8.mp3",
        )
        self.assertEqual(received_packets[11]["type"], "command")
        self.assertEqual(
            received_packets[11]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/nabaztag/9.mp3",
        )
        self.assertEqual(
            received_packets[12]["sequence"][0]["audio"],
            "nabbookd/outro-alt.mp3",
        )
        self.assertEqual(
            received_packets[12]["sequence"][0]["choreography"],
            "nabbookd/outro-alt.chor",
        )
        self.assertEqual(received_packets[13]["type"], "mode")
        self.assertEqual(received_packets[13]["mode"], "idle")
        self.assertEqual(received_packets[13]["events"], ["rfid/nabbookd"])

    def test_play_sequence_noalt(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782092512593",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        self.packet_handler = self.send_responses_packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 15)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/2.mp3",
        )
        self.assertEqual(received_packets[5]["type"], "command")
        self.assertEqual(
            received_packets[5]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/3.mp3",
        )
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/4.mp3",
        )
        self.assertEqual(received_packets[7]["type"], "command")
        self.assertEqual(
            received_packets[7]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/5.mp3",
        )
        self.assertEqual(received_packets[8]["type"], "command")
        self.assertEqual(
            received_packets[8]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/6.mp3",
        )
        self.assertEqual(received_packets[9]["type"], "command")
        self.assertEqual(
            received_packets[9]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/7.mp3",
        )
        self.assertEqual(received_packets[10]["type"], "command")
        self.assertEqual(
            received_packets[10]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/8.mp3",
        )
        self.assertEqual(received_packets[11]["type"], "command")
        self.assertEqual(
            received_packets[11]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/9.mp3",
        )
        self.assertEqual(received_packets[12]["type"], "command")
        self.assertEqual(
            received_packets[12]["sequence"][0]["audio"],
            "nabbookd/books/9782092512593/default/10.mp3",
        )
        self.assertEqual(
            received_packets[13]["sequence"][0]["audio"],
            "nabbookd/outro-noalt.mp3",
        )
        self.assertEqual(
            received_packets[13]["sequence"][0]["choreography"],
            "nabbookd/outro-noalt.chor",
        )
        self.assertEqual(received_packets[14]["type"], "mode")
        self.assertEqual(received_packets[14]["mode"], "idle")
        self.assertEqual(received_packets[14]["events"], ["rfid/nabbookd"])

    async def button_packet_handler(self, substring, packet, writer):
        self.event_packets = [
            {"type": "button_event", "event": "up"},
            {"type": "button_event", "event": "down"},
            {"type": "button_event", "event": "click"},
        ]
        await self.event_packet_handler(substring, packet, writer)

    async def event_packet_handler(self, substring, packet, writer):
        if "type" in packet and packet["type"] == "cancel":
            status = "canceled"
        else:
            status = "ok"
        if (
            "type" in packet
            and packet["type"] == "command"
            and self.state == "idle"
        ):
            playing_state = {"type": "state", "state": "playing"}
            writer.write((json.dumps(playing_state) + "\r\n").encode())
        elif (
            "type" in packet
            and packet["type"] == "mode"
            and packet["mode"] == "idle"
        ):
            self.state = "idle"
            new_state = {"type": "state", "state": "idle"}
            writer.write((json.dumps(new_state) + "\r\n").encode())
        elif (
            "type" in packet
            and packet["type"] == "mode"
            and packet["mode"] == "interactive"
        ):
            self.state = "interactive"
            new_state = {"type": "state", "state": "interactive"}
            writer.write((json.dumps(new_state) + "\r\n").encode())
        if (
            packet["type"] == "command"
            and substring in packet["sequence"][0]["audio"]
            and self.event_packets != []
        ):
            for packet in self.event_packets:
                writer.write((json.dumps(packet) + "\r\n").encode())
            self.event_packets = []
        else:
            response = {"type": "response", "status": status}
            if "request_id" in packet:
                response["request_id"] = packet["request_id"]
            writer.write((json.dumps(response) + "\r\n").encode())

    def test_play_sequence_button_chapter_2(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        packet_handler = partial(self.button_packet_handler, "/2.mp3")
        self.packet_handler = packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 8)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/2.mp3",
        )
        self.assertEqual(received_packets[4]["request_id"], "reading")
        self.assertEqual(received_packets[5]["type"], "cancel")
        self.assertEqual(received_packets[5]["request_id"], "reading")
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"], "nabd/abort.wav"
        )
        self.assertEqual(
            received_packets[6]["sequence"][1]["audio"],
            "nabbookd/interrupt.mp3",
        )
        self.assertEqual(
            received_packets[6]["sequence"][1]["choreography"],
            "nabbookd/interrupt.chor",
        )
        self.assertEqual(received_packets[7]["type"], "mode")
        self.assertEqual(received_packets[7]["mode"], "idle")
        self.assertEqual(received_packets[7]["events"], ["rfid/nabbookd"])

    def test_play_sequence_button_intro(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        packet_handler = partial(self.button_packet_handler, "/intro.mp3")
        self.packet_handler = packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 6)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "cancel")
        self.assertEqual(received_packets[3]["request_id"], "intro")
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"], "nabd/abort.wav"
        )
        self.assertEqual(received_packets[5]["type"], "mode")
        self.assertEqual(received_packets[5]["mode"], "idle")
        self.assertEqual(received_packets[5]["events"], ["rfid/nabbookd"])

    def test_play_sequence_button_outro(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        packet_handler = partial(self.button_packet_handler, "/outro-alt.mp3")
        self.packet_handler = packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(len(received_packets), 26)
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[22]["type"], "command")
        self.assertEqual(
            received_packets[22]["sequence"][0]["audio"],
            "nabbookd/outro-alt.mp3",
        )
        self.assertEqual(
            received_packets[22]["sequence"][0]["choreography"],
            "nabbookd/outro-alt.chor",
        )
        self.assertEqual(received_packets[23]["type"], "cancel")
        self.assertEqual(received_packets[23]["request_id"], "outro")
        self.assertEqual(received_packets[24]["type"], "command")
        self.assertEqual(
            received_packets[24]["sequence"][0]["audio"], "nabd/abort.wav"
        )
        self.assertEqual(received_packets[25]["type"], "mode")
        self.assertEqual(received_packets[25]["mode"], "idle")
        self.assertEqual(received_packets[25]["events"], ["rfid/nabbookd"])

    def test_play_sequence_forward_chapter_2(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        self.event_packets = [{"type": "ear_event", "ear": "right"}]
        packet_handler = partial(self.event_packet_handler, "/2.mp3")
        self.packet_handler = packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/2.mp3",
        )
        self.assertEqual(received_packets[4]["request_id"], "reading")
        self.assertEqual(received_packets[5]["type"], "cancel")
        self.assertEqual(received_packets[5]["request_id"], "reading")
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"], "nabbookd/next.mp3"
        )
        self.assertEqual(received_packets[7]["type"], "command")
        self.assertEqual(
            received_packets[7]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/3.mp3",
        )
        self.assertEqual(received_packets[8]["type"], "command")
        self.assertEqual(
            received_packets[8]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/4.mp3",
        )

    def test_play_sequence_backward_chapter_2(self):
        sent_packets = [
            {"type": "state", "state": "idle", },
            {
                "type": "rfid_event",
                "event": "detected",
                "app": "nabbookd",
                "data": "default/9782070548064",
            },
        ]
        handler = partial(self.packet_list_handler, sent_packets)
        self.mock_connection_handler = handler
        self.event_packets = [{"type": "ear_event", "ear": "left"}]
        packet_handler = partial(self.event_packet_handler, "/2.mp3")
        self.packet_handler = packet_handler
        self.packet_list_handler_called = 0
        self.packet_list_handler_packets = []
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = NabBookd()
        service.run()
        self.assertEqual(self.packet_list_handler_called, 1)
        received_packets = self.packet_list_handler_packets
        self.assertEqual(received_packets[0]["type"], "mode")
        self.assertEqual(received_packets[0]["mode"], "idle")
        self.assertEqual(received_packets[0]["events"], ["rfid/nabbookd"])
        self.assertEqual(received_packets[1]["type"], "mode")
        self.assertEqual(received_packets[1]["mode"], "interactive")
        self.assertEqual(received_packets[1]["events"], ["button", "ears"])
        self.assertEqual(received_packets[2]["type"], "command")
        self.assertEqual(
            received_packets[2]["sequence"][0]["audio"], "nabbookd/intro.mp3"
        )
        self.assertEqual(
            received_packets[2]["sequence"][0]["choreography"],
            "nabbookd/intro.chor",
        )
        self.assertEqual(received_packets[3]["type"], "command")
        self.assertEqual(
            received_packets[3]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/1.mp3",
        )
        self.assertEqual(received_packets[4]["type"], "command")
        self.assertEqual(
            received_packets[4]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/2.mp3",
        )
        self.assertEqual(received_packets[4]["request_id"], "reading")
        self.assertEqual(received_packets[5]["type"], "cancel")
        self.assertEqual(received_packets[5]["request_id"], "reading")
        self.assertEqual(received_packets[6]["type"], "command")
        self.assertEqual(
            received_packets[6]["sequence"][0]["audio"],
            "nabbookd/previous.mp3",
        )
        self.assertEqual(received_packets[7]["type"], "command")
        self.assertEqual(
            received_packets[7]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/1.mp3",
        )
        self.assertEqual(received_packets[8]["type"], "command")
        self.assertEqual(
            received_packets[8]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/2.mp3",
        )
        self.assertEqual(received_packets[9]["type"], "command")
        self.assertEqual(
            received_packets[9]["sequence"][0]["audio"],
            "nabbookd/books/9782070548064/default/3.mp3",
        )
