import unittest
import asyncio
from threading import Thread
import json
import django
import time
import datetime
import signal
import pytest
import os
from dateutil import tz
from nabclockd import nabclockd, models
from nabcommon import nabservice
from nabd.tests.utils import close_old_connections


@pytest.mark.skipif(
    not os.path.isfile("/etc/timezone"),
    reason="Test requires /etc/timezone to exist",
)
@pytest.mark.django_db(transaction=True)
class TestNabclockd(unittest.TestCase):
    def tearDown(self):
        close_old_connections()

    async def mock_nabd_service_handler(self, reader, writer):
        self.service_writer = writer
        if self.mock_connection_handler:
            await self.mock_connection_handler(reader, writer)

    def mock_nabd_thread_entry_point(self):
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
        self.mock_nabd_thread = Thread(
            target=self.mock_nabd_thread_entry_point
        )
        self.mock_nabd_thread.start()
        time.sleep(1)

    def tearDown(self):
        self.mock_nabd_loop.call_soon_threadsafe(
            lambda: self.mock_nabd_loop.stop()
        )
        self.mock_nabd_thread.join(3)

    async def connect_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        self.connect_handler_called += 1

    def test_connect(self):
        self.mock_connection_handler = self.connect_handler
        self.connect_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = nabclockd.NabClockd()
        service.run()
        self.assertEqual(self.connect_handler_called, 1)

    async def wakeup_handler(self, reader, writer):
        await self.wakeup_sleep_handler("asleep", reader, writer)

    async def sleep_handler(self, reader, writer):
        await self.wakeup_sleep_handler("idle", reader, writer)

    async def wakeup_sleep_handler(self, state, reader, writer):
        packet = f'{{"type":"state","state":"{state}"}}\r\n'
        writer.write(packet.encode("utf8"))
        self.wakeup_handler_called += 1
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                if "type" in packet:
                    if packet["type"] == "sleep" and state != "asleep":
                        state = "asleep"
                        new_state_p = (
                            f'{{"type":"state","state":"asleep"}}\r\n'
                        )
                        writer.write(new_state_p.encode("utf8"))
                    if packet["type"] == "wakeup" and state != "idle":
                        state = "idle"
                        new_state_p = f'{{"type":"state","state":"idle"}}\r\n'
                        writer.write(new_state_p.encode("utf8"))
                self.wakeup_handler_packets.append(packet)

    def _do_update_wakeup_hours(self):
        time.sleep(1)
        config = models.Config.load()
        now = datetime.datetime.now()
        config.wakeup_hour = now.hour - 2
        if config.wakeup_hour < 0:
            config.wakeup_hour += 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour + 2
        if config.sleep_hour >= 24:
            config.sleep_hour -= 24
        config.sleep_min = 0
        config.save()

    def _update_wakeup_hours(self, service):
        this_loop = asyncio.get_event_loop()
        thread = Thread(target=self._do_update_wakeup_hours)
        thread.start()
        thread.join()
        this_loop.create_task(service.reload_config())
        this_loop.call_later(1, lambda: this_loop.stop())

    def test_wakeup(self):
        self.mock_connection_handler = self.wakeup_handler
        self.wakeup_handler_packets = []
        self.wakeup_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        now = datetime.datetime.now()
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.save()
        service = nabclockd.NabClockd()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.wakeup_handler_called, 1)
        self.assertEqual(len(self.wakeup_handler_packets), 2)
        # NLU packet
        self.assertTrue("type" in self.wakeup_handler_packets[0])
        self.assertEqual(self.wakeup_handler_packets[0]["type"], "mode")
        self.assertTrue("type" in self.wakeup_handler_packets[1])
        self.assertEqual(self.wakeup_handler_packets[1]["type"], "wakeup")

    def test_sleep(self):
        self.mock_connection_handler = self.sleep_handler
        self.wakeup_handler_packets = []
        self.wakeup_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        now = datetime.datetime.now()
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.save()
        service = nabclockd.NabClockd()
        this_loop.call_later(1, lambda: this_loop.stop())
        service.run()
        self.assertEqual(self.wakeup_handler_called, 1)
        self.assertEqual(len(self.wakeup_handler_packets), 2)
        # NLU packet
        self.assertTrue("type" in self.wakeup_handler_packets[0])
        self.assertEqual(self.wakeup_handler_packets[0]["type"], "mode")
        self.assertTrue("type" in self.wakeup_handler_packets[1])
        self.assertEqual(self.wakeup_handler_packets[1]["type"], "sleep")

    def test_sleep_wakeup(self):
        self.mock_connection_handler = self.sleep_handler
        self.wakeup_handler_packets = []
        self.wakeup_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        config = models.Config.load()
        now = datetime.datetime.now()
        config.wakeup_hour = now.hour + 2
        if config.wakeup_hour >= 24:
            config.wakeup_hour -= 24
        config.wakeup_min = 0
        config.sleep_hour = now.hour - 2
        if config.sleep_hour < 0:
            config.sleep_hour += 24
        config.sleep_min = 0
        config.save()
        service = nabclockd.NabClockd()
        this_loop.call_later(1, lambda: self._update_wakeup_hours(service))
        service.run()
        self.assertEqual(self.wakeup_handler_called, 1)
        self.assertEqual(len(self.wakeup_handler_packets), 3)
        # NLU packet
        self.assertTrue("type" in self.wakeup_handler_packets[0])
        self.assertEqual(self.wakeup_handler_packets[0]["type"], "mode")
        self.assertTrue("type" in self.wakeup_handler_packets[1])
        self.assertEqual(self.wakeup_handler_packets[1]["type"], "sleep")
        self.assertTrue("type" in self.wakeup_handler_packets[2])
        self.assertEqual(self.wakeup_handler_packets[2]["type"], "wakeup")

    def test_clock_response(self):
        service = nabclockd.NabClockd()
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
