import asyncio
import json
import threading
import time
from django.test import TestCase, Client
from django.http import JsonResponse
from nabcommon import nabservice


class TestView(TestCase):
    def test_get_home(self):
        c = Client()
        response = c.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabweb/index.html")
        self.assertTrue("services" in response.context)
        self.assertTrue("nabmastodond" in response.context["services"])
        self.assertTrue("current_locale" in response.context)
        self.assertEqual(response.context["current_locale"], "fr_FR")

    def test_post_home_empty(self):
        c = Client()
        response = c.post("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabweb/index.html")
        self.assertTrue("services" in response.context)
        self.assertTrue("nabmastodond" in response.context["services"])
        self.assertTrue("current_locale" in response.context)
        self.assertEqual(response.context["current_locale"], "fr_FR")

    def test_post_home_set_locale(self):
        c = Client()
        response = c.post("/", {"locale": "en_US"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabweb/index.html")
        self.assertTrue("services" in response.context)
        self.assertTrue("nabmastodond" in response.context["services"])
        self.assertTrue("current_locale" in response.context)
        self.assertEqual(response.context["current_locale"], "en_US")

    def test_get_rfid(self):
        c = Client()
        response = c.get("/rfid/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabweb/rfid/index.html")
        self.assertTrue("rfid_services" in response.context)
        rfid_services = response.context["rfid_services"]
        for item in rfid_services:
            self.assertTrue("app" in item)
            self.assertTrue("name" in item)
        self.assertTrue("rfid_support" in response.context)
        self.assertEqual(response.context["rfid_support"]["status"], "error")

    def test_get_services(self):
        c = Client()
        response = c.get("/services/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweb/services/index.html"
        )
        self.assertTrue("services" in response.context)
        self.assertFalse("nabmastodond" in response.context["services"])
        self.assertTrue("current_locale" in response.context)
        self.assertEqual(response.context["current_locale"], "fr_FR")


class TestNabdClientBase(TestCase):
    async def mock_nabd_service_handler(self, reader, writer):
        self.service_writer = writer
        if hasattr(self, "state_packet"):
            writer.write(self.state_packet)
        else:
            writer.write(b'{"type":"state","state":"idle"}\r\n')
        await writer.drain()
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                if packet["type"] == "gestalt" and hasattr(
                    self, "gestalt_answer"
                ):
                    response_packet = self.gestalt_answer.copy()
                    if "request_id" in packet:
                        response_packet["request_id"] = packet["request_id"]
                    response_json = json.JSONEncoder().encode(response_packet)
                    response_json += "\r\n"
                    writer.write(response_json.encode("utf8"))
                    self.gestalt_answered += 1
                elif hasattr(self, "packet_handler"):
                    self.packet_handler(packet, writer)

    def mock_nabd_thread_entry_point(self, kwargs):
        self.mock_nabd_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.mock_nabd_loop)
        server_task = self.mock_nabd_loop.create_task(
            asyncio.start_server(
                self.mock_nabd_service_handler,
                "localhost",
                nabservice.NabService.PORT_NUMBER,
            )
        )
        try:
            self.mock_nabd_loop.run_forever()
        finally:
            server = server_task.result()
            server.close()
            if self.service_writer:
                self.service_writer.close()
            self.mock_nabd_loop.close()

    def setUp(self):
        self.service_writer = None
        self.mock_nabd_loop = None
        self.mock_nabd_thread = threading.Thread(
            target=self.mock_nabd_thread_entry_point, args=[self]
        )
        self.mock_nabd_thread.start()
        time.sleep(1)

    def tearDown(self):
        self.mock_nabd_loop.call_soon_threadsafe(
            lambda: self.mock_nabd_loop.stop()
        )
        self.mock_nabd_thread.join(3)


class TestRfidView(TestNabdClientBase):
    def test_get_rfid_unsupported(self):
        self.gestalt_answer = {"type": "response", "hardware": {"rfid": False}}
        self.gestalt_answered = 0
        c = Client()
        response = c.get("/rfid/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.gestalt_answered, 1)
        self.assertEqual(response.templates[0].name, "nabweb/rfid/index.html")
        self.assertTrue("rfid_services" in response.context)
        rfid_services = response.context["rfid_services"]
        for item in rfid_services:
            self.assertTrue("app" in item)
            self.assertTrue("name" in item)
        self.assertTrue("rfid_support" in response.context)
        self.assertEqual(response.context["rfid_support"]["status"], "ok")
        self.assertEqual(response.context["rfid_support"]["available"], False)

    def test_get_rfid_supported(self):
        self.gestalt_answer = {"type": "response", "hardware": {"rfid": True}}
        self.gestalt_answered = 0
        c = Client()
        response = c.get("/rfid/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.gestalt_answered, 1)
        self.assertEqual(response.templates[0].name, "nabweb/rfid/index.html")
        self.assertTrue("rfid_services" in response.context)
        rfid_services = response.context["rfid_services"]
        for item in rfid_services:
            self.assertTrue("app" in item)
            self.assertTrue("name" in item)
        self.assertTrue("rfid_support" in response.context)
        self.assertEqual(response.context["rfid_support"]["status"], "ok")
        self.assertEqual(response.context["rfid_support"]["available"], True)


class TestRfidReadView(TestNabdClientBase):
    def read_timeout_handler(self, packet, writer):
        self.packets.append(packet)
        response_packet = None
        if packet["type"] == "mode":
            response_packet = {"type": "response"}
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        elif packet["type"] == "command":
            response_packet = {"type": "response"}
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        if response_packet:
            response_json = json.JSONEncoder().encode(response_packet)
            response_json += "\r\n"
            writer.write(response_json.encode("utf8"))

    def test_read_timeout(self):
        self.packet_handler = self.read_timeout_handler
        self.packets = []
        c = Client()
        response = c.post("/rfid/read")
        self.assertEqual(response.status_code, 200)
        print(self.packets)
        self.assertEqual(len(self.packets), 2)
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "timeout")

    def read_rfid_handler(self, packet, writer):
        self.packets.append(packet)
        response_packet = None
        if packet["type"] == "mode":
            response_packet = {"type": "response"}
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        elif packet["type"] == "command":
            response_packet = {"type": "response"}
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        if response_packet:
            response_json = json.JSONEncoder().encode(response_packet)
            response_json += "\r\n"
            writer.write(response_json.encode("utf8"))
        if packet["type"] == "command":
            event_json = json.JSONEncoder().encode(self.rfid_event)
            event_json += "\r\n"
            writer.write(event_json.encode("utf8"))

    def test_read_clear(self):
        self.packet_handler = self.read_rfid_handler
        self.rfid_event = {
            "type": "rfid_event",
            "event": "detected",
            "uid": "d0:02:18:01:02:03:04:05",
            "support": "empty",
        }
        self.packets = []
        c = Client()
        response = c.post("/rfid/read")
        self.assertEqual(response.status_code, 200)
        print(self.packets)
        self.assertEqual(len(self.packets), 2)
        self.assertEqual(self.packets[0]["type"], "mode")
        self.assertEqual(self.packets[1]["type"], "command")
        self.assertTrue("sequence" in self.packets[1])
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "ok")
        self.assertTrue("event" in json_response)
        self.assertTrue("support" in json_response["event"])
        self.assertEqual(json_response["event"]["support"], "empty")

    def test_read_formatted(self):
        self.packet_handler = self.read_rfid_handler
        self.rfid_event = {
            "type": "rfid_event",
            "event": "detected",
            "uid": "d0:02:18:01:02:03:04:05",
            "app": "nabtaichid",
            "picture": 8,
            "data": "",
            "support": "formatted",
        }
        self.packets = []
        c = Client()
        response = c.post("/rfid/read")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.packets), 2)
        self.assertEqual(self.packets[0]["type"], "mode")
        self.assertEqual(self.packets[1]["type"], "command")
        self.assertTrue("sequence" in self.packets[1])
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "ok")
        self.assertTrue("event" in json_response)
        self.assertTrue("support" in json_response["event"])
        self.assertEqual(json_response["event"]["support"], "formatted")
        self.assertTrue("app" in json_response["event"])
        self.assertEqual(json_response["event"]["app"], "nabtaichid")
        self.assertTrue("picture" in json_response["event"])
        self.assertEqual(json_response["event"]["picture"], 8)


class TestRfidWriteView(TestNabdClientBase):
    def write_rfid_handler(self, packet, writer):
        self.packets.append(packet)
        response_packet = None
        if packet["type"] == "rfid_write":
            response_packet = self.write_response
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        if response_packet:
            response_json = json.JSONEncoder().encode(response_packet)
            response_json += "\r\n"
            writer.write(response_json.encode("utf8"))

    def test_write_ok(self):
        self.packet_handler = self.write_rfid_handler
        self.write_response = {"type": "response", "status": "ok"}
        self.packets = []
        c = Client()
        response = c.post(
            "/rfid/write",
            {
                "uid": "d0:02:18:01:02:03:04:05",
                "app": "nabweatherd",
                "picture": 8,
                "data": "\x02",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.packets), 1)
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "ok")
        self.assertTrue("rfid" in json_response)
        self.assertTrue("uid" in json_response["rfid"])
        self.assertEqual(
            json_response["rfid"]["uid"], "d0:02:18:01:02:03:04:05"
        )

    def test_write_missing_uid(self):
        self.packet_handler = self.write_rfid_handler
        self.write_response = {"type": "response", "status": "ok"}
        self.packets = []
        c = Client()
        response = c.post(
            "/rfid/write", {"app": "nabweatherd", "picture": 8, "data": "\x02"}
        )
        self.assertEqual(response.status_code, 400)

    def test_write_timeout(self):
        self.packet_handler = self.write_rfid_handler
        self.write_response = {"type": "response", "status": "timeout"}
        self.packets = []
        c = Client()
        response = c.post(
            "/rfid/write",
            {
                "uid": "d0:02:18:01:02:03:04:05",
                "app": "nabweatherd",
                "picture": 8,
                "data": "\x02",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.packets), 1)
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "timeout")


class TestShutdownView(TestNabdClientBase):
    def shutdown_view_handler(self, packet, writer):
        self.packets.append(packet)
        response_packet = None
        if packet["type"] == "shutdown":
            response_packet = self.write_response
            if "request_id" in packet:
                response_packet["request_id"] = packet["request_id"]
        if response_packet:
            response_json = json.JSONEncoder().encode(response_packet)
            response_json += "\r\n"
            writer.write(response_json.encode("utf8"))

    def test_post_reboot_action(self):
        self.packet_handler = self.shutdown_view_handler
        self.write_response = {"type": "response", "status": "ok"}
        self.packets = []
        c = Client()
        response = c.post("/system-info/shutdown/reboot", {"mode": "reboot"},)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.packets), 1)
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "ok")

    def test_post_shutdown_action(self):
        self.packet_handler = self.shutdown_view_handler
        self.write_response = {"type": "response", "status": "ok"}
        self.packets = []
        c = Client()
        response = c.post(
            "/system-info/shutdown/shutdown", {"mode": "shutdown"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.packets), 1)
        self.assertTrue(isinstance(response, JsonResponse))
        json_response = json.loads(response.content.decode("utf8"))
        self.assertTrue("status" in json_response)
        self.assertEqual(json_response["status"], "ok")
