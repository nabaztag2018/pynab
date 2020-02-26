import os
import pytest
from django.test import TestCase, Client
from nabclockd.models import Config


@pytest.mark.skipif(
    not os.path.isfile("/etc/timezone"),
    reason="Test requires /etc/timezone to exist",
)
class TestView(TestCase):
    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get("/nabclockd/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabclockd/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.chime_hour, True)
        self.assertEqual(config.wakeup_hour, 7)
        self.assertEqual(config.wakeup_min, 0)
        self.assertEqual(config.sleep_hour, 22)
        self.assertEqual(config.sleep_min, 0)

    def test_set_chime_hour(self):
        c = Client()
        response = c.post("/nabclockd/settings", {"chime_hour": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabclockd/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.chime_hour, False)
        self.assertEqual(config.wakeup_hour, 7)
        self.assertEqual(config.wakeup_min, 0)
        self.assertEqual(config.sleep_hour, 22)
        self.assertEqual(config.sleep_min, 0)

    def test_set_wakeup_time(self):
        c = Client()
        response = c.post("/nabclockd/settings", {"wakeup_time": "09:42"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabclockd/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.chime_hour, True)
        self.assertEqual(config.wakeup_hour, 9)
        self.assertEqual(config.wakeup_min, 42)
        self.assertEqual(config.sleep_hour, 22)
        self.assertEqual(config.sleep_min, 0)

    def test_set_sleep_time(self):
        c = Client()
        response = c.post("/nabclockd/settings", {"sleep_time": "21:21"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabclockd/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.chime_hour, True)
        self.assertEqual(config.wakeup_hour, 7)
        self.assertEqual(config.wakeup_min, 0)
        self.assertEqual(config.sleep_hour, 21)
        self.assertEqual(config.sleep_min, 21)

    def test_set_all(self):
        c = Client()
        response = c.post(
            "/nabclockd/settings",
            {
                "chime_hour": "false",
                "wakeup_time": "09:42",
                "sleep_time": "21:21",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabclockd/settings.html")
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.chime_hour, False)
        self.assertEqual(config.wakeup_hour, 9)
        self.assertEqual(config.wakeup_min, 42)
        self.assertEqual(config.sleep_hour, 21)
        self.assertEqual(config.sleep_min, 21)
