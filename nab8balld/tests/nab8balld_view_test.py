from django.test import TestCase, Client
from nab8balld.models import Config
import datetime

class TestView(TestCase):
  def setUp(self):
    Config.reset_cache()
    Config.load()

  def test_get_settings(self):
    c = Client()
    response = c.get('/nab8balld/settings')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.templates[0].name, 'nab8balld/settings.html')
    self.assertTrue('config' in response.context)
    config = Config.load()
    self.assertEqual(response.context['config'], config)
    self.assertEqual(config.enabled, True)

  def test_set_frequency(self):
    c = Client()
    response = c.post('/nab8balld/settings', {'enabled': True})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.templates[0].name, 'nab8balld/settings.html')
    self.assertTrue('config' in response.context)
    config = Config.load()
    self.assertEqual(response.context['config'], config)
    self.assertEqual(config.enabled, True)
