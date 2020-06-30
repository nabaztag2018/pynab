import os
from django.apps import apps
from django.conf import settings

def configure(appname):
    if not settings.configured:
        from django.apps.config import AppConfig

        conf = {
            "INSTALLED_APPS": [appname],
            "USE_TZ": True,
            "DATABASES": {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": "pynab",
                    "USER": "pynab",
                    "PASSWORD": "",
                    "HOST": "",
                    "PORT": "",
                }
            },
        }
        if "PGDATABASE" in os.environ:
          conf["DATABASES"]["default"]["NAME"] = os.environ["PGDATABASE"]
        if "PGUSER" in os.environ:
          conf["DATABASES"]["default"]["USER"] = os.environ["PGUSER"]
        if "PGPASSWORD" in os.environ:
          conf["DATABASES"]["default"]["PASSWORD"] = os.environ["PGPASSWORD"]
        if "PGHOST" in os.environ:
          conf["DATABASES"]["default"]["HOST"] = os.environ["PGHOST"]
        if "PGPORT" in os.environ:
          conf["DATABASES"]["default"]["PORT"] = os.environ["PGPORT"]
        settings.configure(**conf)
        apps.populate(settings.INSTALLED_APPS)
