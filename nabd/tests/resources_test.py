import unittest
import pytest
from nabd.resources import Resources
from nabd.i18n import Config
from nabd.choreography import ChoreographyInterpreter


@pytest.mark.django_db
class TestResources(unittest.TestCase):
    def test_find_existing(self):
        path = Resources.find("choreographies", "nabtaichid/taichi.chor")
        self.assertTrue(len(path.read_bytes()) > 1024)

    def test_find_not_existing(self):
        path = Resources.find("choreographies", "xy/zp.chor")
        self.assertEqual(path, None)

    def test_find_localized(self):
        path = Resources.find("sounds", "nabclockd/0/1.mp3")
        print(path)
        self.assertNotEqual(path, None)

    def test_find_localized_non_existing(self):
        config = Config()
        config.locale = "tlh_TLH"
        path = Resources.find("sounds", "nabclockd/0/1.mp3")
        self.assertEqual(None, None)

    def test_find_random_localized(self):
        path = Resources.find("sounds", "nabclockd/0/*.mp3")
        self.assertNotEqual(path, None)
        path = Resources.find("sounds", "nabsurprised/*.mp3")
        self.assertNotEqual(path, None)

    def test_find_random_not_localized(self):
        path = Resources.find("sounds", "nabsurprised/respirations/*.mp3")
        print(path)
        self.assertNotEqual(path, None)

    def test_find_midi_list(self):
        for midi in ChoreographyInterpreter.MIDI_LIST:
            path = Resources.find("sounds", midi)
            self.assertNotEqual(path, None)
