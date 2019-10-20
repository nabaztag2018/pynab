from django.db import models
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    surprise_frequency = models.IntegerField(default=30)
    next_surprise = models.DateTimeField(null=True)

    class Meta:
        app_label = "nabsurprised"
