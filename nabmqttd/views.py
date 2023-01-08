import json
from urllib.parse import urlparse, urlunparse

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View
# from mqtt import (  # type: ignore
#     mqtt,
#     mqttError,
#     mqttUnauthorizedError,
# )

from .models import Config
from .nabmqttd import Nabmqttd


def reset_access_token(config):
    config.access_token = None
    config.username = None
    config.last_processed_status_id = None
    config.last_processed_status_date = None
    config.save()


class SettingsView(TemplateView):
    template_name = "nabmqttd/settings.html"

    def get_context_data(self, **kwargs):
        # on charge les donnees depuis la base de données
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        # quand on reçoit une nouvelle config (via interface)
        config = Config.load()
        if "mqtt_host" in request.POST:
            config.mqtt_host = request.POST["mqtt_host"]
        if "mqtt_port" in request.POST:
            config.mqtt_port = request.POST["mqtt_port"]
        if "mqtt_user" in request.POST:
            config.mqtt_user = request.POST["mqtt_user"]
        if "mqtt_pw" in request.POST:
            config.mqtt_pw = request.POST["mqtt_pw"]
        if "mqtt_topic" in request.POST:
            config.mqtt_topic = request.POST["mqtt_topic"]
        config.save()
        Nabmqttd.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)







