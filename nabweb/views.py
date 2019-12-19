import abc
import asyncio
import datetime
import json
import logging
import os
import re
import subprocess

from django.apps import apps
from django.views.generic import View
from django.shortcuts import render
from django.utils import translation
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import cache
from nabd.i18n import Config
from nabcommon.nabservice import NabService
from django.utils.translation import to_locale, to_language


class BaseView(View, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def template_name(self):
        pass

    def get_locales(self):
        config = Config.load()
        return [
            (to_locale(lang), name, to_locale(lang) == config.locale)
            for (lang, name) in settings.LANGUAGES
        ]

    def get_context(self):
        user_locale = Config.load().locale
        locales = self.get_locales()
        return {"current_locale": user_locale, "locales": locales}

    def get(self, request, *args, **kwargs):
        context = self.get_context()
        return render(request, self.template_name(), context=context)

    @staticmethod
    def get_services(page):
        services = []
        for config in apps.get_app_configs():
            if hasattr(config.module, 'NABAZTAG_SERVICE_PRIORITY'):
                service_page = 'services'
                if hasattr(config.module, 'NABAZTAG_SERVICE_PAGE'):
                    service_page = config.module.NABAZTAG_SERVICE_PAGE
                if service_page == page:
                    services.append({
                        'priority': config.module.NABAZTAG_SERVICE_PRIORITY,
                        'name': config.name
                    })
        services_sorted = sorted(services, key=lambda s: s['priority'])
        services_names = map(lambda s: s['name'], services_sorted)
        return services_names

class NabWebView(BaseView):
    def template_name(self):
        return "nabweb/index.html"

    def get_context(self):
        context = super().get_context()
        context["services"] = BaseView.get_services('home')
        return context

    def post(self, request, *args, **kwargs):
        config = Config.load()
        config.locale = request.POST["locale"]
        config.save()
        user_language = to_language(config.locale)
        translation.activate(user_language)
        request.LANGUAGE_CODE = translation.get_language()
        locales = self.get_locales()
        return render(
            request,
            self.template_name(),
            context={"current_locale": config.locale, "locales": locales},
        )

class NabWebServicesView(BaseView):
    def template_name(self):
        return "nabweb/services/index.html"

    def get_context(self):
        context = super().get_context()
        context["services"] = BaseView.get_services('services')
        return context

class NabWebSytemInfoView(BaseView):
    def template_name(self):
        return "nabweb/system-info/index.html"

    async def query_gestalt(self):
        try:
            conn = asyncio.open_connection('127.0.0.1', NabService.PORT_NUMBER)
            reader, writer = await asyncio.wait_for(conn, 0.5)
        except ConnectionRefusedError as err:
            return {"status":"error","message":"Nabd is not running"}
        except asyncio.TimeoutError as err:
            return {
                "status":"error",
                "message":"Communication with Nabd timed out (connecting)"
            }
        try:
            writer.write(b'{"type":"gestalt","request_id":"gestalt"}\r\n')
            while True:
                line = await asyncio.wait_for(reader.readline(), 0.5)
                packet = json.loads(line.decode("utf8"))
                if (
                    "type" in packet and
                    packet["type"] == "response" and
                    "request_id" in packet and
                    packet["request_id"] == "gestalt"
                ):
                    writer.close()
                    return {"status": "ok", "result": packet}
        except asyncio.TimeoutError as err:
            return {
                "status":"error",
                "message":"Communication with Nabd timed out (getting info)"
            }

    def get_os_info(self):
        version = "unknown"
        with open("/etc/os-release") as release:
            line = release.readline()
            matchObj = re.match(r'PRETTY_NAME="(.+)"$', line, re.M)
            if matchObj:
                version = matchObj.group(1)
        with open("/etc/rpi-issue") as issue:
            line = issue.readline()
            matchObj = re.search(r' ([0-9-]+)$', line, re.M)
            if matchObj:
                version = version + ', issue ' + matchObj.group(1)
        with open('/proc/uptime', 'r') as uptime_f:
            uptime = int(float(uptime_f.readline().split()[0]))
        return {'version': version, 'uptime': uptime}

    def get_context(self):
        context = super().get_context()
        gestalt = asyncio.run(self.query_gestalt())
        context["gestalt"] = gestalt
        context["os"] = self.get_os_info()
        return context

class GitInfo:
    REPOSITORIES = {
        "pynab": ".",
        "sound_driver": "../wm8960",
        "ears_driver": "../tagtagtag-ears/",
        "nabblockly": "nabblockly"
    }

    @staticmethod
    def get_root_dir():
        root_dir = (
            os.popen(
                "sed -nE -e 's|WorkingDirectory=(.+)|\\1|p' "
                "< /lib/systemd/system/nabd.service"
            )
            .read()
            .rstrip()
        )
        if root_dir == "":
            root_dir = None
        return root_dir

    @staticmethod
    def get_repository_info(repository, force = False):
        relpath = GitInfo.REPOSITORIES[repository]
        cache_key = f"git/info/{repository}"
        if not force:
            info = cache.get(cache_key)
            if info is not None:
                return info
        info = GitInfo.do_get_repository_info(repository, relpath)
        timeout = 600
        if info["status"] == "ok":
            timeout = 86400
        cache.set(cache_key, info, timeout)
        return info

    @staticmethod
    def do_get_repository_info(repository, relpath):
        root_dir = GitInfo.get_root_dir()
        if root_dir is None:
            return (
                {
                    "status": "error",
                    "message": "Cannot find pynab installation from "
                    "Raspbian systemd services",
                }
            )
        repo_dir = root_dir + "/" + relpath
        head_sha1 = os.popen(
            f"cd {repo_dir} && git rev-parse HEAD"
        ).read().rstrip()
        if head_sha1 == "":
            return (
                {
                    "status": "error",
                    "message": "Cannot get HEAD - not a git repository? "
                    "Check /var/log/syslog",
                }
            )
        info = {}
        info["head"] = head_sha1
        info["branch"] = os.popen(
            f"cd {repo_dir} && sudo -u pi git rev-parse --abbrev-ref HEAD"
        ).read().rstrip()
        upstream_branch = os.popen(
            f"cd {repo_dir} "
            f"&& sudo -u pi git rev-parse --abbrev-ref @{{upstream}}"
        ).read().rstrip()
        remote = upstream_branch.split('/')[0]
        info["upstream_branch"] = upstream_branch
        info["url"] = os.popen(
            f"cd {repo_dir} && sudo -u pi git remote get-url {remote}"
        ).read().rstrip()
        info["local_changes"] = os.popen(
            f"cd {repo_dir} && sudo -u pi git diff-index --quiet HEAD -- "
            f"|| echo 'local_changes' "
        ).read().strip() != ""
        info["tag"] = os.popen(
            f"cd {repo_dir} && sudo -u pi git describe --exact-match --tags"
        ).read().strip()
        commits_count = os.popen(
            f"cd {repo_dir} && sudo -u pi git fetch "
            f"&& sudo -u pi git rev-list --count HEAD..{upstream_branch}"
        ).read().rstrip()
        local_commits_count = os.popen(
            f"cd {repo_dir} "
            f"&& sudo -u pi git rev-list --count {upstream_branch}..HEAD"
        ).read().rstrip()
        if commits_count == "":
            info["status"] = "error"
            info["message"] = (
                "Cannot get number of commits from upstream. "
                "Not connected to the internet?"
            )
        else:
            info["status"] = "ok"
            info["commits_count"] = int(commits_count)
            info["local_commits_count"] = int(local_commits_count)
        info["info-date"] = datetime.datetime.now()
        return info

class NabWebUpgradeView(BaseView):
    def template_name(self):
        return "nabweb/upgrade/index.html"

    def get_context(self):
        context = super().get_context()
        local_changes = False
        for repository in GitInfo.REPOSITORIES.keys():
            info = GitInfo.get_repository_info(repository)
            context[repository] = info
            if "local_changes" in info and info["local_changes"] > 0:
                local_changes = True
        pynab_info = context["pynab"]
        updatable = (
            "commits_count" in pynab_info and
            pynab_info["commits_count"] > 0 and
            "local_commits_count" in pynab_info and
            pynab_info["local_commits_count"] == 0 and
            local_changes is False
        )
        context["updatable"] = updatable
        return context

class NabWebUpgradeStatusView(View):
    def get(self, request, *args, **kwargs):
        repo_info = GitInfo.get_repository_info("pynab")
        return JsonResponse(repo_info)

class NabWebUpgradeNowView(View):
    def get(self, request, *args, **kwargs):
        step = os.popen(
            "sudo -u pi flock -n /tmp/pynab.upgrade echo 'Not upgrading' "
            "|| cat /tmp/pynab.upgrade"
        ).read().rstrip()
        if step == "Not upgrading":
            return JsonResponse({"status": "done"})
        else:
            return JsonResponse({"status": "ok", "message": step})

    def post(self, request, *args, **kwargs):
        root_dir = GitInfo.get_root_dir()
        if root_dir is None:
            return (
                {
                    "status": "error",
                    "message": "Cannot find pynab installation from "
                    "Raspbian systemd services",
                }
            )
        locked = os.popen(
            "sudo -u pi flock -n /tmp/pynab.upgrade echo 'OK' || echo 'Locked'"
        ).read().rstrip()
        if locked == "OK":
            command = [
                "/usr/bin/nohup", "sudo", "-u", "pi",
                "flock", "/tmp/pynab.upgrade",
                "bash", f"{root_dir}/upgrade.sh",
            ]
            subprocess.Popen(command,
                 stdout=open('/tmp/pynab-upgrade-stdout.log', 'w'),
                 stderr=open('/tmp/pynab-upgrade-stderr.log', 'w'),
                 preexec_fn=os.setpgrp
            )
            return JsonResponse({"status": "ok"})
        if locked == "Locked":
            return JsonResponse({"status": "ok"})
        return JsonResponse({
                "status": "error",
                "message": "Could not acquire lock, a problem occurred"
            })
