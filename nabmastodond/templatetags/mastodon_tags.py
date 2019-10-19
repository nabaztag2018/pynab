from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def to_profile_url(value):
    [username, instance] = value.split('@')
    return 'https://' + instance + '/@' + username
