from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils.translation import ugettext as _
from .models import Config
from .nabairqualityd import NabAirqualityd
import datetime


class SettingsView(TemplateView):
    template_name = "nabairqualityd/settings.html"

    def get_context_data(self, **kwargs):
        # on charge les donnees depuis la base de données
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context

    def post(self, request, *args, **kwargs):
        # quand on reçoit une nouvelle config (via interface)
        config = Config.load()
        if "index_airquality" in request.POST:
            index_airquality = request.POST["index_airquality"]
            config.index_airquality = index_airquality
        if "visual_airquality" in request.POST:
            visual_airquality = request.POST["visual_airquality"]
            config.visual_airquality = visual_airquality
        config.save()
        NabAirqualityd.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)

    def put(self, request, *args, **kwargs):
        # quand on clique sur le bouton de l'intervaface pour jouer tout de suite
        config = Config.load()
        config.next_performance_date = datetime.datetime.now(
            datetime.timezone.utc
        )
        config.next_performance_type = "today"
        config.save()
        NabAirqualityd.signal_daemon()
        return JsonResponse({"status": "ok"})
