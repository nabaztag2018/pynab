from django.test import TestCase, Client
from django.http import JsonResponse
from nabtaichid.models import Config
import datetime


class TestView(TestCase):
    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get("/nabtaichid/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabtaichid/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.taichi_frequency, 30)
        self.assertEqual(config.next_taichi, None)

    def test_set_frequency(self):
        c = Client()
        response = c.post("/nabtaichid/settings", {"taichi_frequency": 10})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabtaichid/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.taichi_frequency, 10)
        self.assertEqual(config.next_taichi, None)

    def test_taichi_now(self):
        c = Client()
        response = c.put("/nabtaichid/settings")
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertEqual(response_json["status"], "ok")
        config = Config.load()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertTrue(config.next_taichi < now)
        self.assertTrue(
            config.next_taichi > now - datetime.timedelta(seconds=15)
        )

    def test_get_rfid_data(self):
        c = Client()
        response = c.get("/nabtaichid/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabtaichid/rfid-data.html"
        )

    def test_post_rfid_data(self):
        c = Client()
        response = c.post("/nabtaichid/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(response.content, b'{"data": ""}')
