from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from .models import Config
from .nabrfid2server import NabRfid2server


class SettingsView(TemplateView):
    template_name = "nabrfid2server/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        config.rfid_2_server_test = (
            request.POST["rfid_2_server_test"] == "true"
        )
        config.rfid_2_server_mode = int(request.POST["rfid_2_server_mode"])
        config.rfid_2_server_url = request.POST["rfid_2_server_url"]
        config.save()
        NabRfid2server.signal_daemon()
        context = super().get_context_data(**kwargs)
        context["config"] = config
        return render(request, SettingsView.template_name, context=context)

    def put(self, request, *args, **kwargs):
        config = Config.load()
        config.save()
        NabRfid2server.signal_daemon()
        return JsonResponse({"status": "ok"})
