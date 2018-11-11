import unittest, asyncio, threading, json, django, time, datetime, signal, pytest
from dateutil.tz import tzutc
from nabmastodond import nabmastodond, models
from nabd import nabd

@pytest.mark.django_db
class TestMastodonLogic(unittest.TestCase):
  def test_process_status(self):
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, None)
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.save()
    service = nabmastodond.NabMastodond()
    service.do_update({'id':42,'created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())})
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))

@pytest.mark.django_db
class TestMastodond(unittest.TestCase):
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
    service = nabmastodond.NabMastodond()
    service.run()
    self.assertEqual(self.connect_handler_called, 1)

  async def connect_with_ears_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    self.connect_with_ears_handler_called = self.connect_with_ears_handler_called + 1
    while not reader.at_eof():
      line = await reader.readline()
      if line != b'':
        packet = json.loads(line)
        self.connect_with_ears_handler_packet = packet
        break

  def test_connect_with_ears(self):
    self.mock_connection_handler = self.connect_with_ears_handler
    self.connect_with_ears_handler_packet = None
    self.connect_with_ears_handler_called = 0
    this_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(this_loop)
    this_loop.call_later(2, lambda : this_loop.stop())
    config = models.Config.load()
    config.spouse_left_ear_position = 3
    config.spouse_right_ear_position = 5
    config.save()
    service = nabmastodond.NabMastodond()
    service.run()
    self.assertEqual(self.connect_with_ears_handler_called, 1)
    self.assertIsNot(self.connect_with_ears_handler_packet, None)
    self.assertTrue('type' in self.connect_with_ears_handler_packet)
    self.assertEqual(self.connect_with_ears_handler_packet['type'], 'ears')
    self.assertTrue('left' in self.connect_with_ears_handler_packet)
    self.assertTrue('right' in self.connect_with_ears_handler_packet)
    self.assertEqual(self.connect_with_ears_handler_packet['left'], 3)
    self.assertEqual(self.connect_with_ears_handler_packet['right'], 5)
