from django.test import TestCase, Client
from nabweatherd.models import Config
import datetime

class TestView(TestCase):
    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get('/nabweatherd/settings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'nabweatherd/settings.html')
        self.assertTrue('config' in response.context)
        config = Config.load()
        self.assertEqual(response.context['config'], config)
        self.assertEqual(config.location, None)
        self.assertEqual(config.unit, 1)
        self.assertEqual(config.next_performance_date, None)

    def test_set_unit(self):
        c = Client()
        response = c.post('/nabweatherd/settings', {'unit': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'nabweatherd/settings.html')
        self.assertTrue('config' in response.context)
        config = Config.load()
        self.assertEqual(response.context['config'], config)
        self.assertEqual(config.unit, 2)
        self.assertEqual(config.next_performance_date, None)
        self.assertEqual(config.next_performance_type, None)

    def test_set_location(self):
        c = Client()
        response = c.post('/nabweatherd/settings', {'location': '75005'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'nabweatherd/settings.html')
        self.assertTrue('config' in response.context)
        config = Config.load()
        self.assertEqual(response.context['config'], config)
        self.assertEqual(config.location, '75005')
        self.assertEqual(config.next_performance_date, None)
        self.assertEqual(config.next_performance_type, None)

    def test_forecast_today(self):
        c = Client()
        response = c.put('/nabweatherd/settings', 'type=today')
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue('status' in response_json)
        self.assertEqual(response_json['status'], 'ok')
        config = Config.load()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertTrue(config.next_performance_date < now)
        self.assertTrue(config.next_performance_date > now - datetime.timedelta(seconds=15))
        self.assertEqual(config.next_performance_type, 'today')

    def test_forecast_tomorrow(self):
        c = Client()
        response = c.put('/nabweatherd/settings', 'type=tomorrow')
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue('status' in response_json)
        self.assertEqual(response_json['status'], 'ok')
        config = Config.load()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertTrue(config.next_performance_date < now)
        self.assertTrue(config.next_performance_date > now - datetime.timedelta(seconds=15))
        self.assertEqual(config.next_performance_type, 'tomorrow')
