from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def to_profile_url(value):
    username = ""
    instance = ""
    parts = value.split("@")
    if len(parts) == 2:
        username = parts[0]
        instance = parts[1]
    elif len(parts) == 3 and parts[0] == "":
        username = parts[1]
        instance = parts[2]
    else:
        raise ValueError(
            'Invalid Mastodon identifier "'
            + value
            + '". Should be "name@instance.tld" or "@name@instance.tld"'
        )

    return "https://" + instance + "/@" + username
