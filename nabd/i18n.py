from django.db import models
from asgiref.sync import sync_to_async
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    locale = models.TextField(default="fr_FR")

    class Meta:
        app_label = "nabd"


async def get_locale():
    config = await sync_to_async(Config.load)()
    return config.locale
