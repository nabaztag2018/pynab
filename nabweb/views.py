import abc
import asyncio
import datetime
import json
import os
import re
import subprocess
import base64

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


class NabdConnection:
    async def __aenter__(self):
        conn = asyncio.open_connection("127.0.0.1", NabService.PORT_NUMBER)
        self.reader, self.writer = await asyncio.wait_for(conn, 0.5)
        return self

    async def __aexit__(self, type, value, traceback):
        self.writer.close()

    @staticmethod
    async def transaction(fun, *args):
        try:
            async with NabdConnection() as conn:
                return await fun(conn.reader, conn.writer, *args)
        except ConnectionRefusedError as err:
            return {"status": "error", "message": "Nabd is not running"}
        except asyncio.TimeoutError as err:
            return {
                "status": "error",
                "message": "Communication with Nabd timed out",
            }


class BaseView(View, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def template_name(self):
        pass

    async def query_gestalt(self):
        return await NabdConnection.transaction(self._do_query_gestalt)

    async def _do_query_gestalt(self, reader, writer):
        writer.write(b'{"type":"gestalt","request_id":"gestalt"}\r\n')
        await writer.drain()
        while True:
            line = await asyncio.wait_for(reader.readline(), 0.5)
            packet = json.loads(line.decode("utf8"))
            if (
                "type" in packet
                and packet["type"] == "response"
                and "request_id" in packet
                and packet["request_id"] == "gestalt"
            ):
                return {"status": "ok", "result": packet}

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
            if hasattr(config.module, "NABAZTAG_SERVICE_PRIORITY"):
                service_page = "services"
                if hasattr(config.module, "NABAZTAG_SERVICE_PAGE"):
                    service_page = config.module.NABAZTAG_SERVICE_PAGE
                if service_page == page:
                    services.append(
                        {
                            "priority": config.module.NABAZTAG_SERVICE_PRIORITY,
                            "name": config.name,
                        }
                    )
        services_sorted = sorted(services, key=lambda s: s["priority"])
        services_names = [s["name"] for s in services_sorted]
        return services_names


class NabWebView(BaseView):
    def template_name(self):
        return "nabweb/index.html"

    def get_context(self):
        context = super().get_context()
        context["services"] = BaseView.get_services("home")
        return context

    def post(self, request, *args, **kwargs):
        if "locale" in request.POST:
            config = Config.load()
            config.locale = request.POST["locale"]
            config.save()
            asyncio.run(self.notify_config_update("nabd", "locale"))
            user_language = to_language(config.locale)
            translation.activate(user_language)
            request.LANGUAGE_CODE = translation.get_language()
        context = self.get_context()
        return render(request, self.template_name(), context=context)

    async def notify_config_update(self, service, slot):
        await NabdConnection.transaction(
            self._do_notify_config_update, service, slot
        )

    async def _do_notify_config_update(self, reader, writer, service, slot):
        try:
            packet = (
                f'{{"type":"config-update","service":"{service}",'
                f'"slot":"{slot}"}}\r\n'
            )
            writer.write(packet.encode("utf-8"))
            await writer.drain()
            writer.close()
        except Exception:
            pass


class NabWebServicesView(BaseView):
    def template_name(self):
        return "nabweb/services/index.html"

    def get_context(self):
        context = super().get_context()
        context["services"] = BaseView.get_services("services")
        return context


class NabWebRfidView(BaseView):
    def template_name(self):
        return "nabweb/rfid/index.html"

    @staticmethod
    def get_rfid_services():
        services = []
        for config in apps.get_app_configs():
            if hasattr(config.module, "NABAZTAG_SERVICE_PRIORITY"):
                if hasattr(config.module, "NABAZTAG_RFID_APPLICATION_NAME"):
                    if config.module.NABAZTAG_RFID_APPLICATION_NAME:
                        app_name = config.module.NABAZTAG_RFID_APPLICATION_NAME
                        services.append({"app": config.name, "name": app_name})
        services_sorted = sorted(services, key=lambda s: s["name"])
        return services_sorted

    def get_context(self):
        context = super().get_context()
        gestalt = asyncio.run(self.query_gestalt())
        if gestalt["status"] == "ok":
            rfid = {
                "status": "ok",
                "available": gestalt["result"]["hardware"]["rfid"],
            }
        else:
            rfid = gestalt
        context["rfid_support"] = rfid
        context["rfid_services"] = NabWebRfidView.get_rfid_services()
        return context


class NabWebRfidReadView(View):
    READ_TIMEOUT = 30.0

    async def read_tag(self, timeout):
        return await NabdConnection.transaction(self._do_read_tag, timeout)

    async def _do_read_tag(self, reader, writer, timeout):
        # Enter interactive mode to get every rfid event (instead of apps)
        packet = (
            '{"type":"mode","mode":"interactive","events":["rfid/*"],'
            '"request_id":"mode"}\r\n'
        )
        writer.write(packet.encode("utf8"))
        await writer.drain()
        while True:
            line = await asyncio.wait_for(reader.readline(), 1.0)
            packet = json.loads(line.decode("utf8"))
            if (
                "type" in packet
                and packet["type"] == "response"
                and "request_id" in packet
                and packet["request_id"] == "mode"
            ):
                # Turn nose red to mean we're expecting a tag now
                base64chor = base64.b64encode(
                    bytes([0, 7, 4, 255, 0, 0, 0, 0])
                )
                packet = (
                    b'{"type":"command","sequence":['
                    b'{"choreography":'
                    b'"data:application/x-nabaztag-mtl-choreography;base64,'
                    + base64chor
                    + b'"}]}\r\n'
                )
                writer.write(packet)
                await writer.drain()
                try:
                    while True:
                        line = await asyncio.wait_for(
                            reader.readline(), timeout
                        )
                        packet = json.loads(line.decode("utf8"))
                        if (
                            "type" in packet
                            and packet["type"] == "rfid_event"
                            and packet["event"] != "removed"
                        ):
                            return {"status": "ok", "event": packet}
                except asyncio.TimeoutError as err:
                    return {
                        "status": "timeout",
                        "message": "No RFID tag was detected",
                    }

    def post(self, request, *args, **kwargs):
        read_result = asyncio.run(
            self.read_tag(NabWebRfidReadView.READ_TIMEOUT)
        )
        return JsonResponse(read_result)


class NabWebRfidWriteView(View):
    WRITE_TIMEOUT = 30.0

    async def write_tag(self, uid, picture, app, data, timeout):
        return await NabdConnection.transaction(
            self._do_write_tag, uid, picture, app, data, timeout
        )

    async def _do_write_tag(
        self, reader, writer, uid, picture, app, data, timeout
    ):
        packet = {
            "type": "rfid_write",
            "uid": uid,
            "picture": int(picture),
            "app": app,
            "data": data,
            "request_id": "rfid_write",
        }
        packet_json = json.JSONEncoder().encode(packet)
        packet = packet_json + "\r\n"
        writer.write(packet.encode("utf8"))
        await writer.drain()
        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout)
                packet = json.loads(line.decode("utf8"))
                if (
                    "type" in packet
                    and packet["type"] == "response"
                    and "request_id" in packet
                    and packet["request_id"] == "rfid_write"
                ):
                    response = {
                        "status": packet["status"],
                        "rfid": {
                            "uid": uid,
                            "picture": picture,
                            "app": app,
                            "data": data,
                        },
                    }
                    if "message" in packet:
                        response["message"] = packet["message"]
                    return response
            except asyncio.TimeoutError as err:
                return {
                    "status": "timeout",
                    "message": "No RFID tag was detected",
                }

    def post(self, request, *args, **kwargs):
        if (
            "uid" not in request.POST
            or "picture" not in request.POST
            or "app" not in request.POST
        ):
            return JsonResponse(
                {"status": "error", "message": "Missing arguments"}, status=400
            )
        uid = request.POST["uid"]
        picture = request.POST["picture"]
        app = request.POST["app"]
        if "data" in request.POST:
            data = request.POST["data"]
        else:
            data = ""
        write_result = asyncio.run(
            self.write_tag(
                uid, picture, app, data, NabWebRfidReadView.READ_TIMEOUT
            )
        )
        return JsonResponse(write_result)


class NabWebSytemInfoView(BaseView):
    def template_name(self):
        return "nabweb/system-info/index.html"

    def get_os_info(self):
        version = "unknown"
        with open("/etc/os-release") as release:
            line = release.readline()
            matchObj = re.match(r'PRETTY_NAME="(.+)"$', line, re.M)
            if matchObj:
                version = matchObj.group(1)
        kernel_release = os.popen("uname -rm").read().rstrip()
        version = version + " - Kernel " + kernel_release
        hostname = os.popen("hostname -a").read().rstrip()
        ip_address = os.popen("hostname -I").read().rstrip()
        with open("/proc/uptime", "r") as uptime_f:
            uptime = int(float(uptime_f.readline().split()[0]))
        ssh_state = os.popen("systemctl is-active ssh").read().rstrip()
        if ssh_state == "active" and os.path.isfile("/run/sshwarn"):
            ssh_state = "sshwarn"
        return {
            "version": version,
            "hostname": hostname,
            "address": ip_address,
            "uptime": uptime,
            "ssh": ssh_state,
        }

    def get_pi_info(self):
        with open("/proc/device-tree/model") as model_f:
            model = model_f.readline()
        return {"model": model}

    def get_context(self):
        context = super().get_context()
        gestalt = asyncio.run(self.query_gestalt())
        context["gestalt"] = gestalt
        context["os"] = self.get_os_info()
        context["pi"] = self.get_pi_info()
        return context


class NabWebHardwareTestView(View):
    TEST_TIMEOUT = 30.0

    async def hardware_test(self, test, timeout):
        return await NabdConnection.transaction(
            self._do_hardware_test, test, timeout
        )

    async def _do_hardware_test(self, reader, writer, test, timeout):
        try:
            packet = (
                f'{{"type":"test","test":"{test}","request_id":"test"}}\r\n'
            )
            writer.write(packet.encode("utf8"))
            await writer.drain()
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout)
                packet = json.loads(line.decode("utf8"))
                if (
                    "type" in packet
                    and packet["type"] == "response"
                    and "request_id" in packet
                    and packet["request_id"] == "test"
                ):
                    return {"status": "ok", "result": packet}
        except asyncio.TimeoutError as err:
            return {
                "status": "error",
                "message": "Communication with Nabd timed out (running test)",
            }

    def post(self, request, *args, **kwargs):
        test = kwargs.get("test")
        test_result = asyncio.run(
            self.hardware_test(test, NabWebHardwareTestView.TEST_TIMEOUT)
        )
        return JsonResponse(test_result)


class GitInfo:
    REPOSITORIES = {
        "pynab": ".",
        "sound_driver": "../wm8960",
        "ears_driver": "../tagtagtag-ears/",
        "rfid_driver": "../cr14/",
        "nabblockly": "nabblockly",
    }
    NAMES = {
        "pynab": "Pynab",
        "sound_driver": "Tagtagtag sound card driver",
        "ears_driver": "Ears driver",
        "rfid_driver": "RFID reader driver",
        "nabblockly": "Nabblockly",
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
    def get_repository_info(repository, cached=False, force=False):
        relpath = GitInfo.REPOSITORIES[repository]
        cache_key = f"git/info/{repository}"
        if not force:
            info = cache.get(cache_key)
            if info is not None:
                return info
        if cached:
            return None
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
            return {
                "status": "error",
                "message": "Cannot find pynab installation from "
                "Raspbian systemd services",
            }
        repo_dir = root_dir + "/" + relpath
        head_sha1 = (
            os.popen(f"cd {repo_dir} && git rev-parse HEAD").read().rstrip()
        )
        if head_sha1 == "":
            return {
                "status": "error",
                "message": "Cannot get HEAD - not a git repository? "
                "Check /var/log/syslog",
            }
        info = {}
        info["head"] = head_sha1
        info["branch"] = (
            os.popen(
                f"cd {repo_dir} && sudo -u pi git rev-parse --abbrev-ref HEAD"
            )
            .read()
            .rstrip()
        )
        upstream_branch = (
            os.popen(
                f"cd {repo_dir} "
                f"&& sudo -u pi git rev-parse --abbrev-ref @{{upstream}}"
            )
            .read()
            .rstrip()
        )
        remote = upstream_branch.split("/")[0]
        info["upstream_branch"] = upstream_branch
        info["url"] = (
            os.popen(
                f"cd {repo_dir} && sudo -u pi git remote get-url {remote}"
            )
            .read()
            .rstrip()
        )
        info["local_changes"] = (
            os.popen(
                f"cd {repo_dir} && (sudo -u pi git status -s) > /dev/null "
                f"&& sudo -u pi git diff-index --quiet HEAD -- "
                f"|| echo 'local_changes' "
            )
            .read()
            .strip()
            != ""
        )
        info["tag"] = (
            os.popen(
                f"cd {repo_dir} && sudo -u pi git describe --exact-match --tags"
            )
            .read()
            .strip()
        )
        commits_count = (
            os.popen(
                f"cd {repo_dir} && sudo -u pi git fetch "
                f"&& sudo -u pi git rev-list --count HEAD..{upstream_branch}"
            )
            .read()
            .rstrip()
        )
        local_commits_count = (
            os.popen(
                f"cd {repo_dir} "
                f"&& sudo -u pi git rev-list --count {upstream_branch}..HEAD"
            )
            .read()
            .rstrip()
        )
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
        info["info_date"] = datetime.datetime.now()
        info["name"] = GitInfo.NAMES[repository]
        return info


class NabWebUpgradeView(BaseView):
    def template_name(self):
        return "nabweb/upgrade/index.html"

    def get_context(self):
        context = super().get_context()
        last_check = None
        partial = False
        pynab_info = GitInfo.get_repository_info("pynab")
        for repository in GitInfo.REPOSITORIES.keys():
            info = GitInfo.get_repository_info(repository, cached=True)
            if info is None:
                partial = True
                continue
            context[repository] = info
            if last_check is None:
                last_check = info["info_date"]
            else:
                last_check = min(last_check, info["info_date"])
        updatable = (
            "commits_count" in pynab_info
            and pynab_info["commits_count"] > 0
            and "local_commits_count" in pynab_info
            and pynab_info["local_commits_count"] == 0
        )
        context["partial"] = partial
        context["updatable"] = updatable
        context["last_check"] = last_check
        return context


class NabWebUpgradeRepositoryInfoView(View):
    def get(self, request, *args, **kwargs):
        repository = kwargs.get("repository")
        repo_info = GitInfo.get_repository_info(repository)
        pynab_info = GitInfo.get_repository_info("pynab", cached=True)
        updatable = (
            pynab_info is not None
            and "commits_count" in pynab_info
            and pynab_info["commits_count"] > 0
            and "local_commits_count" in pynab_info
            and pynab_info["local_commits_count"] == 0
        )
        template_name = "nabweb/upgrade/_repository.html"
        context = {"repo": repo_info, "updatable": updatable}
        return render(request, template_name, context=context)


class NabWebUpgradeCheckNowView(View):
    def post(self, request, *args, **kwargs):
        for repository in GitInfo.REPOSITORIES.keys():
            GitInfo.get_repository_info(repository, force=True)
        return JsonResponse({"status": "ok"})


class NabWebUpgradeStatusView(View):
    def get(self, request, *args, **kwargs):
        repo_info = GitInfo.get_repository_info("pynab")
        return JsonResponse(repo_info)


class NabWebUpgradeNowView(View):
    def get(self, request, *args, **kwargs):
        step = (
            os.popen(
                "sudo -u pi flock -n /tmp/pynab.upgrade echo 'Not upgrading' "
                "|| cat /tmp/pynab.upgrade"
            )
            .read()
            .rstrip()
        )
        if step == "Not upgrading":
            return JsonResponse({"status": "done"})
        else:
            return JsonResponse({"status": "ok", "message": step})

    def post(self, request, *args, **kwargs):
        root_dir = GitInfo.get_root_dir()
        if root_dir is None:
            return {
                "status": "error",
                "message": "Cannot find pynab installation from "
                "Raspbian systemd services",
            }
        locked = (
            os.popen(
                "sudo -u pi flock -n /tmp/pynab.upgrade echo 'OK' || echo 'Locked'"
            )
            .read()
            .rstrip()
        )
        if locked == "OK":
            command = [
                "/usr/bin/nohup",
                "sudo",
                "-u",
                "pi",
                "flock",
                "/tmp/pynab.upgrade",
                "bash",
                f"{root_dir}/upgrade.sh",
            ]
            subprocess.Popen(
                command,
                stdout=open("/tmp/pynab-upgrade-stdout.log", "w"),
                stderr=open("/tmp/pynab-upgrade-stderr.log", "w"),
                preexec_fn=os.setpgrp,
            )
            return JsonResponse({"status": "ok"})
        if locked == "Locked":
            return JsonResponse({"status": "ok"})
        return JsonResponse(
            {
                "status": "error",
                "message": "Could not acquire lock, a problem occurred",
            }
        )


class NabWebShutdownView(View):
    SHUTDOWN_TIMEOUT = 30.0

    async def os_shutdown(self, mode):
        return await NabdConnection.transaction(self._do_os_shutdown, mode)

    async def _do_os_shutdown(self, reader, writer, mode):
        try:
            packet = (
                f'{{"type":"shutdown","mode":"{mode}",'
                f'"request_id":"shutdown"}}\r\n'
            )
            writer.write(packet.encode("utf8"))
            await writer.drain()
            while True:
                line = await asyncio.wait_for(
                    reader.readline(), NabWebShutdownView.SHUTDOWN_TIMEOUT
                )
                packet = json.loads(line.decode("utf8"))
                if (
                    "type" in packet
                    and packet["type"] == "response"
                    and "request_id" in packet
                    and packet["request_id"] == "shutdown"
                ):
                    return {"status": "ok", "result": packet}
        except asyncio.TimeoutError as err:
            return {
                "status": "error",
                "message": "Communication with Nabd timed out (shutdown)",
            }

    def post(self, request, *args, **kwargs):
        mode = kwargs.get("mode")
        shutdown_result = asyncio.run(self.os_shutdown(mode))
        return JsonResponse(shutdown_result)
