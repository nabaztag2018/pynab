from django.views.generic import View
from django.shortcuts import render
from django.utils import translation
from django.conf import settings
from nabd.i18n import Config
from django.utils.translation import to_locale, to_language

class NabWebView(View):
  template_name = 'nabweb/index.html'

  def get_locales(self):
    return [(to_locale(lang), name) for (lang, name) in settings.LANGUAGES]

  def get(self, request, *args, **kwargs):
    user_locale = Config.load().locale
    user_language = to_language(user_locale)
    translation.activate(user_language)
    self.request.session[translation.LANGUAGE_SESSION_KEY] = user_language
    locales = self.get_locales()
    return render(request, NabWebView.template_name, context={'current_locale': user_locale, 'locales': locales})

  def post(self, request, *args, **kwargs):
    config = Config.load()
    config.locale = request.POST['locale']
    config.save()
    locales = self.get_locales()
    return render(request, NabWebView.template_name, context={'current_locale': config.locale, 'locales': locales})
