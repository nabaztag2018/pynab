from django.db import models

from nabcommon import singleton_model


# Create your models here.
class Config(singleton_model.SingletonModel):

    ifttt_key = models.TextField(null=True, default="")
    json_data_base = models.TextField(null=True, default="")
