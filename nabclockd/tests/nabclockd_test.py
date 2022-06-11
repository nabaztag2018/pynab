import asyncio
import datetime
import json
import os
import time
from functools import partial
from threading import Thread

import pytest
from dateutil import tz
from django.db import close_old_connections

from nabclockd import models, nabclockd, rfid_data
from nabd.tests.mock import NabdMockTestCase
from nabd.tests.utils import close_old_async_connections


@pytest.mark.django_db(transaction=True)
class TestNabclockd(NabdMockTestCase):
    def tearDown(self):
        NabdMockTestCase.tearDown(self)
        close_old_async_connections()
        close_old_connections()

    def get_system_tz(self):
        return "Europe/Paris"

    def synchronized_since_boot(self):
        return True

    def create_service(self):
        service = nabclockd.NabClockd.__new__(nabclockd.NabClockd)
        service.get_system_tz = self.get_system_tz
        service.synchronized_since_boot = self.synchronized_since_boot
        service.__init__()
        return service

    async def connect_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        self.connect_handler_called += 1

    def test_connect(self):
        self.mock_connection_handler = self.connect_handler
        self.connect_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = self.create_service()
        service.run()
        self.assertEqual(self.connect_handler_called, 1)

    async def wakeup_handler(self, reader, writer):
        await self.wakeup_sleep_handler("asleep", reader, writer)

    async def sleep_handler(self, reader, writer):
        await self.wakeup_sleep_handler("idle", reader, writer)

    async def wakeup_sleep_handler(self, state, reader, writer):
        packet = f'{{"type":"state","state":"{state}"}}\r\n'
        await self.packets_handler(state, [packet], reader, writer)

    async def packets_handler(self, state, packets, reader, writer):
        self.packets_handler_called += 1
        if len(packets) > 0:
            if packets[0]:
                writer.write(packets[0].encode("utf8"))
            packets = packets[1:]
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                if "type" in packet:
                    if packet["type"] == "sleep" and state != "asleep":
                        state = "asleep"
                        new_state_p = '{"type":"state","state":"asleep"}\r\n'
                        writer.write(new_state_p.encode("utf8"))
                    if packet["type"] == "wakeup" and state != "idle":
                        state = "idle"
                        new_state_p = '{"type":"state","state":"idle"}\r\n'
                        writer.write(new_state_p.encode("utf8"))
                self.received_packets.append(packet)
                if len(packets) > 0:
                    if packets[0]:
                        writer.write(packets[0].encode("utf8"))
                    packets = packets[1:]

    def _do_update_wakeup_hours(self):
        time.sleep(1)
        config = models.Config.load()
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        if not config.settings_per_day:
            config.wakeup_hour = now.hour - 2
            if config.wakeup_hour < 0:
                config.wakeup_hour += 24
            config.wakeup_min = 0
            config.sleep_hour = now.hour + 2
            if config.sleep_hour >= 24:
                config.sleep_hour -= 24
            config.sleep_min = 0
        else:
            wakeup_hour = now.hour - 2
            if wakeup_hour < 0:
                wakeup_hour += 24
            wakeup_min = 0
            sleep_hour = now.hour + 2
            if sleep_hour >= 24:
                sleep_hour -= 24
            sleep_min = 0
            curDateValue = datetime.datetime.now() + datetime.timedelta(
                hours=-3
            )
            dayOfTheWeek = curDateValue.strftime("%A").lower()
            setattr(config, "wakeup_hour_" + dayOfTheWeek, wakeup_hour)
            setattr(config, "wakeup_min_" + dayOfTheWeek, wakeup_min)
            setattr(config, "sleep_hour_" + dayOfTheWeek, sleep_hour)
            setattr(config, "sleep_min_" + dayOfTheWeek, sleep_min)
        config.save()
        close_old_connections()

    def _update_wakeup_hours(self, service):
        this_loop = asyncio.get_event_loop()
        thread = Thread(target=self._do_update_wakeup_hours)
        thread.start()
        thread.join()
        this_loop.create_task(service.reload_config())
        this_loop.call_later(1, lambda: this_loop.stop())

    def test_wakeup(self):
        self.mock_connection_handler = self.wakeup_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 3:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "message")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 3)

    def test_wakeup_perday(self):
        self.mock_connection_handler = self.wakeup_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = True
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        wakeup_hour = now.hour + 2
        if wakeup_hour >= 24:
            wakeup_hour -= 24
        wakeup_min = 0
        sleep_hour = now.hour - 2
        if sleep_hour < 0:
            sleep_hour += 24
        sleep_min = 0
        curDateValue = datetime.datetime.now() + datetime.timedelta(hours=-3)
        dayOfTheWeek = curDateValue.strftime("%A").lower()
        setattr(config, "wakeup_hour_" + dayOfTheWeek, wakeup_hour)
        setattr(config, "wakeup_min_" + dayOfTheWeek, wakeup_min)
        setattr(config, "sleep_hour_" + dayOfTheWeek, sleep_hour)
        setattr(config, "sleep_min_" + dayOfTheWeek, sleep_min)
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 3:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "message")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 3)

    def test_sleep(self):
        self.mock_connection_handler = self.sleep_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = False
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 2:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertEqual(len(self.received_packets), 2)

    def test_sleep_perday(self):
        self.mock_connection_handler = self.sleep_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = True
        config.play_wakeup_sleep_sounds = False
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        wakeup_hour = now.hour + 2
        if wakeup_hour >= 24:
            wakeup_hour -= 24
        wakeup_min = 0
        sleep_hour = now.hour - 2
        if sleep_hour < 0:
            sleep_hour += 24
        sleep_min = 0
        curDateValue = datetime.datetime.now() + datetime.timedelta(hours=-3)
        dayOfTheWeek = curDateValue.strftime("%A").lower()
        setattr(config, "wakeup_hour_" + dayOfTheWeek, wakeup_hour)
        setattr(config, "wakeup_min_" + dayOfTheWeek, wakeup_min)
        setattr(config, "sleep_hour_" + dayOfTheWeek, sleep_hour)
        setattr(config, "sleep_min_" + dayOfTheWeek, sleep_min)
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 2:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertEqual(len(self.received_packets), 2)

    def test_sleep_wakeup(self):
        self.mock_connection_handler = self.sleep_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = False
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 3:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 3)

    def test_sleep_wakeup_perday(self):
        self.mock_connection_handler = self.sleep_handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = False
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.settings_per_day = True
        wakeup_hour = now.hour + 2
        if wakeup_hour >= 24:
            wakeup_hour -= 24
        wakeup_min = 0
        sleep_hour = now.hour - 2
        if sleep_hour < 0:
            sleep_hour += 24
        sleep_min = 0
        curDateValue = datetime.datetime.now() + datetime.timedelta(hours=-3)
        dayOfTheWeek = curDateValue.strftime("%A").lower()
        setattr(config, "wakeup_hour_" + dayOfTheWeek, wakeup_hour)
        setattr(config, "wakeup_min_" + dayOfTheWeek, wakeup_min)
        setattr(config, "sleep_hour_" + dayOfTheWeek, sleep_hour)
        setattr(config, "sleep_min_" + dayOfTheWeek, sleep_min)
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 3:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 3)

    def test_clock_response(self):
        service = self.create_service()
        config = models.Config.load()
        config.wakeup_hour = 7
        config.wakeup_min = 0
        config.sleep_hour = 22
        config.sleep_min = 0
        config.chime_hour = True
        config.save()
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        reload_task = this_loop.create_task(service.reload_config())
        this_loop.run_until_complete(reload_task)
        service.asleep = True
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 0, 0, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 30, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 1, 0, tzinfo=tz.gettz())
            ),
            ["wakeup"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 6, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "reset_last_chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 22, 0, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 23, 0, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        service.asleep = False
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 0, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 0, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 30, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 1, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 6, 0, tzinfo=tz.gettz())
            ),
            ["reset_last_chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 22, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 23, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        config.wakeup_hour = 22
        config.wakeup_min = 0
        config.sleep_hour = 7
        config.sleep_min = 0
        config.chime_hour = True
        config.save()
        reload_task = this_loop.create_task(service.reload_config())
        this_loop.run_until_complete(reload_task)
        service.asleep = True
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 0, 0, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 1, 0, 30, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 1, 6, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "reset_last_chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 1, 0, tzinfo=tz.gettz())
            ),
            [],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 22, 0, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 23, 0, 0, tzinfo=tz.gettz())
            ),
            ["wakeup", "chime"],
        )
        service.asleep = False
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 0, 0, 0, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 1, 0, 30, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 1, 6, 0, tzinfo=tz.gettz())
            ),
            ["reset_last_chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 8, 1, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 22, 0, 0, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 23, 0, 0, tzinfo=tz.gettz())
            ),
            ["chime"],
        )
        config.sleep_wakeup_override = True
        config.save()
        reload_task = this_loop.create_task(service.reload_config())
        this_loop.run_until_complete(reload_task)
        service.asleep = True
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            ["clear_override"],
        )
        service.asleep = False
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 7, 0, 0, tzinfo=tz.gettz())
            ),
            ["clear_override", "sleep"],
        )
        self.assertEqual(
            service.clock_response(
                datetime.datetime(2018, 11, 2, 22, 0, 0, tzinfo=tz.gettz())
            ),
            ["sleep"],
        )

    def test_sleep_tag_override(self):
        sleep_data = rfid_data.serialize("sleep").decode("utf8")
        packets = [
            '{"type":"state","state":"idle"}\r\n',
            json.dumps(
                dict(
                    type="rfid_event",
                    event="detected",
                    app="nabclockd",
                    data=sleep_data,
                )
            )
            + "\r\n",
        ]
        handler = partial(self.packets_handler, "idle", packets)
        self.mock_connection_handler = handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour - 2
        if config.wakeup_hour < 0:
            config.wakeup_hour += 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour + 2
        if config.sleep_hour >= 24:
            config.sleep_hour -= 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 2:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertEqual(self.received_packets[0]["mode"], "idle")
        self.assertTrue("button" in self.received_packets[0]["events"])
        self.assertTrue("asr/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("rfid/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertEqual(len(self.received_packets), 2)

    def test_asr_sleep(self):
        packets = [
            '{"type":"state","state":"idle"}\r\n',
            '{"type":"asr_event","nlu":{"intent":"nabclockd/sleep"}}\r\n',
        ]
        handler = partial(self.packets_handler, "idle", packets)
        self.mock_connection_handler = handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour - 2
        if config.wakeup_hour < 0:
            config.wakeup_hour += 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour + 2
        if config.sleep_hour >= 24:
            config.sleep_hour -= 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 2:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertEqual(self.received_packets[0]["mode"], "idle")
        self.assertTrue("button" in self.received_packets[0]["events"])
        self.assertTrue("asr/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("rfid/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertEqual(len(self.received_packets), 2)

    def test_wakeup_tag_override(self):
        wakeup_data = rfid_data.serialize("wakeup").decode("utf8")
        packets = [
            '{"type":"state","state":"idle"}\r\n',
            None,
            json.dumps(
                dict(
                    type="rfid_event",
                    event="detected",
                    app="nabclockd",
                    data=wakeup_data,
                )
            )
            + "\r\n",
        ]
        handler = partial(self.packets_handler, "idle", packets)
        self.mock_connection_handler = handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 4:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertEqual(self.received_packets[0]["mode"], "idle")
        self.assertTrue("button" in self.received_packets[0]["events"])
        self.assertTrue("asr/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("rfid/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "message")
        self.assertEqual(
            self.received_packets[2]["body"][0]["audio"][0], "wakeup/*.mp3"
        )
        self.assertTrue("type" in self.received_packets[3])
        self.assertEqual(self.received_packets[3]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 4)

    def test_wakeup_button_override(self):
        packets = [
            '{"type":"state","state":"idle"}\r\n',
            None,
            '{"type":"button_event","event":"click"}\r\n',
        ]
        handler = partial(self.packets_handler, "idle", packets)
        self.mock_connection_handler = handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.chime_hour = False
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 4:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertEqual(self.received_packets[0]["mode"], "idle")
        self.assertTrue("button" in self.received_packets[0]["events"])
        self.assertTrue("asr/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("rfid/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertTrue("type" in self.received_packets[2])
        self.assertEqual(self.received_packets[2]["type"], "message")
        self.assertEqual(
            self.received_packets[2]["body"][0]["audio"][0], "wakeup/*.mp3"
        )
        self.assertTrue("type" in self.received_packets[3])
        self.assertEqual(self.received_packets[3]["type"], "wakeup")
        self.assertEqual(len(self.received_packets), 4)

    def test_start_with_sleep_override(self):
        packets = [
            '{"type":"state","state":"idle"}\r\n',
        ]
        handler = partial(self.packets_handler, "idle", packets)
        self.mock_connection_handler = handler
        self.received_packets = []
        self.packets_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        config.settings_per_day = False
        config.play_wakeup_sleep_sounds = True
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        config.wakeup_hour = now.hour - 2
        if config.wakeup_hour < 0:
            config.wakeup_hour += 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour + 2
        if config.sleep_hour >= 24:
            config.sleep_hour -= 24
        config.sleep_min = 0
        config.sleep_wakeup_override = True
        config.save()
        service = self.create_service()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.packets_handler_called, 1)
        if len(self.received_packets) != 2:
            print(self.received_packets)
        self.assertTrue("type" in self.received_packets[0])
        self.assertEqual(self.received_packets[0]["type"], "mode")
        self.assertEqual(self.received_packets[0]["mode"], "idle")
        self.assertTrue("button" in self.received_packets[0]["events"])
        self.assertTrue("asr/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("rfid/nabclockd" in self.received_packets[0]["events"])
        self.assertTrue("type" in self.received_packets[1])
        self.assertEqual(self.received_packets[1]["type"], "sleep")
        self.assertEqual(len(self.received_packets), 2)


@pytest.mark.skipif(
    not os.path.isfile("/etc/timezone")
    or not os.path.isfile("/run/systemd/timesync/synchronized"),
    reason=(
        "Test requires /etc/timezone & "
        "/run/systemd/timesync/synchronized to exist"
    ),
)
@pytest.mark.django_db(transaction=True)
class TestNabclockdLinux(NabdMockTestCase):
    def tearDown(self):
        NabdMockTestCase.tearDown(self)
        close_old_async_connections()
        close_old_connections()

    def create_service(self):
        return nabclockd.NabClockd()

    async def connect_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        self.connect_handler_called += 1

    def test_connect(self):
        self.mock_connection_handler = self.connect_handler
        self.connect_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = self.create_service()
        service.run()
        self.assertEqual(self.connect_handler_called, 1)
