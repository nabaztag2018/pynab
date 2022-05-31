from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from . import rfid_data
from .models import Config
from .nabiftttd import NabIftttd


class SettingsView(TemplateView):
    template_name = "nabiftttd/settings.html"

    def get_context_data(self, **kwargs):
        # on charge les donnees depuis la base de données
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        # quand on reçoit une nouvelle config (via interface)
        config = Config.load()
        if "ifttt_key" in request.POST:
            config.ifttt_key = request.POST["ifttt_key"]
        config.save()
        NabIftttd.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)


class RFIDDataView(TemplateView):
    template_name = "nabiftttd/rfid-data.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        uid = request.GET.get("uid", None)

        event_name = rfid_data.read_data_ui_for_views(uid)

        context["event_name"] = event_name
        context["ifttt_uid"] = uid

        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):

        data = "DATA_IN_LOCAL_DB"

        if "ifttt_uid" in request.POST:
            uid = request.POST["ifttt_uid"]
        if "event_name" in request.POST:
            event_name = request.POST["event_name"]
            event_name = event_name.replace(" ", "_")
        else:
            event_name = uid

        rfid_data.write_data_ui_for_views(uid, event_name)

        return JsonResponse({"data": data})
