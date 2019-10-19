import unittest
import asyncio
import threading
import json
import django
import time
import datetime
import signal
import pytest
from nabsurprised.nabsurprised import NabSurprised


class MockWriter(object):
    def __init__(self):
        self.written = []

    def write(self, packet):
        self.written.append(packet)


@pytest.mark.django_db
class TestNabSurprised(unittest.TestCase):
    def test_perform(self):
        service = NabSurprised()
        writer = MockWriter()
        service.writer = writer
        expiration = datetime.datetime(2018, 11, 1, 0, 0, 0)
        service.perform(expiration, None)
        self.assertEqual(len(writer.written), 1)
        packet = writer.written[0]
        packet_json = json.loads(packet.decode('utf8'))
        self.assertEqual(packet_json['type'], 'message')
        self.assertTrue('signature' in packet_json)
        self.assertTrue('body' in packet_json)
