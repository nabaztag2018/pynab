import unittest, asyncio, threading, json, django, time, datetime, signal, pytest, re
from dateutil.tz import tzutc
from nabmastodond import nabmastodond, models
from nabcommon import nabservice

class MockMastodonClient:
  def __init__(self):
      self.posted_statuses = []

  def status_post(self, status, visibility=None, idempotency_key=None):
    """
    Callback as a mastodon_client
    """
    if visibility == None:
      visibility = 'public'
    content = re.sub(r'@([^ @]+)@([^ @]+)', r'<span class="h-card"><a href="https://\2/@\1" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>\1</span></a></span>', status)
    status = {'id': len(self.posted_statuses) + 1, 'created_at': datetime.datetime.utcnow(), 'visibility':visibility, 'content': content}
    self.posted_statuses.append(status)
    return status

  def timeline(self, *args, **kwargs):
    return []

  def close(self):
    pass

@pytest.mark.django_db
class TestMastodonLogic(unittest.TestCase, MockMastodonClient):
  def setUp(self):
    self.posted_statuses = []

  def test_process_status(self):
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, None)
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.save()
    service = nabmastodond.NabMastodond()
    service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'Hello','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())})
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])

  def test_ignore_old_status_by_date(self):
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, None)
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.save()
    service = nabmastodond.NabMastodond()
    service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())})
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(self.posted_statuses, [])

  def test_ignore_old_status_by_id(self):
    config = models.Config.load()
    config.last_processed_status_id = 64
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.save()
    service = nabmastodond.NabMastodond()
    service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())})
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 64)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(self.posted_statuses, [])

  def test_decode_dm(self):
    service = nabmastodond.NabMastodond()
    self.assertEqual(service.decode_dm({'content':'<p><span class="h-card"><a href="https://botsin.space/@rostropovich" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>rostropovich</span></a></span> Yup! (NabPairing Acceptation - <a href="https://github.com/nabaztag2018/pynab" rel="nofollow noopener" target="_blank"><span class="invisible">https://</span><span class="">github.com/nabaztag2018/pynab</span><span class="invisible"></span></a>)</p>'}), ('acceptation', None))

class TestMastodondBase(unittest.TestCase):
  async def mock_nabd_service_handler(self, reader, writer):
    self.service_writer = writer
    if self.mock_connection_handler:
      await self.mock_connection_handler(reader, writer)

  def mock_nabd_thread_entry_point(self, kwargs):
    self.mock_nabd_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.mock_nabd_loop)
    server_task = self.mock_nabd_loop.create_task(asyncio.start_server(self.mock_nabd_service_handler, 'localhost', nabservice.NabService.PORT_NUMBER))
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
    self.posted_statuses = []
    time.sleep(1)

  def tearDown(self):
    self.mock_nabd_loop.call_soon_threadsafe(lambda : self.mock_nabd_loop.stop())
    self.mock_nabd_thread.join(3)

@pytest.mark.django_db
class TestMastodond(TestMastodondBase):
  async def connect_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    self.connect_handler_called = self.connect_handler_called + 1

  def test_connect(self):
    self.mock_connection_handler = self.connect_handler
    self.connect_handler_called = 0
    self.service_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.service_loop)
    self.service_loop.call_later(1, lambda : self.service_loop.stop())
    service = nabmastodond.NabMastodond()
    service.run()
    self.assertEqual(self.connect_handler_called, 1)

  async def connect_with_ears_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    self.connect_with_ears_handler_called = self.connect_with_ears_handler_called + 1
    while not reader.at_eof():
      line = await reader.readline()
      if line != b'':
        packet = json.loads(line.decode('utf8'))
        self.connect_with_ears_handler_packets.append(packet)

  def test_connect_with_ears(self):
    self.mock_connection_handler = self.connect_with_ears_handler
    self.connect_with_ears_handler_packets = []
    self.connect_with_ears_handler_called = 0
    self.service_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.service_loop)
    self.service_loop.call_later(2, lambda : self.service_loop.stop())
    config = models.Config.load()
    config.spouse_left_ear_position = 3
    config.spouse_right_ear_position = 5
    config.spouse_pairing_state = 'married'
    config.save()
    service = nabmastodond.NabMastodond()
    service.run()
    self.assertEqual(self.connect_with_ears_handler_called, 1)
    self.assertEqual(len(self.connect_with_ears_handler_packets), 2)
    self.assertEqual(self.connect_with_ears_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.connect_with_ears_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.connect_with_ears_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.connect_with_ears_handler_packets[1]['type'], 'ears')
    self.assertEqual(self.connect_with_ears_handler_packets[1]['left'], 3)
    self.assertEqual(self.connect_with_ears_handler_packets[1]['right'], 5)

class TestMastodondPairingProtocol(TestMastodondBase, MockMastodonClient):
  """
  Test pairing protocol
  """
  def setUp(self):
    super().setUp()
    self.posted_statuses = []
    self.mock_connection_handler = self.protocol_handler
    self.protocol_handler_packets = []
    self.protocol_handler_called = 0
    self.service_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.service_loop)
    self.service_loop.call_later(2, lambda : self.service_loop.stop())

  async def protocol_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    self.protocol_handler_called = self.protocol_handler_called + 1
    while not reader.at_eof():
      line = await reader.readline()
      if line != b'':
        packet = json.loads(line.decode('utf8'))
        self.protocol_handler_packets.append(packet)

@pytest.mark.django_db
class TestMastodondPairingProtocolFree(TestMastodondPairingProtocol):
  def setUp(self):
    super().setUp()
    config = models.Config.load()
    config.instance = 'botsin.space'
    config.username = 'self'
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.save()

  # Free -> Waiting Approval

  def test_process_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  # Free -> Free

  def test_process_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, None)
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

@pytest.mark.django_db
class TestMastodondPairingProtocolProposed(TestMastodondPairingProtocol):
  def setUp(self):
    super().setUp()
    config = models.Config.load()
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.spouse_handle = 'tester@botsin.space'
    config.spouse_pairing_state = 'proposed'
    config.spouse_pairing_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.save()

  # Proposed -> Free

  def test_process_matching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  def test_process_matching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  # Proposed -> Married

  def test_process_matching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 2)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.protocol_handler_packets[1]['type'], 'message')

  def test_process_matching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 2)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.protocol_handler_packets[1]['type'], 'message')

  # Proposed -> Proposed

  def test_process_nonmatching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Rejection - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_matching_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 0)
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'proposed')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

@pytest.mark.django_db
class TestMastodondPairingProtocolWaitingApproval(TestMastodondPairingProtocol):
  def setUp(self):
    super().setUp()
    config = models.Config.load()
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.spouse_handle = 'tester@botsin.space'
    config.spouse_pairing_state = 'waiting_approval'
    config.spouse_pairing_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.save()

  # Waiting Approval -> Free

  def test_process_matching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  def test_process_matching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_matching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  # Waiting Approval -> Waiting Approval

  def test_process_matching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  def test_process_nonmatching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'other@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Rejection - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'message')

  def test_process_nonmatching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_matching_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 0)
    self.assertEqual(len(self.protocol_handler_packets), 0)

  def test_process_nonmatching_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'waiting_approval')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 0)

@pytest.mark.django_db
class TestMastodondPairingProtocolMarried(TestMastodondPairingProtocol):
  def setUp(self):
    super().setUp()
    config = models.Config.load()
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.spouse_handle = 'tester@botsin.space'
    config.spouse_pairing_state = 'married'
    config.spouse_pairing_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.save()

  # Married -> Free

  def test_process_matching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 3)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.protocol_handler_packets[1]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[1]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[1]['events'], [])
    self.assertEqual(self.protocol_handler_packets[2]['type'], 'message')

  def test_process_matching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, None)
    self.assertEqual(config.spouse_pairing_state, None)
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 3)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.protocol_handler_packets[1]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[1]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[1]['events'], [])
    self.assertEqual(self.protocol_handler_packets[2]['type'], 'message')

  # Married -> Married

  def test_process_matching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_matching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 0)
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_matching_ears(self):
    config = models.Config.load()
    config.spouse_left_ear_position = 7
    config.spouse_right_ear_position = 5
    config.save()
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'tester@botsin.space','url':'https://botsin.space/@tester','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_left_ear_position, 4)
    self.assertEqual(config.spouse_right_ear_position, 6)
    self.assertEqual(len(self.posted_statuses), 0)
    self.assertEqual(len(self.protocol_handler_packets), 4)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])
    self.assertEqual(self.protocol_handler_packets[1]['type'], 'ears')
    self.assertEqual(self.protocol_handler_packets[1]['left'], 7)
    self.assertEqual(self.protocol_handler_packets[1]['right'], 5)
    self.assertEqual(self.protocol_handler_packets[2]['type'], 'command')
    self.assertEqual(self.protocol_handler_packets[3]['type'], 'ears')
    self.assertEqual(self.protocol_handler_packets[3]['left'], 4)
    self.assertEqual(self.protocol_handler_packets[3]['right'], 6)

  def test_process_nonmatching_proposal(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Would you accept to be my spouse? (NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Rejection - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_nonmatching_acceptation(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_nonmatching_rejection(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse right now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_nonmatching_divorce(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> I think we should split. Can we skip the lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(self.posted_statuses, [])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

  def test_process_nonmatching_ears(self):
    service = nabmastodond.NabMastodond()
    self.service_loop.call_later(1, lambda : service.do_update(self, {'id':42,'visibility':'direct','account':{'acct':'other@botsin.space','url':'https://botsin.space/@other','display_name':'Test specialist'},'content':'<p><span class="h-card"><a href="https://botsin.space/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank">@<span>nabaztag</span></a></span> Let\'s dance (NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)</p>','created_at':datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())}))
    service.run()
    config = models.Config.load()
    self.assertEqual(config.last_processed_status_id, 42)
    self.assertEqual(config.last_processed_status_date, datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc()))
    self.assertEqual(config.spouse_handle, 'tester@botsin.space')
    self.assertEqual(config.spouse_pairing_state, 'married')
    self.assertEqual(config.spouse_pairing_date, datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc()))
    self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Divorce - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@other' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.protocol_handler_packets), 1)
    self.assertEqual(self.protocol_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.protocol_handler_packets[0]['mode'], 'idle')
    self.assertEqual(self.protocol_handler_packets[0]['events'], ['ears'])

@pytest.mark.django_db
class TestMastodondEars(TestMastodondBase, MockMastodonClient):
  """
  Test pairing protocol
  """
  def setUp(self):
    super().setUp()
    self.posted_statuses = []
    self.mock_connection_handler = self.ears_handler
    self.ears_handler_packets = []
    self.ears_handler_called = 0
    self.service_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.service_loop)
    self.service_loop.call_later(2, lambda : self.service_loop.stop())

  async def ears_handler(self, reader, writer):
    writer.write(b'{"type":"state","state":"idle"}\r\n')
    writer.write(b'{"type":"ears_event","left":4,"right":6}\r\n')
    self.ears_handler_called = self.ears_handler_called + 1
    while not reader.at_eof():
      line = await reader.readline()
      if line != b'':
        packet = json.loads(line.decode('utf8'))
        self.ears_handler_packets.append(packet)

  def test_married(self):
    config = models.Config.load()
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.spouse_left_ear_position = 7
    config.spouse_right_ear_position = 5
    config.spouse_handle = 'tester@botsin.space'
    config.spouse_pairing_state = 'married'
    config.spouse_pairing_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.access_token = 'access_token'
    config.save()
    service = nabmastodond.NabMastodond()
    service.mastodon_client = self
    service.mastodon_stream_handle = self
    service.current_access_token = 'access_token'
    service.run()
    config = models.Config.load()
    #self.assertEqual(config.spouse_left_ear_position, 4)
    #self.assertEqual(config.spouse_right_ear_position, 6)
    #self.assertEqual(len(self.posted_statuses), 1)
    self.assertEqual(self.posted_statuses[0]['visibility'], 'direct')
    self.assertTrue('(NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)' in self.posted_statuses[0]['content'])
    self.assertTrue('botsin.space/@tester' in self.posted_statuses[0]['content'])
    self.assertEqual(len(self.ears_handler_packets), 3)
    self.assertEqual(self.ears_handler_packets[0]['type'], 'mode')
    self.assertEqual(self.ears_handler_packets[1]['type'], 'ears')
    self.assertEqual(self.ears_handler_packets[2]['type'], 'command')

  def test_not_married(self):
    config = models.Config.load()
    config.last_processed_status_date = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
    config.instance = 'botsin.space'
    config.username = 'self'
    config.spouse_handle = None
    config.spouse_pairing_state = None
    config.spouse_pairing_date = None
    config.save()
    service = nabmastodond.NabMastodond()
    service.mastodon_client = self
    service.run()
    config = models.Config.load()
    self.assertEqual(config.spouse_left_ear_position, None)
    self.assertEqual(config.spouse_right_ear_position, None)
    self.assertEqual(len(self.posted_statuses), 0)
    self.assertEqual(len(self.ears_handler_packets), 0)
