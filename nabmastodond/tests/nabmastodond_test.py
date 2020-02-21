import unittest
import asyncio
import json
import django
import time
import datetime
import signal
import pytest
import re
import os
from dateutil.tz import tzutc
from asgiref.sync import async_to_sync
from nabmastodond import nabmastodond, models
from nabcommon import nabservice
from mastodon import Mastodon, MastodonNotFoundError
from nabd.tests.mock import NabdMockTestCase
from nabd.tests.utils import close_old_async_connections


DATE_1 = datetime.datetime(2018, 11, 11, 11, 11, 0, tzinfo=tzutc())
DATE_2 = datetime.datetime(2018, 11, 11, 11, 11, 11, tzinfo=tzutc())
TESTER_MASTODON_ACCOUNT = {
    "acct": "tester@botsin.space",
    "url": "https://botsin.space/@tester",
    "display_name": "Test specialist",
}
OTHER_MASTODON_ACCOUNT = {
    "acct": "other@botsin.space",
    "url": "https://botsin.space/@other",
    "display_name": "Test specialist",
}
SPLIT_CONTENT = (
    '<p><span class="h-card"><a href="https://botsin.space/@nab'
    'aztag" class="u-url mention" rel="nofollow noopener" target="_blank">@'
    "<span>nabaztag</span></a></span> I think we should split. Can weskip t"
    "he lawyers? (NabPairing Divorce - https://github.com/nabaztag2018/pyna"
    "b)</p>"
)
REJECTION_CONTENT = (
    '<p><span class="h-card"><a href="https://botsin.space/'
    '@nabaztag" class="u-url mention" rel="nofollow noopener" target="_blan'
    'k">@<span>nabaztag</span></a></span> Sorry, I cannot be your spouse ri'
    "ght now (NabPairing Rejection - https://github.com/nabaztag2018/pynab)"
    "</p>"
)
EARS_4_6_CONTENT = (
    '<p><span class="h-card"><a href="https://botsin.space/@'
    'nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank'
    "\">@<span>nabaztag</span></a></span> Let's dance (NabPairing Ears 4 6 "
    "- https://github.com/nabaztag2018/pynab)</p>"
)
PROPOSAL_CONTENT = (
    '<p><span class="h-card"><a href="https://botsin.space/@'
    'nabaztag" class="u-url mention" rel="nofollow noopener" target="_blank'
    '">@<span>nabaztag</span></a></span> Would you accept to be my spouse? '
    "(NabPairing Proposal - https://github.com/nabaztag2018/pynab)</p>"
)
ACCEPTATION_CONTENT = (
    '<p><span class="h-card"><a href="https://botsin.spac'
    'e/@nabaztag" class="u-url mention" rel="nofollow noopener" target="_bl'
    'ank">@<span>nabaztag</span></a></span> Oh yes, I do accept to be your '
    "spouse (NabPairing Acceptation - https://github.com/nabaztag2018/pynab"
    ")</p>"
)
ALTERNATE_ACCEPTATION_CONTENT = (
    '<p><span class="h-card"><a href="https://b'
    'otsin.space/@rostropovich" class="u-url mention" rel="nofollow noopene'
    'r" target="_blank">@<span>rostropovich</span></a></span> Yup! (NabPair'
    'ing Acceptation - <a href="https://github.com/nabaztag2018/pynab" rel='
    '"nofollow noopener" target="_blank"><span class="invisible">https://</'
    'span><span class="">github.com/nabaztag2018/pynab</span><span class="i'
    'nvisible"></span></a>)</p>'
)


class MockMastodonClient:
    def __init__(self):
        self.posted_statuses = []

    def status_post(self, status, visibility=None, idempotency_key=None):
        """
        Callback as a mastodon_client
        """
        if visibility is None:
            visibility = "public"
        content = re.sub(
            r"@([^ @]+)@([^ @]+)",
            r'<span class="h-card"><a href="https://\2/@\1" '
            r'class="u-url mention" rel="nofollow noopener" '
            r'target="_blank">@<span>\1</span></a></span>',
            status,
        )
        status = {
            "id": len(self.posted_statuses) + 1,
            "created_at": datetime.datetime.utcnow(),
            "visibility": visibility,
            "content": content,
        }
        self.posted_statuses.append(status)
        return status

    def conversations(self, *args, **kwargs):
        return []

    def close(self):
        pass


@pytest.mark.django_db(transaction=True)
class TestMastodonLogic(unittest.TestCase, MockMastodonClient):
    def setUp(self):
        self.posted_statuses = []

    def tearDown(self):
        close_old_async_connections()

    def test_process_status(self):
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, None)
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
        config.save()
        service = nabmastodond.NabMastodond()
        async_to_sync(service.loop_update)(
            self,
            {
                "id": 42,
                "visibility": "direct",
                "account": {
                    "acct": "tester@botsin.space",
                    "url": "https://botsin.space/@tester",
                    "display_name": "Test specialist",
                },
                "content": "Hello",
                "created_at": DATE_2,
            },
        )
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])

    def test_ignore_old_status_by_date(self):
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, None)
        config.last_processed_status_date = DATE_2
        config.instance = "botsin.space"
        config.username = "self"
        config.save()
        service = nabmastodond.NabMastodond()
        async_to_sync(service.loop_update)(
            self,
            {
                "id": 42,
                "visibility": "direct",
                "account": TESTER_MASTODON_ACCOUNT,
                "content": PROPOSAL_CONTENT,
                "created_at": DATE_1,
            },
        )
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(self.posted_statuses, [])

    def test_ignore_old_status_by_id(self):
        config = models.Config.load()
        config.last_processed_status_id = 64
        config.last_processed_status_date = DATE_2
        config.instance = "botsin.space"
        config.username = "self"
        config.save()
        service = nabmastodond.NabMastodond()
        async_to_sync(service.loop_update)(
            self,
            {
                "id": 42,
                "visibility": "direct",
                "account": TESTER_MASTODON_ACCOUNT,
                "content": PROPOSAL_CONTENT,
                "created_at": DATE_1,
            },
        )
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 64)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(self.posted_statuses, [])

    def test_decode_dm(self):
        service = nabmastodond.NabMastodond()
        self.assertEqual(
            service.decode_dm({"content": ALTERNATE_ACCEPTATION_CONTENT}),
            ("acceptation", None),
        )


class TestMastodondBase(NabdMockTestCase):
    def setUp(self):
        NabdMockTestCase.setUp(self)
        self.posted_statuses = []


@pytest.mark.django_db(transaction=True)
class TestMastodond(TestMastodondBase):
    def tearDown(self):
        TestMastodondBase.tearDown(self)
        close_old_async_connections()

    def test_connect(self):
        self.do_test_connect(nabmastodond.NabMastodond)

    async def connect_with_ears_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        self.connect_with_ears_handler_called += 1
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                self.connect_with_ears_handler_packets.append(packet)

    def test_connect_with_ears(self):
        self.mock_connection_handler = self.connect_with_ears_handler
        self.connect_with_ears_handler_packets = []
        self.connect_with_ears_handler_called = 0
        self.service_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.service_loop)
        self.service_loop.call_later(2, lambda: self.service_loop.stop())
        config = models.Config.load()
        config.spouse_left_ear_position = 3
        config.spouse_right_ear_position = 5
        config.spouse_pairing_state = "married"
        config.save()
        service = nabmastodond.NabMastodond()
        service.run()
        self.assertEqual(self.connect_with_ears_handler_called, 1)
        self.assertEqual(len(self.connect_with_ears_handler_packets), 2)
        self.assertEqual(
            self.connect_with_ears_handler_packets[0]["type"], "mode"
        )
        self.assertEqual(
            self.connect_with_ears_handler_packets[0]["mode"], "idle"
        )
        self.assertEqual(
            self.connect_with_ears_handler_packets[0]["events"], ["ears"]
        )
        self.assertEqual(
            self.connect_with_ears_handler_packets[1]["type"], "ears"
        )
        self.assertEqual(self.connect_with_ears_handler_packets[1]["left"], 3)
        self.assertEqual(self.connect_with_ears_handler_packets[1]["right"], 5)


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
        self.service_loop.call_later(2, lambda: self.service_loop.stop())

    def tearDown(self):
        TestMastodondBase.tearDown(self)
        close_old_async_connections()

    async def protocol_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        await writer.drain()
        self.protocol_handler_called += 1
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                self.protocol_handler_packets.append(packet)


@pytest.mark.django_db(transaction=True)
class TestMastodondPairingProtocolFree(TestMastodondPairingProtocol):
    def setUp(self):
        super().setUp()
        config = models.Config.load()
        config.instance = "botsin.space"
        config.username = "self"
        config.last_processed_status_date = DATE_1
        config.save()

    # Free -> Waiting Approval

    def test_process_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    # Free -> Free

    def test_process_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)


@pytest.mark.django_db(transaction=True)
class TestMastodondPairingProtocolProposed(TestMastodondPairingProtocol):
    def setUp(self):
        super().setUp()
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
        config.spouse_handle = "tester@botsin.space"
        config.spouse_pairing_state = "proposed"
        config.spouse_pairing_date = DATE_1
        config.save()

    # Proposed -> Free

    def test_process_matching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    def test_process_matching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    # Proposed -> Married

    def test_process_matching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 2)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])
        self.assertEqual(self.protocol_handler_packets[1]["type"], "message")

    def test_process_matching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 2)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])
        self.assertEqual(self.protocol_handler_packets[1]["type"], "message")

    # Proposed -> Proposed

    def test_process_nonmatching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Rejection - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_matching_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 0)
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "proposed")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)


@pytest.mark.django_db(transaction=True)
class TestMastodondPairingProtocolWaitingApproval(
    TestMastodondPairingProtocol
):
    def setUp(self):
        super().setUp()
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
        config.spouse_handle = "tester@botsin.space"
        config.spouse_pairing_state = "waiting_approval"
        config.spouse_pairing_date = DATE_1
        config.save()

    # Waiting Approval -> Free

    def test_process_matching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    def test_process_matching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_matching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)

    # Waiting Approval -> Waiting Approval

    def test_process_matching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    def test_process_nonmatching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "other@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Rejection - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "message")

    def test_process_nonmatching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_matching_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 0)
        self.assertEqual(len(self.protocol_handler_packets), 0)

    def test_process_nonmatching_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 0)


@pytest.mark.django_db(transaction=True)
class TestMastodondPairingProtocolMarried(TestMastodondPairingProtocol):
    def setUp(self):
        super().setUp()
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
        config.spouse_handle = "tester@botsin.space"
        config.spouse_pairing_state = "married"
        config.spouse_pairing_date = DATE_1
        config.save()

    # Married -> Free

    def test_process_matching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 3)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])
        self.assertEqual(self.protocol_handler_packets[1]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[1]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[1]["events"], [])
        self.assertEqual(self.protocol_handler_packets[2]["type"], "message")

    def test_process_matching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 3)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])
        self.assertEqual(self.protocol_handler_packets[1]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[1]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[1]["events"], [])
        self.assertEqual(self.protocol_handler_packets[2]["type"], "message")

    # Married -> Married

    def test_process_matching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_matching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(len(self.posted_statuses), 0)
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_matching_ears(self):
        config = models.Config.load()
        config.spouse_left_ear_position = 7
        config.spouse_right_ear_position = 5
        config.save()
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": TESTER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_2)
        self.assertEqual(config.spouse_left_ear_position, 4)
        self.assertEqual(config.spouse_right_ear_position, 6)
        self.assertEqual(len(self.posted_statuses), 0)
        self.assertEqual(len(self.protocol_handler_packets), 4)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])
        self.assertEqual(self.protocol_handler_packets[1]["type"], "ears")
        self.assertEqual(self.protocol_handler_packets[1]["left"], 7)
        self.assertEqual(self.protocol_handler_packets[1]["right"], 5)
        self.assertEqual(self.protocol_handler_packets[2]["type"], "command")
        self.assertEqual(self.protocol_handler_packets[3]["type"], "ears")
        self.assertEqual(self.protocol_handler_packets[3]["left"], 4)
        self.assertEqual(self.protocol_handler_packets[3]["right"], 6)

    def test_process_nonmatching_proposal(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": PROPOSAL_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Rejection - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_nonmatching_acceptation(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": ACCEPTATION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_nonmatching_rejection(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": REJECTION_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_nonmatching_divorce(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": SPLIT_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(self.posted_statuses, [])
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])

    def test_process_nonmatching_ears(self):
        service = nabmastodond.NabMastodond()
        self.service_loop.call_later(
            0.5,
            lambda: self.service_loop.create_task(
                service.loop_update(
                    self,
                    {
                        "id": 42,
                        "visibility": "direct",
                        "account": OTHER_MASTODON_ACCOUNT,
                        "content": EARS_4_6_CONTENT,
                        "created_at": DATE_2,
                    },
                )
            ),
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, 42)
        self.assertEqual(config.last_processed_status_date, DATE_2)
        self.assertEqual(config.spouse_handle, "tester@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "married")
        self.assertEqual(config.spouse_pairing_date, DATE_1)
        self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@other" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.protocol_handler_packets), 1)
        self.assertEqual(self.protocol_handler_packets[0]["type"], "mode")
        self.assertEqual(self.protocol_handler_packets[0]["mode"], "idle")
        self.assertEqual(self.protocol_handler_packets[0]["events"], ["ears"])


@pytest.mark.django_db(transaction=True)
class TestMastodondEars(TestMastodondBase, MockMastodonClient):
    """
    Test pairing protocol
    """

    def setUp(self):
        super().setUp()
        self.posted_statuses = []
        self.mock_connection_handler = self.ears_handler
        self.connection = None
        self.ears_handler_packets = []
        self.ears_handler_called = 0
        self.service_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.service_loop)
        self.service_loop.call_later(2, lambda: self.service_loop.stop())

    def tearDown(self):
        TestMastodondBase.tearDown(self)
        close_old_async_connections()

    async def ears_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        writer.write(b'{"type":"ears_event","left":4,"right":6}\r\n')
        await writer.drain()
        self.ears_handler_called += 1
        while not reader.at_eof():
            line = await reader.readline()
            if line != b"":
                packet = json.loads(line.decode("utf8"))
                self.ears_handler_packets.append(packet)

    def test_married(self):
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
        config.spouse_left_ear_position = 7
        config.spouse_right_ear_position = 5
        config.spouse_handle = "tester@botsin.space"
        config.spouse_pairing_state = "married"
        config.spouse_pairing_date = DATE_1
        config.access_token = "access_token"
        config.save()
        service = nabmastodond.NabMastodond()
        service.mastodon_client = self
        service.mastodon_stream_handle = self
        service.current_access_token = "access_token"
        service.run()
        config = models.Config.load()
        # self.assertEqual(config.spouse_left_ear_position, 4)
        # self.assertEqual(config.spouse_right_ear_position, 6)
        # self.assertEqual(len(self.posted_statuses), 1)
        self.assertEqual(self.posted_statuses[0]["visibility"], "direct")
        self.assertTrue(
            "(NabPairing Ears 4 6 - https://github.com/nabaztag2018/pynab)"
            in self.posted_statuses[0]["content"]
        )
        self.assertTrue(
            "botsin.space/@tester" in self.posted_statuses[0]["content"]
        )
        self.assertEqual(len(self.ears_handler_packets), 3)
        # command may happen first if nabd packet is processed early
        if self.ears_handler_packets[0]["type"] == "mode":
            self.assertEqual(self.ears_handler_packets[1]["type"], "ears")
            self.assertEqual(self.ears_handler_packets[2]["type"], "command")
        else:
            self.assertEqual(self.ears_handler_packets[0]["type"], "command")
            self.assertEqual(self.ears_handler_packets[1]["type"], "mode")
            self.assertEqual(self.ears_handler_packets[2]["type"], "ears")

    def test_not_married(self):
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = "self"
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


class TestMastodonClientBase:
    INSTANCE = "botsin.space"
    API_BASE_URL = "https://" + INSTANCE
    REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

    APPKEY_FILE = "./tmp/mastodon-test-app-key.txt"

    USER1KEY_FILE = "./tmp/mastodon-test-user-1-key.txt"
    USER1OOB_FILE = "./tmp/mastodon-test-user-1-oob.txt"
    USER2KEY_FILE = "./tmp/mastodon-test-user-2-key.txt"
    USER2OOB_FILE = "./tmp/mastodon-test-user-2-oob.txt"

    def setUp(self):
        if not os.path.isfile(TestMastodonClientBase.APPKEY_FILE):
            if not os.path.exists("./tmp/"):
                os.makedirs("./tmp/")
            (client_id, client_secret) = Mastodon.create_app(
                "nabmastodond",
                api_base_url=TestMastodonClientBase.API_BASE_URL,
                redirect_uris=TestMastodonClientBase.REDIRECT_URI,
            )
            with open(TestMastodonClientBase.APPKEY_FILE, "w") as appkey_file:
                appkey_file.writelines(
                    [client_id + "\n", client_secret + "\n"]
                )
        with open(TestMastodonClientBase.APPKEY_FILE, "r") as appkey_file:
            self.client_id = appkey_file.readline().strip()
            self.client_secret = appkey_file.readline().strip()
        self.user1_access_token, self.user1_username = self.login(
            TestMastodonClientBase.USER1KEY_FILE,
            TestMastodonClientBase.USER1OOB_FILE,
            1,
        )
        self.user2_access_token, self.user2_username = self.login(
            TestMastodonClientBase.USER2KEY_FILE,
            TestMastodonClientBase.USER2OOB_FILE,
            2,
        )

    def tearDown(self):
        if self.user1_access_token is not None:
            self.purge_dms(self.user1_access_token)
        if self.user2_access_token is not None:
            self.purge_dms(self.user2_access_token)

    def login(self, key_file, oob_file, user_n):
        if not os.path.isfile(key_file):
            mastodon_client = Mastodon(
                client_id=self.client_id,
                client_secret=self.client_secret,
                api_base_url=TestMastodonClientBase.API_BASE_URL,
            )
            if not os.path.isfile(oob_file):
                request_url = mastodon_client.auth_request_url(
                    redirect_uris=TestMastodonClientBase.REDIRECT_URI
                )
                reason = (
                    f"Log as user {user_n} and visit {request_url} and"
                    f" save code to {oob_file}"
                )
                print(reason)
                pytest.skip(reason)
            with open(oob_file, "r") as oob_file:
                oob = oob_file.readline().strip()
            access_token = mastodon_client.log_in(
                code=oob, redirect_uri=TestMastodonClientBase.REDIRECT_URI
            )
            with open(key_file, "w") as user1key_file:
                user1key_file.writelines([access_token])
        with open(key_file, "r") as user1key_file:
            access_token = user1key_file.readline().strip()
            mastodon_client = Mastodon(
                client_id=self.client_id,
                client_secret=self.client_secret,
                api_base_url=TestMastodonClientBase.API_BASE_URL,
                access_token=access_token,
            )
            account_details = mastodon_client.account_verify_credentials()
            return (access_token, account_details.username)

    def purge_dms(self, access_token):
        mastodon_client = Mastodon(
            client_id=self.client_id,
            client_secret=self.client_secret,
            api_base_url=TestMastodonClientBase.API_BASE_URL,
            access_token=access_token,
        )
        conversations = mastodon_client.conversations()
        for conversation in conversations:
            status = conversation.last_status
            try:
                mastodon_client.status_delete(status.id)
            except MastodonNotFoundError:
                pass


class TestSendDM(unittest.TestCase, TestMastodonClientBase):
    def setUp(self):
        TestMastodonClientBase.setUp(self)

    def tearDown(self):
        TestMastodonClientBase.tearDown(self)

    def test_connect_send_dm(self):
        user1_mastodon_client = Mastodon(
            client_id=self.client_id,
            client_secret=self.client_secret,
            api_base_url=TestMastodonClientBase.API_BASE_URL,
            access_token=self.user1_access_token,
        )
        spouse = self.user2_username
        if "@" not in spouse:
            spouse = spouse + "@" + TestMastodonClientBase.INSTANCE
        proposal_toot = nabmastodond.NabMastodond.send_dm(
            user1_mastodon_client, spouse, "proposal"
        )
        user2_mastodon_client = Mastodon(
            client_id=self.client_id,
            client_secret=self.client_secret,
            api_base_url=TestMastodonClientBase.API_BASE_URL,
            access_token=self.user2_access_token,
        )
        self.assertEqual(
            user2_mastodon_client.conversations()[0].last_status.id,
            proposal_toot.id,
        )


@pytest.mark.django_db(transaction=True)
class TestMastodonClientProposal(TestMastodondBase, TestMastodonClientBase):
    def setUp(self):
        # Give a chance to TestMastodonClientBase to skip the test before
        # starting a mock nabd
        TestMastodonClientBase.setUp(self)
        TestMastodondBase.setUp(self)
        self.alter_mastodon_client = Mastodon(
            client_id=self.client_id,
            client_secret=self.client_secret,
            api_base_url=TestMastodonClientBase.API_BASE_URL,
            access_token=self.user2_access_token,
        )

    def tearDown(self):
        TestMastodondBase.tearDown(self)
        TestMastodonClientBase.tearDown(self)
        close_old_async_connections()

    def test_mastodon_client_alter_proposal_before_start(self):
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = self.user1_username
        config.access_token = self.user1_access_token
        config.save()
        self.service_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.service_loop)
        self.service_loop.call_later(1, lambda: self.service_loop.stop())
        service = nabmastodond.NabMastodond()
        proposal_toot = nabmastodond.NabMastodond.send_dm(
            self.alter_mastodon_client, self.user1_username, "proposal"
        )
        service.run()
        config = models.Config.load()
        self.assertEqual(config.last_processed_status_id, proposal_toot.id)
        self.assertEqual(
            config.last_processed_status_date, proposal_toot.created_at
        )
        self.assertEqual(config.spouse_handle, "pynab_test_2@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(config.spouse_pairing_date, proposal_toot.created_at)

    def test_mastodon_client_alter_proposal_after_start(self):
        config = models.Config.load()
        config.last_processed_status_date = DATE_1
        config.instance = "botsin.space"
        config.username = self.user1_username
        config.access_token = self.user1_access_token
        config.save()
        self.service_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.service_loop)
        self.service_loop.call_later(
            2,
            lambda: nabmastodond.NabMastodond.send_dm(
                self.alter_mastodon_client, self.user1_username, "proposal"
            ),
        )
        self.service_loop.call_later(3, lambda: self.service_loop.stop())
        service = nabmastodond.NabMastodond()
        service.run()
        config = models.Config.load()
        self.assertNotEqual(config.last_processed_status_id, None)
        self.assertNotEqual(config.last_processed_status_date, None)
        self.assertEqual(config.spouse_handle, "pynab_test_2@botsin.space")
        self.assertEqual(config.spouse_pairing_state, "waiting_approval")
        self.assertEqual(
            config.spouse_pairing_date, config.last_processed_status_date
        )
