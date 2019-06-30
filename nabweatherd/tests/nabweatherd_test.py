import unittest, asyncio, threading, json, django, time, datetime, signal, pytest
from nabweatherd.nabweatherd import NabWeatherd

class MockWriter(object):
  def __init__(self):
    self.written = []

  def write(self, packet):
    self.written.append(packet)

@pytest.mark.django_db
class TestNabWeatherd(unittest.TestCase):
  def test_perform(self):
    service = NabWeatherd()
    writer = MockWriter()
    service.writer = writer
    service.location = '75005'
    expiration = datetime.datetime(2019,4,22,0,0,0)
    service.perform(expiration, "today")
    self.assertEqual(len(writer.written), 2)
    packet = writer.written[0]
    packet_json = json.loads(packet.decode('utf8'))
    self.assertEqual(packet_json['type'], 'info')
    self.assertEqual(packet_json['info_id'], 'weather')
    self.assertTrue('animation' in packet_json)
    packet = writer.written[1]
    packet_json = json.loads(packet.decode('utf8'))
    self.assertEqual(packet_json['type'], 'message')
    self.assertTrue('signature' in packet_json)
    self.assertTrue('body' in packet_json)

  def test_aliases(self):
    service = NabWeatherd()
    weather_class = service.normalize_weather_class('J_W1_0-N_4')
    self.assertEqual(weather_class, 'J_W1_0-N_1')
    weather_class = service.normalize_weather_class('J_W1_0-N_1')
    self.assertEqual(weather_class, 'J_W1_0-N_1')
    weather_class = service.normalize_weather_class('J_W2_4-N_1')
    self.assertEqual(weather_class, 'J_W1_3-N_0')
