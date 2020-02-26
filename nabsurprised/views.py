from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from .models import Config
from .nabsurprised import NabSurprised
from . import rfid_data
import datetime


class SettingsView(TemplateView):
    template_name = "nabsurprised/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        config.surprise_frequency = int(request.POST["surprise_frequency"])
        config.save()
        NabSurprised.signal_daemon()
        context = super().get_context_data(**kwargs)
        context["config"] = config
        return render(request, SettingsView.template_name, context=context)

    def put(self, request, *args, **kwargs):
        config = Config.load()
        config.next_surprise = datetime.datetime.now(datetime.timezone.utc)
        config.save()
        NabSurprised.signal_daemon()
        return JsonResponse({"status": "ok"})


class RFIDDataView(TemplateView):
    template_name = "nabsurprised/rfid-data.html"

    def get(self, request, *args, **kwargs):
        """
        Unserialize RFID application data
        """
        lang = "default"
        type = "surprise"
        data = request.GET.get("data", None)
        if data:
            lang, type = rfid_data.unserialize(data.encode("utf8"))
        context = self.get_context_data(**kwargs)
        context["lang"] = lang
        context["type"] = type
        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):
        """
        Serialize RFID application data
        """
        lang = "default"
        type = "surprise"
        if "type" in request.POST:
            type = request.POST["type"]
        if "lang" in request.POST:
            lang = request.POST["lang"]
        data = rfid_data.serialize(lang, type)
        data = data.decode("utf8")
        return JsonResponse({"data": data})
