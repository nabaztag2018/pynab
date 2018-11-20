from django.db import models
from nabcommon import singleton_model

class Config(singleton_model.UncachableSingletonModel):
  locale = models.TextField(default='fr_FR')

  class Meta:
    app_label = 'nabd'

def get_locale():
  return Config.load().locale
