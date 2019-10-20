from django.db import models
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    taichi_frequency = models.IntegerField(default=30)
    next_taichi = models.DateTimeField(null=True)

    class Meta:
        app_label = "nabtaichid"
