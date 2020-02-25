from django.test import TestCase, Client
from django.http import JsonResponse
import datetime


class TestView(TestCase):
    def test_get_settings(self):
        c = Client()
        response = c.get("/nabbookd/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabbookd/settings.html")


class TestRFIDView(TestCase):
    def test_get_rfid_data(self):
        c = Client()
        response = c.get("/nabbookd/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabbookd/rfid-data.html")
        self.assertTrue("books" in response.context)
        # At least La Belle Lisse Poire
        self.assertGreaterEqual(len(response.context["books"]), 1)
        la_belle_lisse_poire = None
        for book_item in response.context["books"]:
            if book_item["isbn"] == "9782070548064":
                la_belle_lisse_poire = book_item
                break
        self.assertNotEqual(la_belle_lisse_poire, None)
        self.assertEqual(
            la_belle_lisse_poire["title"],
            "La belle lisse poire du prince de Motordu",
        )
        self.assertGreaterEqual(len(la_belle_lisse_poire["voices"]), 1)
        default_voice = None
        for voice in la_belle_lisse_poire["voices"]:
            if voice["id"] == "default":
                default_voice = voice
                break
        self.assertNotEqual(default_voice, None)
        self.assertTrue("description" in default_voice)
        self.assertEqual(default_voice["description"], "Voix par défaut")

    def test_get_rfid_data_empty(self):
        c = Client()
        response = c.get("/nabbookd/rfid-data?data=")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabbookd/rfid-data.html")

    def test_get_rfid_data_invalid(self):
        c = Client()
        response = c.get("/nabbookd/rfid-data?data=%00")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "nabbookd/rfid-data.html")

    def test_post_rfid_data(self):
        c = Client()
        response = c.post("/nabbookd/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(
            response.content, b'{"data": "default/9782070548064"}'
        )

    def test_post_rfid_data_param(self):
        c = Client()
        response = c.post(
            "/nabbookd/rfid-data",
            {"book": "9782092512593", "voice": "default", },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(
            response.content, b'{"data": "default/9782092512593"}'
        )

    def test_post_rfid_data_voice_data(self):
        c = Client()
        response = c.post(
            "/nabbookd/rfid-data",
            {"book": "9782070548064", "voice": "nabaztag", },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(
            response.content, b'{"data": "nabaztag/9782070548064"}'
        )
