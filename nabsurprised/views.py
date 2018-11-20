from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from .models import Config
from .nabsurprised import NabSurprised
import datetime

class SettingsView(TemplateView):
  template_name = "nabsurprised/settings.html"

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['config'] = Config.load()
    return context

  def post(self, request, *args, **kwargs):
    config = Config.load()
    config.surprise_frequency = int(request.POST['surprise_frequency'])
    config.save()
    NabSurprised.signal_daemon()
    context = super().get_context_data(**kwargs)
    context['config'] = config
    return render(request, SettingsView.template_name, context=context)

  def put(self, request, *args, **kwargs):
    config = Config.load()
    config.next_surprise = datetime.datetime.now(datetime.timezone.utc)
    config.save()
    NabSurprised.signal_daemon()
    return JsonResponse({'status': 'ok'})
