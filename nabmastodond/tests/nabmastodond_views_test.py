from django.test import TestCase, Client
from nabmastodond.models import Config
import datetime
from dateutil.tz import tzutc


class TestView(TestCase):
    def setUp(self):
        Config.load()

    def test_get_settings(self):
        c = Client()
        response = c.get("/nabmastodond/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabmastodond/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.client_id, None)
        self.assertEqual(config.client_secret, None)
        self.assertEqual(config.redirect_uri, None)
        self.assertEqual(config.access_token, None)
        self.assertEqual(config.username, None)
        self.assertEqual(config.display_name, None)
        self.assertEqual(config.avatar, None)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(config.spouse_left_ear_position, None)
        self.assertEqual(config.spouse_right_ear_position, None)
        self.assertEqual(config.last_processed_status_id, None)
        self.assertEqual(config.last_processed_status_date, None)

    def test_post_connect(self):
        c = Client()
        config = Config.load()
        config.client_id = "test_client_id"
        config.client_secret = "test_client_secret"
        config.save()

        response = c.post(
            "/nabmastodond/connect",
            {
                "location": "http://192.168.0.42/",
                "instance": "mastodon.social",
            },
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertTrue("request_url" in response_json)
        config = Config.load()
        self.assertEqual(config.instance, "mastodon.social")
        self.assertNotEqual(config.client_id, "test_client_id")
        self.assertNotEqual(config.client_secret, "test_client_secret")
        self.assertEqual(
            config.redirect_uri, "http://192.168.0.42/nabmastodond/oauthcb"
        )
        ms1_client_id = config.client_id
        ms1_client_secret = config.client_secret

        response = c.post(
            "/nabmastodond/connect",
            {
                "location": "http://192.168.0.42/",
                "instance": "mastodon.social",
            },
        )
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertTrue("request_url" in response_json)
        config = Config.load()
        self.assertEqual(config.instance, "mastodon.social")
        self.assertEqual(config.client_id, ms1_client_id)
        self.assertEqual(config.client_secret, ms1_client_secret)
        self.assertEqual(
            config.redirect_uri, "http://192.168.0.42/nabmastodond/oauthcb"
        )

        response = c.post(
            "/nabmastodond/connect",
            {"location": "http://10.10.10.42/", "instance": "mastodon.social"},
        )
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertTrue("request_url" in response_json)
        config = Config.load()
        self.assertEqual(config.instance, "mastodon.social")
        self.assertNotEqual(config.client_id, ms1_client_id)
        self.assertNotEqual(config.client_secret, ms1_client_secret)
        self.assertEqual(
            config.redirect_uri, "http://10.10.10.42/nabmastodond/oauthcb"
        )
        ms2_client_id = config.client_id
        ms2_client_secret = config.client_secret

        response = c.post(
            "/nabmastodond/connect",
            {"location": "http://10.10.10.42/", "instance": "mstdn.fr"},
        )
        response_json = response.json()
        self.assertTrue("status" in response_json)
        self.assertTrue("request_url" in response_json)
        config = Config.load()
        self.assertNotEqual(config.client_id, ms2_client_id)
        self.assertNotEqual(config.client_secret, ms2_client_secret)
        self.assertEqual(
            config.redirect_uri, "http://10.10.10.42/nabmastodond/oauthcb"
        )

    def test_delete_connect(self):
        c = Client()
        config = Config.load()
        config.client_id = "test_client_id"
        config.client_secret = "test_client_secret"
        config.redirect_uri = "test_redirect_uri"
        config.access_token = "test_access_token"
        config.username = "test_username"
        config.display_name = "test_display_name"
        config.avatar = "test_avatar"
        config.spouse_handle = "test_spouse_handle"
        config.spouse_pairing_state = "spouse_pairing_state"
        config.spouse_pairing_date = datetime.datetime(
            2018, 11, 11, 11, 11, 11, tzinfo=tzutc()
        )
        config.spouse_left_ear_position = 3
        config.spouse_right_ear_position = 5
        config.last_processed_status_id = 42
        config.last_processed_status_date = datetime.datetime(
            2018, 11, 11, 11, 11, 0, tzinfo=tzutc()
        )
        config.save()
        response = c.delete("/nabmastodond/connect")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.templates[0].name, "nabmastodond/settings.html"
        )
        self.assertTrue("config" in response.context)
        config = Config.load()
        self.assertEqual(response.context["config"], config)
        self.assertEqual(config.client_id, "test_client_id")
        self.assertEqual(config.client_secret, "test_client_secret")
        self.assertEqual(config.redirect_uri, "test_redirect_uri")
        self.assertEqual(config.access_token, None)
        self.assertEqual(config.username, None)
        self.assertEqual(config.display_name, None)
        self.assertEqual(config.avatar, None)
        self.assertEqual(config.spouse_handle, None)
        self.assertEqual(config.spouse_pairing_state, None)
        self.assertEqual(config.spouse_pairing_date, None)
        self.assertEqual(config.spouse_left_ear_position, None)
        self.assertEqual(config.spouse_right_ear_position, None)
        self.assertEqual(config.last_processed_status_id, None)
        self.assertEqual(config.last_processed_status_date, None)
