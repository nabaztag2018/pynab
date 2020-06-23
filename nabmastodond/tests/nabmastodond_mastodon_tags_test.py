from django.test import SimpleTestCase
from django.template import Context, Template


class ToProfileUrl1AtTagTest(SimpleTestCase):
    def test_rendered(self):
        context = Context()
        template_to_render = Template(
            "{% load mastodon_tags %}"
            '{{ "name@instance.tld" | to_profile_url }}'
        )
        rendered_template = template_to_render.render(context)
        self.assertEqual("https://instance.tld/@name", rendered_template)


class ToProfileUrl2AtTagTest(SimpleTestCase):
    def test_rendered(self):
        context = Context()
        template_to_render = Template(
            "{% load mastodon_tags %}"
            '{{ "@name@instance.tld" | to_profile_url }}'
        )
        rendered_template = template_to_render.render(context)
        self.assertEqual("https://instance.tld/@name", rendered_template)


class ToProfileUrl3AtTagTest(SimpleTestCase):
    def test_rendered(self):
        with self.assertRaises(ValueError):
            context = Context()
            template_to_render = Template(
                "{% load mastodon_tags %}"
                '{{ "@name@instance.tld@" | to_profile_url }}'
            )
            rendered_template = template_to_render.render(context)
            self.assertEqual("https://instance.tld/@name", rendered_template)
