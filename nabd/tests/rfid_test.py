import asyncio
import socket
import unittest.mock
from unittest import TestCase

from nabd.rfid import TagFlags
from nabd.rfid_dev import RfidDev, RfidDevState


class TestResources(TestCase):
    def test_is_compatible(self):
        self.assertTrue(
            RfidDev.is_compatible(b"\xD0\x02\x0C\xC1\x1E\xCB\x0D\x02")
        )
        self.assertTrue(
            RfidDev.is_compatible(b"\xD0\x02\x18\xBD\x6E\x56\x8A\xE6")
        )
        self.assertTrue(
            RfidDev.is_compatible(b"\xD0\x02\x30\xD6\x44\x8D\x6A\x5A")
        )
        self.assertFalse(
            RfidDev.is_compatible(b"\xE0\x01\x02\x03\x04\x05\x06\x07")
        )
        self.assertFalse(
            RfidDev.is_compatible(b"\xD0\x01\x02\x03\x04\x05\x06\x07")
        )
        self.assertFalse(
            RfidDev.is_compatible(b"\xD0\x02\x02\x03\x04\x05\x06\x07")
        )


class TestRfidDevRemovalTimeout(TestCase):
    """
    When the removal timeout expires while the reader's packet is waiting
    (nabd busy playing the detection sound), the tag must not be reported
    removed then detected again: that ran the tag's action twice.
    """

    UID_LE = bytes(reversed(b"\xD0\x02\x1A\x35\x03\x94\x48\x3A"))

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.events = []
        self.dev_sock, self.reader_sock = socket.socketpair()
        self.reader_sock.setblocking(False)
        with unittest.mock.patch("os.path.exists", return_value=False):
            self.dev = RfidDev()
        # Plug the socket in place of /dev/rfid0, without the reader
        # callback: the test calls _do_read itself.
        self.dev._RfidDev__fd = self.dev_sock.fileno()
        self.dev._RfidDev__callback = (self.loop, self._on_event)
        self.dev._RfidDev__state = RfidDevState.POLLING_REPEAT
        self.dev._RfidDev__current_uid = bytearray(reversed(self.UID_LE))

    def tearDown(self):
        self.dev._cancel_timer()
        self.dev_sock.close()
        self.reader_sock.close()
        self.loop.close()
        asyncio.set_event_loop(None)

    def _on_event(self, tech, uid, picture, app, app_data, flags, tag_info):
        self.events.append(flags)

    def _run_pending_callbacks(self):
        self.loop.run_until_complete(asyncio.sleep(0))

    def _commands_sent(self):
        try:
            return self.reader_sock.recv(64)
        except BlockingIOError:
            return b""

    def test_pending_uid_keeps_the_tag(self):
        self.reader_sock.sendall(b"u" + self.UID_LE)
        self.dev._timer_cb()
        self.dev._do_read()
        self._run_pending_callbacks()
        self.assertEqual(self.events, [])
        self.assertEqual(self._commands_sent(), b"")
        self.assertEqual(self.dev._RfidDev__state, RfidDevState.POLLING_REPEAT)

    def test_no_uid_removes_the_tag(self):
        self.dev._timer_cb()
        self._run_pending_callbacks()
        self.assertEqual(self.events, [TagFlags.REMOVED])
        self.assertEqual(self._commands_sent(), b"p")
        self.assertEqual(self.dev._RfidDev__state, RfidDevState.POLLING_ONCE)

    def test_timer_runs_in_the_event_loop(self):
        self.dev._start_timer()
        self.assertIsInstance(self.dev._RfidDev__polling_timer, asyncio.Handle)
