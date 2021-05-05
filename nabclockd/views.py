import os

from django.shortcuts import render
from django.views.generic import TemplateView
from pytz import common_timezones

from .models import Config
from .nabclockd import NabClockd


class SettingsView(TemplateView):
    template_name = "nabclockd/settings.html"
    daysOfTheWeek = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        context["timezones"] = common_timezones
        context["current_timezone"] = self.get_system_tz()
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        if "chime_hour" in request.POST:
            config.chime_hour = request.POST["chime_hour"] == "true"
        if "wakeup_time" in request.POST:
            (hour, min) = self.parse_time(request.POST["wakeup_time"])
            config.wakeup_hour = hour
            config.wakeup_min = min
        if "sleep_time" in request.POST:
            (hour, min) = self.parse_time(request.POST["sleep_time"])
            config.sleep_hour = hour
            config.sleep_min = min
        for dayName in SettingsView.daysOfTheWeek:
            if ("wakeup_time_" + dayName) in request.POST:
                (hour, min) = self.parse_time(
                    request.POST["wakeup_time_" + dayName]
                )
                setattr(config, "wakeup_hour_" + dayName, hour)
                setattr(config, "wakeup_min_" + dayName, min)
            if ("sleep_time_" + dayName) in request.POST:
                (hour, min) = self.parse_time(
                    request.POST["sleep_time_" + dayName]
                )
                setattr(config, "sleep_hour_" + dayName, hour)
                setattr(config, "sleep_min_" + dayName, min)
        if "timezone" in request.POST:
            selected_tz = request.POST["timezone"]
            if selected_tz in common_timezones:
                self.set_system_tz(selected_tz)
        if "play_wakeup_sleep_sounds" in request.POST:
            config.play_wakeup_sleep_sounds = (
                request.POST["play_wakeup_sleep_sounds"] == "true"
            )
        if "settings_per_day" in request.POST:
            config.settings_per_day = (
                request.POST["settings_per_day"] == "true"
            )
        config.save()
        NabClockd.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)

    def parse_time(self, hour_str):
        [hour_str, min_str] = hour_str.split(":")
        return (int(hour_str), int(min_str))

    def get_system_tz(self):
        with open("/etc/timezone") as w:
            return w.read().strip()

    def set_system_tz(self, tz):
        if tz != self.get_system_tz():
            with open("/etc/timezone", "w") as w:
                w.write("%s\n" % tz)
                os.system(
                    f"/bin/ln -fs /usr/share/zoneinfo/{tz} /etc/localtime"
                )
