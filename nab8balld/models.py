from django.db import models
from django.core import validators
from nabcommon import singleton_model

class Config(singleton_model.SingletonModel):
  enabled = models.BooleanField(default=True)

  class Meta:
    app_label = 'nab8balld'
