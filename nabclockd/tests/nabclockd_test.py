import unittest, asyncio, threading, json, django, time, datetime, signal, pytest
from nabclockd import nabclockd, models
from nabd import nabd

@pytest.mark.django_db
class TestNabclockd(unittest.TestCase):
  async def mock_nabd_service_handler(self, reader, writer):
    self.service_writer = writer
    if self.mock_connection_handler:
      await self.mock_connection_handler(reader, writer)

  def mock_nabd_thread_entry_point(self, kwargs):
    self.mock_nabd_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.mock_nabd_loop)
    server_task = self.mock_nabd_loop.create_task(asyncio.start_server(self.mock_nabd_service_handler, 'localhost', nabd.Nabd.PORT_NUMBER))
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
    self.mock_nabd_thread = threading.Thread(target = self.mock_nabd_thread_entry_point, args = [self])
    self.mock_nabd_thread.start()
    time.sleep(1)

  def tearDown(self):
    self.mock_nabd_loop.call_soon_threadsafe(lambda : self.mock_nabd_loop.stop())
    self.mock_nabd_thread.join(3)

  async def connect_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    self.connect_handler_called = self.connect_handler_called + 1

  def test_connect(self):
    self.mock_connection_handler = self.connect_handler
    self.connect_handler_called = 0
    this_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(this_loop)
    this_loop.call_later(1, lambda : this_loop.stop())
    service = nabclockd.NabClockd()
    service.run()
    self.assertEqual(self.connect_handler_called, 1)

  async def wakeup_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"asleep"}\r\n')
    self.wakeup_handler_called = self.wakeup_handler_called + 1
    while not reader.at_eof():
      line = await reader.readline()
      if line != b'':
        packet = json.loads(line)
        self.wakeup_handler_packet = packet
        break

  def test_wakeup(self):
    self.mock_connection_handler = self.wakeup_handler
    self.wakeup_handler_packet = None
    self.wakeup_handler_called = 0
    this_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(this_loop)
    this_loop.call_later(2, lambda : this_loop.stop())
    service = nabclockd.NabClockd()
    config = models.Config.load()
    now = datetime.datetime.now()
    config.wakeup_hour = now.hour
    config.wakeup_min = 0
    if now.hour == 23:
      config.sleep_hour = 0
    else:
      config.sleep_hour = now.hour + 1
    config.sleep_min = 0
    config.save()
    this_loop.create_task(service.reload_config())
    this_loop.call_later(1, lambda : this_loop.create_task(service.reload_config()))
    service.run()
    self.assertEqual(self.wakeup_handler_called, 1)
    self.assertIsNot(self.wakeup_handler_packet, None)
    self.assertTrue('type' in self.wakeup_handler_packet)
    self.assertEqual(self.wakeup_handler_packet['type'], 'wakeup')

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
    self.assertEqual(service.clock_response(datetime.datetime(1970,1,1,0,0,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(1970,1,1,8,0,0)), [])
    service.asleep = True
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,0,0,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,7,0,0)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,0)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,30)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,1,0)), ['wakeup'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,6,0)), ['wakeup','reset_last_chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,22,0,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,23,0,0)), [])
    service.asleep = False
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,0,0,0)), ['sleep'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,7,0,0)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,0)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,30)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,1,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,6,0)), ['reset_last_chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,22,0,0)), ['sleep'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,23,0,0)), ['sleep'])
    config.wakeup_hour = 22
    config.wakeup_min = 0
    config.sleep_hour = 7
    config.sleep_min = 0
    config.chime_hour = True
    config.save()
    reload_task = this_loop.create_task(service.reload_config())
    this_loop.run_until_complete(reload_task)
    service.asleep = True
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,0,0,0)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,1,0,30)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,1,6,0)), ['wakeup','reset_last_chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,7,0,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,1,0)), [])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,22,0,0)), ['wakeup','chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,23,0,0)), ['wakeup','chime'])
    service.asleep = False
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,0,0,0)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,1,0,30)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,1,6,0)), ['reset_last_chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,7,0,0)), ['sleep'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,0,0)), ['sleep'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,8,1,0)), ['sleep'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,22,0,0)), ['chime'])
    self.assertEqual(service.clock_response(datetime.datetime(2018,11,2,23,0,0)), ['chime'])
