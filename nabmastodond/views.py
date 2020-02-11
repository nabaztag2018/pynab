import json
from urllib.parse import urlparse, urlunparse
from django.shortcuts import render
from django.views.generic import View, TemplateView
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from .models import Config
from .nabmastodond import NabMastodond
from mastodon import Mastodon, MastodonError, MastodonUnauthorizedError


def reset_access_token(config):
    config.access_token = None
    config.username = None
    config.display_name = None
    config.avatar = None
    config.spouse_handle = None
    config.spouse_pairing_state = None
    config.spouse_pairing_date = None
    config.spouse_left_ear_position = None
    config.spouse_right_ear_position = None
    config.last_processed_status_id = None
    config.last_processed_status_date = None
    config.save()


class SettingsView(TemplateView):
    template_name = "nabmastodond/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        return context


class ConnectView(View):
    def post(self, request, *args, **kwargs):
        config = Config.load()
        # Determine callback URL from passed location.
        location = urlparse(request.POST["location"])
        redirect_location = (
            location.scheme,
            location.netloc,
            reverse("nabmastodond.oauthcb"),
            "",
            "",
            "",
        )
        redirect_uri = urlunparse(redirect_location)
        if (
            config.instance != request.POST["instance"]
            or config.redirect_uri != redirect_uri
        ):
            config.client_id = None
            config.client_secret = None
            config.redirect_uri = None
            config.instance = request.POST["instance"]
        # Register application on Mastodon
        if config.client_secret is None:
            try:
                (client_id, client_secret) = Mastodon.create_app(
                    "nabmastodond",
                    api_base_url="https://" + config.instance,
                    redirect_uris=redirect_uri,
                )
                config.client_id = client_id
                config.client_secret = client_secret
                config.redirect_uri = redirect_uri
                reset_access_token(config)
            except MastodonError as e:
                return HttpResponse(
                    "Unknown error",
                    content=f'{{"status":"error",'
                    f'"code":"MastodonError",'
                    f'"message":"{e}"}}',
                    mimetype="application/json",
                    status=500,
                )
        # Start OAuth process
        mastodon_client = Mastodon(
            client_id=config.client_id,
            client_secret=config.client_secret,
            api_base_url="https://" + config.instance,
        )
        request_url = mastodon_client.auth_request_url(
            redirect_uris=redirect_uri
        )
        return JsonResponse({"status": "ok", "request_url": request_url})

    def delete(self, request, *args, **kwargs):
        config = Config.load()
        reset_access_token(config)
        NabMastodond.signal_daemon()
        context = {"config": config}
        return render(request, SettingsView.template_name, context=context)


class LoginView(View):
    """
    View for asynchronous update of mastodon account.
    """

    def get(self, request, *args, **kwargs):
        config = Config.load()
        if config.access_token:
            try:
                mastodon_client = Mastodon(
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    access_token=config.access_token,
                    api_base_url="https://" + config.instance,
                )
                account_details = mastodon_client.account_verify_credentials()
                updated = False
                if config.username != account_details.username:
                    config.username = account_details.username
                    updated = True
                if config.display_name != account_details.display_name:
                    config.display_name = account_details.display_name
                    updated = True
                if config.avatar != account_details.avatar:
                    config.avatar = account_details.avatar
                    updated = True
                if updated:
                    config.save()
                    return JsonResponse({"status": "ok", "result": "updated"})
                else:
                    return JsonResponse(
                        {"status": "ok", "result": "not_modified"}
                    )
            except MastodonUnauthorizedError as e:
                reset_access_token(config)
                config.save()
                NabMastodond.signal_daemon()
                return HttpResponse(
                    "Unauthorized",
                    content=f'{{"status":"error",'
                    f'"result":"unauthorized",'
                    f'"message":"{e}"}}',
                    mimetype="application/json",
                    status=401,
                )
            except MastodonError as e:
                return HttpResponse(
                    "Unknown error",
                    content=f'{{"status":"error","message":"{e}"}}',
                    mimetype="application/json",
                    status=500,
                )
        else:
            return HttpResponse(
                "Not found",
                content='{"status":"error","result":"not_found"}',
                mimetype="application/json",
                status=404,
            )


class OAuthCBView(View):
    """
    View for oauth callback of mastodon account.
    """

    def get(self, request, *args, **kwargs):
        if "code" in request.GET:
            config = Config.load()
            mastodon_client = Mastodon(
                client_id=config.client_id,
                client_secret=config.client_secret,
                api_base_url="https://" + config.instance,
            )
            config.access_token = mastodon_client.log_in(
                code=request.GET["code"], redirect_uri=config.redirect_uri
            )
            config.last_processed_status_date = timezone.now()
            config.save()
            NabMastodond.signal_daemon()
        return HttpResponseRedirect("/")


class WeddingView(View):
    def put(self, request, *args, **kwargs):
        config = Config.load()
        if config.spouse_pairing_state is None:
            mastodon_client = Mastodon(
                client_id=config.client_id,
                client_secret=config.client_secret,
                access_token=config.access_token,
                api_base_url="https://" + config.instance,
            )
            params = json.loads(request.body.decode("utf8"))
            spouse = params["spouse"]
            if "@" not in spouse:
                spouse = spouse + "@" + config.instance
            status = NabMastodond.send_dm(mastodon_client, spouse, "proposal")
            config.spouse_pairing_date = status.created_at
            config.spouse_pairing_state = "proposed"
            config.spouse_handle = spouse
            config.save()
            NabMastodond.signal_daemon()
        context = {"config": config}
        return render(request, SettingsView.template_name, context=context)

    def post(self, request, *args, **kwargs):
        config = Config.load()
        if (
            config.spouse_pairing_state == "waiting_approval"
            and config.spouse_handle == request.POST["spouse"]
        ):
            mastodon_client = Mastodon(
                client_id=config.client_id,
                client_secret=config.client_secret,
                access_token=config.access_token,
                api_base_url="https://" + config.instance,
            )
            if request.POST["accept"] == "true":
                status = NabMastodond.send_dm(
                    mastodon_client, config.spouse_handle, "acceptation"
                )
                config.spouse_pairing_date = status.created_at
                config.spouse_pairing_state = "married"
            else:
                NabMastodond.send_dm(
                    mastodon_client, config.spouse_handle, "rejection"
                )
                config.spouse_pairing_date = None
                config.spouse_pairing_state = None
                config.spouse_handle = None
            config.save()
            NabMastodond.signal_daemon()
        context = {"config": config}
        return render(request, SettingsView.template_name, context=context)

    def delete(self, request, *args, **kwargs):
        config = Config.load()
        params = json.loads(request.body.decode("utf8"))
        spouse = params["spouse"]
        if (
            config.spouse_pairing_state == "married"
            or config.spouse_pairing_state == "proposed"
        ) and config.spouse_handle == spouse:
            mastodon_client = Mastodon(
                client_id=config.client_id,
                client_secret=config.client_secret,
                access_token=config.access_token,
                api_base_url="https://" + config.instance,
            )
            NabMastodond.send_dm(
                mastodon_client, config.spouse_handle, "divorce"
            )
            config.spouse_pairing_date = None
            config.spouse_pairing_state = None
            config.spouse_handle = None
            config.save()
            NabMastodond.signal_daemon()
        context = {"config": config}
        return render(request, SettingsView.template_name, context=context)
