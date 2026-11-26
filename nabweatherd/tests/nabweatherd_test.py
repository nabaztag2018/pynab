import datetime
import json
import unittest

import pytest
from asgiref.sync import async_to_sync

from nabd.tests.mock import MockWriter, NabdMockTestCase
from nabd.tests.utils import close_old_async_connections
from nabweatherd import models, rfid_data
from nabweatherd.nabweatherd import NabWeatherd


def get_nabweatherd_instance(**kwargs):
    object = NabWeatherd()
    object.get_system_tz = lambda: "Europe/Paris"
    return object


class TestNabWeatherd(unittest.TestCase):
    def test_aliases(self):
        service = get_nabweatherd_instance()
        weather_class = service.normalize_weather_class("Pluie forte")
        self.assertEqual(weather_class, "Pluie forte")
        weather_class = service.normalize_weather_class("None")
        self.assertEqual(weather_class, None)

    def test_hail_storm_spellings(self):
        # Météo-France sends both the singular and the plural (PR #492)
        service = get_nabweatherd_instance()
        for desc in ("Orage avec grêle", "Orages avec grêle"):
            self.assertEqual(service.normalize_weather_class(desc), desc)

    UNKNOWN_CLASS_DATA = {
        "weather_animation_type": "weather_only",
        "current_weather_class": None,
        "next_rain": False,
        "today_forecast_weather_class": None,
        "today_forecast_max_temp": 12,
        "tomorrow_forecast_weather_class": None,
        "tomorrow_forecast_max_temp": 14,
    }

    def test_unknown_class_has_no_animation(self):
        # An unknown description (e.g. in English, issue #371) used to raise
        # KeyError: None. The weather animation is skipped instead.
        service = get_nabweatherd_instance()
        service.writer = MockWriter()
        for animation_type in ("weather_only", "weather_and_rain"):
            info_data = dict(
                self.UNKNOWN_CLASS_DATA, weather_animation_type=animation_type
            )
            self.assertIsNone(service.get_animation(info_data))

    def test_unknown_class_says_nothing(self):
        service = get_nabweatherd_instance()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION,
            NabWeatherd.UNIT_CELSIUS,
            "weather_only",
            3,
            None,
            False,
        )
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        for forecast in ("today", "tomorrow"):
            async_to_sync(service.perform_additional)(
                expiration, forecast, self.UNKNOWN_CLASS_DATA, config_t
            )
        self.assertEqual(writer.written, [])


@pytest.mark.django_db(transaction=True)
class TestNabWeatherdDB(unittest.TestCase):
    RENNES_LOCATION = dict(
        insee="35238",
        name="Rennes",
        lat=48.11417,
        lon=-1.68083,
        country="FR",
        admin="Bretagne",
        admin2="35",
        postCode="35000",
    )

    def tearDown(self):
        close_old_async_connections()

    def test_fetch_info_data(self):
        service = get_nabweatherd_instance()

        data = async_to_sync(service.fetch_info_data)(
            (
                TestNabWeatherdDB.RENNES_LOCATION,
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
        service = get_nabweatherd_instance()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION,
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
        service = get_nabweatherd_instance()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION,
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
        service = get_nabweatherd_instance()
        writer = MockWriter()
        service.writer = writer
        config_t = (
            TestNabWeatherdDB.RENNES_LOCATION,
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
        config.location = TestNabWeatherdDB.RENNES_LOCATION
        config.unit = NabWeatherd.UNIT_CELSIUS
        config.weather_animation_type = "weather_only"
        config.save()
        service = get_nabweatherd_instance()
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
