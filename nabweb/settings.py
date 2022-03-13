"""
Django settings for nabweb project.

Generated by 'django-admin startproject' using Django 2.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os

from django.utils.translation import ugettext_lazy as _

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "+m)qk@&t%tlqj@o$jo$&egt34r7yu0fq4v!0o82&b9+b51ppyy"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

# https://code.djangoproject.com/ticket/30250
CSRF_COOKIE_SAMESITE = None
SESSION_COOKIE_SAMESITE = None

# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "nabd",
    "nab8balld",
    "nabbookd",
    "nabclockd",
    "nabmastodond",
    "nabsurprised",
    "nabtaichid",
    "nabweatherd",
    "nabairqualityd",
    "nabweb",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "nabweb.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nabweb.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "nabweb.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "pynab",
        "USER": "pynab",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

if "PGDATABASE" in os.environ:
    DATABASES["default"]["NAME"] = os.environ["PGDATABASE"]
if "PGUSER" in os.environ:
    DATABASES["default"]["USER"] = os.environ["PGUSER"]
if "PGPASSWORD" in os.environ:
    DATABASES["default"]["PASSWORD"] = os.environ["PGPASSWORD"]
if "PGHOST" in os.environ:
    DATABASES["default"]["HOST"] = os.environ["PGHOST"]
if "PGPORT" in os.environ:
    DATABASES["default"]["PORT"] = os.environ["PGPORT"]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "MinimumLengthValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "NumericPasswordValidator"
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

# Available languages for modules.
# Locales are inferred from this list.
LANGUAGES = [
    ("fr-fr", _("French")),
    ("de-de", _("German")),
    ("en-us", _("U.S. English")),
    ("en-gb", _("British English")),
    ("it-it", _("Italian")),
    ("es-es", _("Spanish")),
    ("ja-jp", _("Japanese")),
    ("pt-br", _("Brazilian Portuguese")),
]

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = "/static/"
