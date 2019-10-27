from django.shortcuts import render
from django.views.generic import TemplateView
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
