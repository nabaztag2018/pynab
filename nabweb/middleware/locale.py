from django.utils import translation
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import to_language
from nabd.i18n import Config


class LocaleMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user_locale = Config.load().locale
        user_language = to_language(user_locale)
        translation.activate(user_language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        language = translation.get_language()
        patch_vary_headers(response, ("Accept-Language",))
        response.setdefault("Content-Language", language)
        return response
