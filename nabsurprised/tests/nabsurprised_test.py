import unittest
import threading
import json
import django
import time
import datetime
import signal
import pytest
from asgiref.sync import async_to_sync
from nabsurprised.nabsurprised import NabSurprised
from nabd.tests.utils import close_old_async_connections
from nabd.tests.mock import MockWriter, NabdMockTestCase


@pytest.mark.django_db
class TestNabSurprised(unittest.TestCase):
    def tearDown(self):
        close_old_async_connections()

    def test_perform(self):
        service = NabSurprised()
        writer = MockWriter()
        service.writer = writer
        expiration = datetime.datetime(2018, 11, 1, 0, 0, 0)
        async_to_sync(service.perform)(expiration, None, None)
        self.assertEqual(len(writer.written), 1)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)


@pytest.mark.django_db
class TestRfid(unittest.TestCase):
    def tearDown(self):
        close_old_async_connections()

    def test_detect_language(self):
        service = NabSurprised()
        writer = MockWriter()
        service.writer = writer
        expiration = datetime.datetime(2018, 11, 1, 0, 0, 0)
        nabd_packet = {
            "type": "rfid_event",
            "uid": "d0:02:1a:01:02:03:04:05",
            "event": "detected",
            "support": "formatted",
            "picture": 21,
            "app": "nabsurprised",
            "data": "\x07\x00",
        }
        async_to_sync(service.process_nabd_packet)(nabd_packet)
        self.assertEqual(len(writer.written), 1)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)
        self.assertEqual(len(packet_json["body"]), 1)
        self.assertTrue("audio" in packet_json["body"][0])
        self.assertEqual(len(packet_json["body"][0]["audio"]), 1)
        self.assertEqual(
            packet_json["body"][0]["audio"][0], "ja_JP/nabsurprised/*.mp3"
        )

    def test_detect_surprise(self):
        service = NabSurprised()
        writer = MockWriter()
        service.writer = writer
        expiration = datetime.datetime(2018, 11, 1, 0, 0, 0)
        nabd_packet = {
            "type": "rfid_event",
            "uid": "d0:02:1a:01:02:03:04:05",
            "event": "detected",
            "support": "formatted",
            "picture": 21,
            "app": "nabsurprised",
            "data": "\x00\x01",
        }
        async_to_sync(service.process_nabd_packet)(nabd_packet)
        self.assertEqual(len(writer.written), 1)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)
        self.assertEqual(len(packet_json["body"]), 1)
        self.assertTrue("audio" in packet_json["body"][0])
        self.assertEqual(len(packet_json["body"][0]["audio"]), 1)
        self.assertEqual(
            packet_json["body"][0]["audio"][0], "nabsurprised/carrot/*.mp3"
        )


@pytest.mark.django_db
class TestNabSurprisedRun(NabdMockTestCase):
    def tearDown(self):
        NabdMockTestCase.tearDown(self)
        close_old_async_connections()

    def test_connect(self):
        self.do_test_connect(NabSurprised)
