import unittest
from nabd.resources import Resources
from nabd.choreography import ChoreographyInterpreter

class TestResources(unittest.TestCase):
  def test_find_existing(self):
    path = Resources.find('choreographies', 'nabtaichid/taichi.chor')
    self.assertTrue(len(path.read_bytes()) > 1024)

  def test_find_not_existing(self):
    path = Resources.find('choreographies', 'xy/zp.chor')
    self.assertEqual(path, None)

  def test_find_midi_list(self):
    for midi in ChoreographyInterpreter.MIDI_LIST:
      path = Resources.find('sounds', midi)
      self.assertNotEqual(path, None)
