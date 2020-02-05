from django.utils.translation import gettext as _
from django import template

register = template.Library()


@register.filter
def duration(seconds):
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    if hours == 0 and minutes == 0:
        return _("less than one minute")
    if hours == 0 and minutes == 1:
        return _("1 minute")
    if hours == 0 and minutes > 1:
        return _("{} minutes").format(minutes)
    if hours == 1 and minutes == 0:
        return _("1 hour")
    if hours == 1 and minutes == 1:
        return _("1 hour and 1 minute")
    if hours == 1:
        return _("1 hour and {} minutes").format(minutes)
    if minutes == 0:
        return _("{} hours").format(hours)
    if minutes == 1:
        return _("{} hours and 1 minute").format(hours)
    return _("{} hours and {} minutes").format(hours, minutes)
