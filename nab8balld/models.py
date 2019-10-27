from django.db import models
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = "nab8balld"
