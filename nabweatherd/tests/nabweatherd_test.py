import unittest
import json
import django
import time
import datetime
import pytest
from asgiref.sync import async_to_sync
from nabweatherd.nabweatherd import NabWeatherd
from nabweatherd import models
from nabweatherd import rfid_data
from nabd.tests.utils import close_old_async_connections
from nabd.tests.mock import MockWriter, NabdMockTestCase


class TestNabWeatherd(unittest.TestCase):
    def test_aliases(self):
        service = NabWeatherd()
        weather_class = service.normalize_weather_class("Pluie forte")
        self.assertEqual(weather_class, "Pluie forte")
        weather_class = service.normalize_weather_class("None")
        self.assertEqual(weather_class, None)


@pytest.mark.django_db(transaction=True)
class TestNabWeatherdDB(unittest.TestCase):
    RENNES_LOCATION_JSON = '{"insee":"35238","name":"Rennes","lat":48.11417,"lon":-1.68083,"country":"FR","admin":"Bretagne","admin2":"35","postCode":"35000"}'

    def tearDown(self):
        close_old_async_connections()

    def test_fetch_info_data(self):
        service = NabWeatherd()

        data = async_to_sync(service.fetch_info_data)(
            (
                TestNabWeatherdDB.RENNES_LOCATION_JSON,
                NabWeatherd.UNIT_CELSIUS,
                "weather_and_rain",
                3,
                None,
                False,
            )
        )
        self.assertTrue("current_weather_class" in data)
        self.assertTrue("today_forecast_weather_class" in data)
        self.assertTrue("today_forecast_max_temp" in data)
        self.assertTrue("tomorrow_forecast_weather_class" in data)
        self.assertTrue("tomorrow_forecast_max_temp" in data)
        self.assertTrue("next_rain" in data)
        self.assertTrue("weather_animation_type" in data)

    def test_perform_both(self):
        service = NabWeatherd()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION_JSON,
            NabWeatherd.UNIT_CELSIUS,
            "weather_and_rain",
            3,
            None,
            False,
        )
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        async_to_sync(service.perform)(expiration, "today", config_t)
        self.assertEqual(len(writer.written), 3)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd_rain")
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[2]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)

    def test_perform_rain(self):
        service = NabWeatherd()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION_JSON,
            NabWeatherd.UNIT_CELSIUS,
            "rain_only",
            3,
            None,
            False,
        )
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        async_to_sync(service.perform)(expiration, "today", config_t)
        self.assertEqual(len(writer.written), 3)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd_rain")
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd")
        self.assertFalse("animation" in packet_json)
        packet = writer.written[2]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)

    def test_perform(self):
        service = NabWeatherd()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION_JSON,
            NabWeatherd.UNIT_CELSIUS,
            "weather_only",
            3,
            None,
            False,
        )
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        async_to_sync(service.perform)(expiration, "today", config_t)
        self.assertEqual(len(writer.written), 3)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd_rain")
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[2]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)

    def test_asr(self):
        config = models.Config.load()
        config.location = TestNabWeatherdDB.RENNES_LOCATION_JSON
        config.unit = NabWeatherd.UNIT_CELSIUS
        config.weather_animation_type = "weather_only"
        config.save()
        service = NabWeatherd()
        writer = MockWriter()
        service.writer = writer
        packet = {
            "type": "asr_event",
            "nlu": {"intent": "nabweatherd/forecast"},
        }
        async_to_sync(service.process_nabd_packet)(packet)
        self.assertEqual(len(writer.written), 3)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd_rain")
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[2]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)


class TestRFIDData(unittest.TestCase):
    def test_serialize(self):
        self.assertEqual(b"\x01", rfid_data.serialize("today"))
        self.assertEqual(b"\x02", rfid_data.serialize("tomorrow"))
        self.assertEqual(b"\x01", rfid_data.serialize("unknown"))

    def test_unserialize(self):
        self.assertEqual("today", rfid_data.unserialize(b"\x01"))
        self.assertEqual("tomorrow", rfid_data.unserialize(b"\x02"))
        self.assertEqual("today", rfid_data.unserialize(b""))
        self.assertEqual("today", rfid_data.unserialize(b"unknown"))


@pytest.mark.django_db
class TestNabWeatherdRun(NabdMockTestCase):
    def tearDown(self):
        NabdMockTestCase.tearDown(self)
        close_old_async_connections()

    def test_connect(self):
        self.do_test_connect(NabWeatherd)
