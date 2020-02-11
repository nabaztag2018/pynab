from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from .models import Config
from .nabtaichid import NabTaichid
import datetime


class SettingsView(TemplateView):
    template_name = "nabtaichid/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        config.taichi_frequency = int(request.POST["taichi_frequency"])
        config.save()
        NabTaichid.signal_daemon()
        context = super().get_context_data(**kwargs)
        context["config"] = config
        return render(request, SettingsView.template_name, context=context)

    def put(self, request, *args, **kwargs):
        config = Config.load()
        config.next_taichi = datetime.datetime.now(datetime.timezone.utc)
        config.save()
        NabTaichid.signal_daemon()
        return JsonResponse({"status": "ok"})


class RFIDDataView(TemplateView):
    template_name = "nabtaichid/rfid-data.html"

    def get(self, request, *args, **kwargs):
        """
        Unserialize RFID application data
        """
        return render(request, RFIDDataView.template_name)

    def post(self, request, *args, **kwargs):
        """
        Serialize RFID application data
        """
        return JsonResponse({"data": ""})
