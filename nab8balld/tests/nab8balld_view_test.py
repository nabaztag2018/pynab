from django.test import TestCase, Client
from nab8balld.models import Config
import datetime


class TestView(TestCase):
    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get("/nab8balld/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nab8balld/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.enabled, True)

    def test_toggle(self):
        c = Client()
        response = c.post("/nab8balld/settings", {"enabled": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nab8balld/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.enabled, False)
        response = c.post("/nab8balld/settings", {"enabled": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nab8balld/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.enabled, True)
