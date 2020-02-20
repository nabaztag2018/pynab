import asyncio
import unittest
import pytest
from nabd.resources import Resources
from nabd.i18n import Config
from nabd.choreography import ChoreographyInterpreter
from nabd.tests.utils import close_old_async_connections


@pytest.mark.django_db(transaction=True)
class TestResources(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        close_old_async_connections()

    def test_find_existing(self):
        task = self.loop.create_task(
            Resources.find("choreographies", "nabtaichid/taichi.chor")
        )
        path = self.loop.run_until_complete(task)
        self.assertTrue(len(path.read_bytes()) > 1024)

    def test_find_not_existing(self):
        task = self.loop.create_task(
            Resources.find("choreographies", "xy/zp.chor")
        )
        path = self.loop.run_until_complete(task)
        self.assertEqual(path, None)

    def test_find_localized(self):
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/0/1.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)

    def test_find_localized_non_existing(self):
        config = Config()
        config.locale = "tlh_TLH"
        config.save()
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/0/1.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertEqual(path, None)

    def test_find_random_localized(self):
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/0/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)
        task = self.loop.create_task(
            Resources.find("sounds", "nabsurprised/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)

    def test_find_random_semi_colon_localized(self):
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/0/*.mp3;nabclockd/1/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/z/*.mp3;nabclockd/1/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)
        task = self.loop.create_task(
            Resources.find("sounds", "nabclockd/z/*.mp3;nabclockd/y/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertEqual(path, None)

    def test_find_random_not_localized(self):
        task = self.loop.create_task(
            Resources.find("sounds", "nabsurprised/respirations/*.mp3")
        )
        path = self.loop.run_until_complete(task)
        self.assertNotEqual(path, None)

    def test_find_midi_list(self):
        for midi in ChoreographyInterpreter.MIDI_LIST:
            task = self.loop.create_task(Resources.find("sounds", midi))
            path = self.loop.run_until_complete(task)
            self.assertNotEqual(path, None)
