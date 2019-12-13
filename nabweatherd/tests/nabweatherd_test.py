import unittest
import asyncio
import threading
import json
import django
import time
import datetime
import signal
import pytest
from nabweatherd.nabweatherd import NabWeatherd


class MockWriter(object):
    def __init__(self):
        self.written = []

    def write(self, packet):
        self.written.append(packet)


@pytest.mark.django_db
class TestNabWeatherd(unittest.TestCase):
    def test_fetch_info_data(self):
        service = NabWeatherd()
        data = service.fetch_info_data(("75005", NabWeatherd.UNIT_CELSIUS))
        self.assertTrue("current_weather_class" in data)
        self.assertTrue("today_forecast_weather_class" in data)
        self.assertTrue("today_forecast_max_temp" in data)
        self.assertTrue("tomorrow_forecast_weather_class" in data)
        self.assertTrue("tomorrow_forecast_max_temp" in data)

    def test_perform(self):
        service = NabWeatherd()
        writer = MockWriter()
        service.writer = writer
        config_t = ("75005", NabWeatherd.UNIT_CELSIUS)
        expiration = datetime.datetime(2019, 4, 22, 0, 0, 0)
        service.perform(expiration, "today", config_t)
        self.assertEqual(len(writer.written), 2)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "info")
        self.assertEqual(packet_json["info_id"], "nabweatherd")
        self.assertTrue("animation" in packet_json)
        packet = writer.written[1]
        packet_json = json.loads(packet.decode("utf8"))
        self.assertEqual(packet_json["type"], "message")
        self.assertTrue("signature" in packet_json)
        self.assertTrue("body" in packet_json)

    def test_aliases(self):
        service = NabWeatherd()
        weather_class = service.normalize_weather_class("J_W1_0-N_4")
        self.assertEqual(weather_class, "J_W1_0-N_1")
        weather_class = service.normalize_weather_class("J_W1_0-N_1")
        self.assertEqual(weather_class, "J_W1_0-N_1")
        weather_class = service.normalize_weather_class("J_W2_4-N_1")
        self.assertEqual(weather_class, "J_W1_3-N_0")
