import unittest
import asyncio
import sys
import platform
import pytest
import os


@pytest.mark.skipif(
    sys.platform != "linux"
    or "arm" not in platform.machine()
    or "CI" in os.environ,
    reason="HW test only makes sense on a physical Nabaztag",
)
class TestNabIOHW(unittest.TestCase):
    def setUp(self):
        from nabd.nabio_hw import NabIOHW

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.nabio = NabIOHW()

    def test_ears(self):
        setup_task = self.loop.create_task(self.nabio.setup_ears(4, 12))
        self.loop.run_until_complete(setup_task)
        self.assertEqual(setup_task.exception(), None)
        move_task = self.loop.create_task(self.nabio.move_ears(11, 5))
        self.loop.run_until_complete(move_task)
        self.assertEqual(move_task.exception(), None)
        detect_task = self.loop.create_task(self.nabio.detect_ears_positions())
        self.loop.run_until_complete(detect_task)
        self.assertEqual(detect_task.exception(), None)
        self.assertEqual(detect_task.result(), (11, 5))
