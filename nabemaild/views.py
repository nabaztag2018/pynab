from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from . import rfid_data
from .models import Config
from .nabemaild import NabEmaild


class SettingsView(TemplateView):
    template_name = "nabemaild/settings.html"

    def get_context_data(self, **kwargs):
        # on charge les donnees depuis la base de données
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        # quand on reçoit une nouvelle config (via interface)
        config = Config.load()
        if "gmail_account" in request.POST:
            config.gmail_account = request.POST["gmail_account"]
        if "gmail_passwd" in request.POST:
            config.gmail_passwd = request.POST["gmail_passwd"]
        config.save()
        NabEmaild.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)


class RFIDDataView(TemplateView):
    template_name = "nabemaild/rfid-data.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        uid = request.GET.get("uid", None)

        email, subject = rfid_data.read_data_ui_for_views(uid)

        context["nabemaild_email"] = email
        context["nabemaild_subject"] = subject
        context["nabemaild_uid"] = uid

        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):

        if "nabemaild_email" in request.POST:
            email = request.POST["nabemaild_email"]

        if "nabemaild_subject" in request.POST:
            subject = request.POST["nabemaild_subject"]

        if "nabemaild_uid" in request.POST:
            uid = request.POST["nabemaild_uid"]

        rfid_data.write_data_ui_for_views(uid, email, subject)

        data = "DATA_IN_LOCAL_DB"
        return JsonResponse({"data": data})
