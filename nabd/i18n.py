from django.db import models
from nabcommon import singleton_model
from datetime import date


class Config(singleton_model.SingletonModel):

    locale = models.TextField(default="fr_FR")

    class Meta:
        app_label = "nabd"


async def get_locale():
    config = await Config.load_async()
    return config.locale
