import unittest
import json
import django
import time
import datetime
import pytest
from asgiref.sync import async_to_sync
from nabairqualityd.nabairqualityd import NabAirqualityd
from nabairqualityd import models
from nabd.tests.utils import close_old_async_connections
from nabd.tests.mock import MockWriter, NabdMockTestCase


@pytest.mark.django_db(transaction=True)
class TestNabAirqualityd(unittest.TestCase):
    def tearDown(self):
        close_old_async_connections()

    def test_fetch_info_data(self):
        config = models.Config.load()
        config.index_airquality = "aqi"
        config.visual_airquality = "always"
        config.localisation = None
        config.save()
        service = NabAirqualityd()
        info_data = async_to_sync(service.fetch_info_data)(("aqi", "always"))
        config = models.Config.load()
        self.assertIsNotNone(info_data)
        self.assertTrue("data" in info_data)   
        self.assertTrue(info_data["data"] < 4)
        self.assertTrue(info_data["data"] >= 0)
        self.assertIsNotNone(config.localisation)

    def test_perform(self):
        config = models.Config.load()
        config.index_airquality = "aqi"
        config.visual_airquality = "always"
        config.localisation = None
        config.save()
        service = NabAirqualityd()
        writer = MockWriter()
        service.writer = writer
        config_t = ("aqi", "always")
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        async_to_sync(service.perform)(expiration, "today", config_t)
        self.assertEqual(len(writer.written), 2)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabairqualityd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)

    def test_asr(self):
        config = models.Config.load()
        config.index_airquality = "aqi"
        config.visual_airquality = "always"
        config.localisation = None
        config.save()
        service = NabAirqualityd()
        writer = MockWriter()
        service.writer = writer
        config_t = "aqi"
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        packet = {
            "type": "asr_event",
            "nlu": {"intent": "nabairqualityd/forecast"},
        }
        async_to_sync(service.process_nabd_packet)(packet)
        print(writer.written)
        self.assertEqual(len(writer.written), 2)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabairqualityd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)


@pytest.mark.django_db
class TestNabAirqualitydRun(NabdMockTestCase):
    def tearDown(self):
        NabdMockTestCase.tearDown(self)
        close_old_async_connections()

    def test_connect(self):
        self.do_test_connect(NabAirqualityd)
