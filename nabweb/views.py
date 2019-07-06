from django.views.generic import View
from django.shortcuts import render
from django.utils import translation
from django.conf import settings
from django.http import JsonResponse
from nabd.i18n import Config
from django.utils.translation import to_locale, to_language
import os

class NabWebView(View):
  template_name = 'nabweb/index.html'

  def get_locales(self):
    config = Config.load()
    return [(to_locale(lang), name, to_locale(lang) == config.locale) for (lang, name) in settings.LANGUAGES]

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
    user_language = to_language(config.locale)
    translation.activate(user_language)
    self.request.session[translation.LANGUAGE_SESSION_KEY] = user_language
    locales = self.get_locales()
    return render(request, NabWebView.template_name, context={'current_locale': config.locale, 'locales': locales})

class NabWebUpgradeView(View):
  def get(self, request, *args, **kwargs):
    root_dir=os.popen("sed -nE -e 's|WorkingDirectory=(.+)|\\1|p' < /lib/systemd/system/nabd.service").read().rstrip()
    if root_dir == '':
      return JsonResponse({'status': 'error', 'message': 'Cannot find pynab installation from Raspbian systemd services'})
    head_sha1=os.popen('cd {root_dir} && git rev-parse HEAD'.format(root_dir=root_dir)).read().rstrip()
    if head_sha1 == '':
      return JsonResponse({'status': 'error', 'message': 'Cannot get HEAD - not a git repository? Check /var/log/syslog'})
    commit_count=os.popen('cd {root_dir} && git fetch && git rev-list --count HEAD..origin/master'.format(root_dir=root_dir)).read().rstrip()
    if commit_count == '':
      return JsonResponse({'status': 'error', 'message': 'Cannot get number of commits from upstream. Not connected to the internet?'})
    return JsonResponse({'status': 'ok', 'head': head_sha1, 'commit_count': commit_count})

  def post(self, request, *args, **kwargs):
    root_dir=os.popen("sed -nE -e 's|WorkingDirectory=(.+)|\\1|p' < /lib/systemd/system/nabd.service").read().rstrip()
    head_sha1=os.popen('cd {root_dir} && git rev-parse HEAD'.format(root_dir=root_dir)).read().rstrip()
    pid=os.fork()
    if pid==0: # new process
      os.system('nohup bash {root_dir}/upgrade.sh &'.format(root_dir=root_dir))
      exit()
    return JsonResponse({'status': 'ok', 'root_dir': root_dir, 'old': head_sha1})
