from unittest import TestCase
from nabd.rfid_dev import RfidDev


class TestResources(TestCase):
    def test_is_compatible(self):
        self.assertTrue(
            RfidDev.is_compatible(b'\xD0\x02\x0C\xC1\x1E\xCB\x0D\x02')
        )
        self.assertTrue(
            RfidDev.is_compatible(b'\xD0\x02\x18\xBD\x6E\x56\x8A\xE6')
        )
        self.assertTrue(
            RfidDev.is_compatible(b'\xD0\x02\x30\xD6\x44\x8D\x6A\x5A')
        )
        self.assertFalse(
            RfidDev.is_compatible(b'\xE0\x01\x02\x03\x04\x05\x06\x07')
        )
        self.assertFalse(
            RfidDev.is_compatible(b'\xD0\x01\x02\x03\x04\x05\x06\x07')
        )
        self.assertFalse(
            RfidDev.is_compatible(b'\xD0\x02\x02\x03\x04\x05\x06\x07')
        )
