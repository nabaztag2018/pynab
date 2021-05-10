import datetime

from django.http import JsonResponse
from django.test import Client, TestCase

from nabweatherd.models import Config


class TestView(TestCase):
    NYC_LOCATION_JSON = (
        '{"insee":"","name":"New York City",'
        '"lat":40.71427,"lon":-74.00597,"country":"US",'
        '"admin":"New York","admin2":"","postCode":""}'
    )

    PARIS_LOCATION_JSON = (
        '{"insee":"75056","name":"Paris 14",'
        '"lat":48.8331,"lon":2.3264,"country":"FR",'
        '"admin":"Île-de-France","admin2":"75",'
        '"postCode":"75014"}'
    )

    PARIS_LOCATION_USERFRIENDLY = "Paris 14 - Île-de-France (75) - FR"

    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get("/nabweatherd/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweatherd/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.location, TestView.PARIS_LOCATION_JSON)
        self.assertEqual(
            config.location_user_friendly, TestView.PARIS_LOCATION_USERFRIENDLY
        )
        self.assertEqual(config.unit, 1)
        self.assertEqual(config.next_performance_date, None)

    def test_set_unit(self):
        c = Client()
        response = c.post("/nabweatherd/settings", {"unit": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweatherd/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.unit, 2)
        self.assertEqual(config.next_performance_date, None)
        self.assertEqual(config.next_performance_type, None)

    def test_set_location(self):
        c = Client()
        response = c.post(
            "/nabweatherd/settings", {"location": TestView.NYC_LOCATION_JSON}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweatherd/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.location, TestView.NYC_LOCATION_JSON)
        self.assertEqual(
            config.location_user_friendly, "New York City - New York - US"
        )
        self.assertEqual(config.next_performance_date, None)
        self.assertEqual(config.next_performance_type, None)

    def test_forecast_today(self):
        c = Client()
        response = c.put("/nabweatherd/settings", "type=today")
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertEqual(response_json["status"], "ok")
        config = Config.load()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertTrue(config.next_performance_date < now)
        self.assertTrue(
            config.next_performance_date > now - datetime.timedelta(seconds=15)
        )
        self.assertEqual(config.next_performance_type, "today")

    def test_forecast_tomorrow(self):
        c = Client()
        response = c.put("/nabweatherd/settings", "type=tomorrow")
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertEqual(response_json["status"], "ok")
        config = Config.load()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertTrue(config.next_performance_date < now)
        self.assertTrue(
            config.next_performance_date > now - datetime.timedelta(seconds=15)
        )
        self.assertEqual(config.next_performance_type, "tomorrow")

    def test_get_rfid_data(self):
        c = Client()
        response = c.get("/nabweatherd/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweatherd/rfid-data.html"
        )
        self.assertEqual(response.context["type"], "today")

    def test_get_rfid_data_param(self):
        c = Client()
        response = c.get("/nabweatherd/rfid-data?data=%02")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabweatherd/rfid-data.html"
        )
        self.assertEqual(response.context["type"], "tomorrow")

    def test_post_rfid_data(self):
        c = Client()
        response = c.post("/nabweatherd/rfid-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(response.content, b'{"data": "\\u0001"}')

    def test_post_rfid_data_param(self):
        c = Client()
        response = c.post("/nabweatherd/rfid-data", {"type": "tomorrow"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, JsonResponse))
        self.assertEqual(response.content, b'{"data": "\\u0002"}')
