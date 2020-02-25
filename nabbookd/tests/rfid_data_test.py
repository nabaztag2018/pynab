from unittest import TestCase
from nabbookd.rfid_data import serialize, unserialize


class TestSerialize(TestCase):
    def test_serialize_empty(self):
        serialized = serialize("", "")
        self.assertEqual(b"", serialized)
        serialized = serialize("", "1234567890123")
        self.assertEqual(b"", serialized)

    def test_serialize_valid(self):
        serialized = serialize("default", "1234567890123")
        self.assertEqual(b"default/1234567890123", serialized)
        serialized = serialize("nabaztag", "1234567890")
        self.assertEqual(b"nabaztag/1234567890", serialized)

    def test_serialize_invalid_isbn(self):
        serialized = serialize("default", "123456789")
        self.assertEqual(b"", serialized)
        serialized = serialize("default", "123456789012")
        self.assertEqual(b"", serialized)
        serialized = serialize("default", "123456789012a")
        self.assertEqual(b"", serialized)

    def test_serialize_invalid_voice(self):
        serialized = serialize("/", "1234567890123")
        self.assertEqual(b"", serialized)
        serialized = serialize(".", "1234567890123")
        self.assertEqual(b"", serialized)
        serialized = serialize("", "1234567890123")
        self.assertEqual(b"", serialized)


class TestUnserialize(TestCase):
    def test_unserialize_empty(self):
        unserialized = unserialize(b"")
        self.assertEqual(None, unserialized)

    def test_unserialize_valid(self):
        unserialized = unserialize(b"default/1234567890123")
        self.assertEqual(("default", "1234567890123"), unserialized)
        unserialized = unserialize(b"default/1234567890")
        self.assertEqual(("default", "1234567890"), unserialized)

    def test_unserialize_invalid_isbn(self):
        unserialized = unserialize(b"default/123456789")
        self.assertEqual(None, unserialized)
        unserialized = unserialize(b"default/123456789012")
        self.assertEqual(None, unserialized)
        unserialized = unserialize(b"default/123456789012a")
        self.assertEqual(None, unserialized)

    def test_unserialize_invalid_voice(self):
        unserialized = unserialize(b"1234567890123")
        self.assertEqual(None, unserialized)
        unserialized = unserialize(b"./1234567890123")
        self.assertEqual(None, unserialized)
        unserialized = unserialize(b"/1234567890123")
        self.assertEqual(None, unserialized)
        unserialized = unserialize(b"//1234567890123")
        self.assertEqual(None, unserialized)
