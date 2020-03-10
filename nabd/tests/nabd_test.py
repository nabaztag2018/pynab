import unittest
import threading
import time
import asyncio
import socket
import json
import io
import pytest
import datetime
from nabd import nabd
from nabd.rfid import TagFlags
from mock import NabIOMock
from utils import close_old_async_connections
from django.db import close_old_connections
import nabtaichid

# import unittest.mock


class SocketIO(io.RawIOBase):
    """ Use RawIOBase for buffering lines """

    def __init__(self, sock):
        self.sock = sock

    def read(self, sz=-1):
        if sz == -1:
            sz = 0x7FFFFFFF
        return self.sock.recv(sz)

    def seekable(self):
        return False

    def write(self, b):
        return self.sock.send(b)

    def close(self):
        return self.sock.close()

    def settimeout(self, timeout):
        return self.sock.settimeout(timeout)


class TestNabdBase(unittest.TestCase):
    def nabd_thread_loop(self):
        nabd_loop = asyncio.new_event_loop()
        nabd_loop.set_debug(True)
        asyncio.set_event_loop(nabd_loop)
        self.nabio = NabIOMock()
        self.nabd = nabd.Nabd(self.nabio)
        with self.nabd_cv:
            self.nabd_cv.notify()
        self.nabd.run()
        nabd_loop.close()
        close_old_connections()

    def setUp(self):
        self.nabd_cv = threading.Condition()
        with self.nabd_cv:
            self.nabd_thread = threading.Thread(target=self.nabd_thread_loop)
            self.nabd_thread.start()
            self.nabd_cv.wait()
        time.sleep(1)  # make sure Nabd was started

    def tearDown(self):
        self.nabd.stop()
        self.nabd_thread.join(10)
        if self.nabd_thread.is_alive():
            raise RuntimeError("nabd_thread still running")

    def test_init(self):
        self.assertEqual(self.nabio.left_ear, 0)
        self.assertEqual(self.nabio.right_ear, 0)
        self.assertEqual(self.nabio.left_led, None)
        self.assertEqual(self.nabio.center_led, None)
        self.assertEqual(self.nabio.right_led, None)
        self.assertEqual(self.nabio.bottom_led, "pulse((255, 0, 255))")
        self.assertEqual(self.nabio.nose_led, None)

    def service_socket(self):
        s = socket.socket()
        s.connect(("0.0.0.0", 10543))
        s.settimeout(5.0)
        return SocketIO(s)


class TestNabd(TestNabdBase):
    def test_state(self):
        s = self.service_socket()
        try:
            packet = s.readline()
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s.close()

    def test_sleep_wakeup(self):
        s1 = self.service_socket()
        s2 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = s2.readline()  # state packet
            s1.write(b'{"type":"sleep","request_id":"test_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "asleep")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "asleep")
            s1.write(b'{"type":"wakeup","request_id":"wakeup_request"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "wakeup_request")
            self.assertEqual(packet_j["status"], "ok")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()
            s2.close()

    def test_sleep_message_wakeup(self):
        s1 = self.service_socket()
        s2 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = s2.readline()  # state packet
            s1.write(b'{"type":"sleep","request_id":"test_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "asleep")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "asleep")
            s2.write(
                b'{"type":"command",'
                b'"request_id":"command_request_1","sequence":[]}\r\n'
            )
            s2.write(
                b'{"type":"command",'
                b'"request_id":"command_request_2","sequence":[]}\r\n'
            )
            s1.write(b'{"type":"wakeup","request_id":"wakeup_request"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "wakeup_request")
            self.assertEqual(packet_j["status"], "ok")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            time.sleep(3)  # give time to play sequence
            packet = s2.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "command_request_1")
            self.assertEqual(packet_j["status"], "ok")
            time.sleep(3)  # give time to play sequence
            packet = s2.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "command_request_2")
            self.assertEqual(packet_j["status"], "ok")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
            packet = s2.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()
            s2.close()

    def test_info_id_required(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            s1.write(b'{"type":"info","request_id":"test_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "error")
            self.assertEqual(packet_j["class"], "MalformedPacket")
        finally:
            s1.close()

    def test_info(self):
        s1 = self.service_socket()
        self.assertEqual(self.nabio.played_infos, [])
        try:
            packet = s1.readline()  # state packet
            # [25 {3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 0 0 0 0 0 0 0 0 0}] // soleil
            s1.write(
                b'{"type":"info",'
                b'"info_id":"weather","request_id":"test_id",'
                b'"animation":{"tempo":25,"colors":['
                b'{"left":"ffff00","center":"ffff00","right":"ffff00"},'
                b'{"left":"ffff00","center":"ffff00","right":"ffff00"},'
                b'{"left":"ffff00","center":"ffff00","right":"ffff00"},'
                b'{"left":"ffff00","center":"ffff00","right":"ffff00"},'
                b'{"left":"ffff00","center":"ffff00","right":"ffff00"},'
                b'{"left":"000000","center":"000000","right":"000000"},'
                b'{"left":"000000","center":"000000","right":"000000"},'
                b'{"left":"000000","center":"000000","right":"000000"}]}}'
                b"\r\n"
            )
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            time.sleep(10)  # give time to play info once
            self.assertNotEqual(self.nabio.played_infos, [])
            last_info = self.nabio.played_infos.pop()
            self.assertEqual(
                last_info,
                {
                    "tempo": 25,
                    "colors": [
                        {
                            "left": "ffff00",
                            "center": "ffff00",
                            "right": "ffff00",
                        },
                        {
                            "left": "ffff00",
                            "center": "ffff00",
                            "right": "ffff00",
                        },
                        {
                            "left": "ffff00",
                            "center": "ffff00",
                            "right": "ffff00",
                        },
                        {
                            "left": "ffff00",
                            "center": "ffff00",
                            "right": "ffff00",
                        },
                        {
                            "left": "ffff00",
                            "center": "ffff00",
                            "right": "ffff00",
                        },
                        {
                            "left": "000000",
                            "center": "000000",
                            "right": "000000",
                        },
                        {
                            "left": "000000",
                            "center": "000000",
                            "right": "000000",
                        },
                        {
                            "left": "000000",
                            "center": "000000",
                            "right": "000000",
                        },
                    ],
                },
            )
            # [25 {3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 0 0 0 0 0 0 0 0 0}] // soleil
            s1.write(
                b'{"type":"info","info_id":"weather",'
                b'"request_id":"clear_id"}\r\n'
            )
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "clear_id")
            self.assertEqual(packet_j["status"], "ok")
            time.sleep(20)  # make sure info is not played
            self.assertEqual(self.nabio.played_infos, [])
        finally:
            s1.close()

    def test_command(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            s1.write(
                b'{"type":"command","request_id":"test_id",'
                b'"sequence":[{"audio":['
                b'"weather/fr/signature.mp3","weather/fr/today.mp3",'
                b'"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                b'"weather/fr/temp/degree.mp3",'
                b'"weather/fr/temp/signature.mp3"],'
                b'"choregraphy":"streaming"}]}\r\n'
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            s1.settimeout(15.0)
            packet = s1.readline()  # response packet
            s1.settimeout(5.0)
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            last_sequence = self.nabio.played_sequences.pop()
            self.assertEqual(
                last_sequence,
                [
                    {
                        "audio": [
                            "weather/fr/signature.mp3",
                            "weather/fr/today.mp3",
                            "weather/fr/sky/0.mp3",
                            "weather/fr/temp/42.mp3",
                            "weather/fr/temp/degree.mp3",
                            "weather/fr/temp/signature.mp3",
                        ],
                        "choregraphy": "streaming",
                    }
                ],
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()

    def test_cancel(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            s1.write(
                b'{"type":"command","request_id":"test_id",'
                b'"sequence":[{"audio":['
                b'"weather/fr/signature.mp3","weather/fr/today.mp3",'
                b'"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                b'"weather/fr/temp/degree.mp3",'
                b'"weather/fr/temp/signature.mp3"],'
                b'"choregraphy":"streaming"}]}\r\n'
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            s1.write(b'{"type":"cancel","request_id":"test_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "canceled")
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()

    def test_cancel_wrong_request_id(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            s1.write(
                b'{"type":"command","request_id":"test_id",'
                b'"sequence":[{"audio":['
                b'"weather/fr/signature.mp3","weather/fr/today.mp3",'
                b'"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                b'"weather/fr/temp/degree.mp3",'
                b'"weather/fr/temp/signature.mp3"],'
                b'"choregraphy":"streaming"}]}\r\n'
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            s1.write(b'{"type":"cancel","request_id":"other_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "other_id")
            self.assertEqual(packet_j["status"], "error")
            s1.settimeout(15.0)
            packet = s1.readline()  # response packet
            s1.settimeout(5.0)
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            last_sequence = self.nabio.played_sequences.pop()
            self.assertEqual(
                last_sequence,
                [
                    {
                        "audio": [
                            "weather/fr/signature.mp3",
                            "weather/fr/today.mp3",
                            "weather/fr/sky/0.mp3",
                            "weather/fr/temp/42.mp3",
                            "weather/fr/temp/degree.mp3",
                            "weather/fr/temp/signature.mp3",
                        ],
                        "choregraphy": "streaming",
                    }
                ],
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()

    def test_cancel_not_cancelable(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            s1.write(
                b'{"type":"command","request_id":"test_id",'
                b'"sequence":[{"audio":['
                b'"weather/fr/signature.mp3","weather/fr/today.mp3",'
                b'"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                b'"weather/fr/temp/degree.mp3",'
                b'"weather/fr/temp/signature.mp3"],'
                b'"choregraphy":"streaming"}],'
                b'"cancelable":false}\r\n'
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
            s1.write(b'{"type":"cancel","request_id":"test_id"}\r\n')
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "error")
            s1.settimeout(15.0)
            packet = s1.readline()  # response packet
            s1.settimeout(5.0)
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "test_id")
            self.assertEqual(packet_j["status"], "ok")
            last_sequence = self.nabio.played_sequences.pop()
            self.assertEqual(
                last_sequence,
                [
                    {
                        "audio": [
                            "weather/fr/signature.mp3",
                            "weather/fr/today.mp3",
                            "weather/fr/sky/0.mp3",
                            "weather/fr/temp/42.mp3",
                            "weather/fr/temp/degree.mp3",
                            "weather/fr/temp/signature.mp3",
                        ],
                        "choregraphy": "streaming",
                    }
                ],
            )
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "idle")
        finally:
            s1.close()

    def test_expiration_not_expired(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            now = datetime.datetime.now()
            expiration = now + datetime.timedelta(minutes=3)
            packet = (
                '{"type":"command","request_id":"test_id",'
                '"sequence":[{"audio":['
                '"weather/fr/signature.mp3","weather/fr/today.mp3",'
                '"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                '"weather/fr/temp/degree.mp3",'
                '"weather/fr/temp/signature.mp3"],'
                '"choregraphy":"streaming"}],'
                '"expiration":"' + expiration.isoformat() + '"}\r\n'
            )
            s1.write(packet.encode("utf8"))
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "state")
            self.assertEqual(packet_j["state"], "playing")
        finally:
            s1.close()

    def test_expiration_expired(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            now = datetime.datetime.now()
            expiration = now + datetime.timedelta(minutes=-1)
            packet = (
                '{"type":"command","request_id":"test_id",'
                '"sequence":[{"audio":['
                '"weather/fr/signature.mp3","weather/fr/today.mp3",'
                '"weather/fr/sky/0.mp3","weather/fr/temp/42.mp3",'
                '"weather/fr/temp/degree.mp3",'
                '"weather/fr/temp/signature.mp3"],'
                '"choregraphy":"streaming"}],'
                '"expiration":"' + expiration.isoformat() + '"}\r\n'
            )
            s1.write(packet.encode("utf8"))
            packet = s1.readline()  # new state packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["status"], "expired")
        finally:
            s1.close()

    def test_shutdown_api_method(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = (
                '{"type":"shutdown",'
                '"mode":"reboot",'
                '"request_id":"shutdown"}\r\n'
            )
            s1.write(packet.encode("utf8"))
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "shutdown")
            time.sleep(1)
            nabio = self.nabd.nabio
            self.assertEqual(len(nabio.called_list), 1)
            ear_pos = self.nabd.SLEEP_EAR_POSITION
            self.assertEqual(
                nabio.called_list[0], f"move_ears({ear_pos}, {ear_pos})",
            )
            self.assertEqual(nabio.left_led, (255, 0, 255))
            self.assertEqual(nabio.center_led, (255, 0, 255))
            self.assertEqual(nabio.right_led, (255, 0, 255))
            self.assertEqual(nabio.nose_led, (255, 0, 255))
            self.assertEqual(nabio.bottom_led, (255, 0, 255))
        finally:
            s1.close()


@pytest.mark.django_db(transaction=True)
class TestRfid(TestNabdBase):
    def tearDown(self):
        TestNabdBase.tearDown(self)
        close_old_async_connections()

    def test_detect_clear_rfid(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = (
                '{"type":"mode","request_id":"mode_id",'
                '"mode":"interactive",'
                '"events":["rfid/*"]}\r\n'
            )
            s1.write(packet.encode("utf8"))
            # state & response packets
            packet1 = s1.readline()
            packet2 = s1.readline()
            packet_j1 = json.loads(packet1.decode("utf8"))
            packet_j2 = json.loads(packet2.decode("utf8"))
            if packet_j1["type"] == "state":
                state_packet_j = packet_j1
                mode_packet_j = packet_j2
            else:
                state_packet_j = packet_j2
                mode_packet_j = packet_j1
            self.assertEqual(state_packet_j["type"], "state")
            self.assertEqual(state_packet_j["state"], "interactive")
            self.assertEqual(mode_packet_j["type"], "response")
            self.assertEqual(mode_packet_j["request_id"], "mode_id")
            rfid = self.nabd.nabio.rfid
            rfid.send_detect_event(
                b"\xd0\x02\x18\x01\x02\x03\x04\x05",
                None,
                None,
                None,
                TagFlags.CLEAR,
            )
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "rfid_event")
            self.assertEqual(packet_j["event"], "detected")
            self.assertEqual(packet_j["uid"], "d0:02:18:01:02:03:04:05")
        finally:
            s1.close()

    def test_detect_taichi_rfid(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = (
                '{"type":"mode","request_id":"mode_id",'
                '"mode":"idle",'
                '"events":["rfid/nabtaichid"]}\r\n'
            )
            s1.write(packet.encode("utf8"))
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "mode_id")
            rfid = self.nabd.nabio.rfid
            rfid.send_detect_event(
                b"\xd0\x02\x18\x01\x02\x03\x04\x05",
                42,
                nabtaichid.NABAZTAG_RFID_APPLICATION_ID,
                b"",
                TagFlags.FORMATTED,
            )
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "rfid_event")
            self.assertEqual(packet_j["event"], "detected")
            self.assertEqual(packet_j["app"], "nabtaichid")
            self.assertEqual(packet_j["uid"], "d0:02:18:01:02:03:04:05")
            self.assertEqual(packet_j["picture"], 42)
        finally:
            s1.close()

    def test_write_rfid(self):
        s1 = self.service_socket()
        try:
            packet = s1.readline()  # state packet
            packet = (
                '{"type":"rfid_write",'
                '"uid":"d0:02:18:01:02:03:04:05",'
                '"picture":42,'
                '"app":"nabtaichid",'
                '"data":"",'
                '"request_id":"rfid_write_id"}\r\n'
            )
            s1.write(packet.encode("utf8"))
            packet = s1.readline()  # response packet
            packet_j = json.loads(packet.decode("utf8"))
            self.assertEqual(packet_j["type"], "response")
            self.assertEqual(packet_j["request_id"], "rfid_write_id")
            rfid = self.nabd.nabio.rfid
            self.assertEqual(len(rfid.called_list), 2)
            self.assertEqual(rfid.called_list[0], "on_detect()")
            self.assertEqual(
                rfid.called_list[1],
                f"write(b'\\xd0\\x02\\x18\\x01\\x02\\x03\\x04\\x05',"
                f"42,{nabtaichid.NABAZTAG_RFID_APPLICATION_ID},b'')",
            )
        finally:
            s1.close()
