from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from . import rfid_data
from .models import Config
from .nab8balld import Nab8Balld


class SettingsView(TemplateView):
    template_name = "nab8balld/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        config.enabled = request.POST["enabled"] == "true"
        config.save()
        Nab8Balld.signal_daemon()
        context = super().get_context_data(**kwargs)
        context["config"] = config
        return render(request, SettingsView.template_name, context=context)


class RFIDDataView(TemplateView):
    template_name = "nab8balld/rfid-data.html"

    def get(self, request, *args, **kwargs):
        """
        Unserialize RFID application data
        """
        lang = "default"
        data = request.GET.get("data", None)
        if data:
            lang = rfid_data.unserialize(data.encode("utf8"))
        context = self.get_context_data(**kwargs)
        context["lang"] = lang
        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):
        """
        Serialize RFID application data
        """
        lang = "default"
        if "lang" in request.POST:
            lang = request.POST["lang"]
        data = rfid_data.serialize(lang)
        data = data.decode("utf8")
        return JsonResponse({"data": data})
