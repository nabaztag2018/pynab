from django.db import models
from nabcommon import singleton_model

class Config(singleton_model.SingletonModel):
  location = models.TextField(null=True)
  unit = models.IntegerField(null=False, default=1)
  next_performance_date = models.DateTimeField(null=True)
  next_performance_type = models.TextField(null=True)

  class Meta:
    app_label = 'nabweatherd'

class ScheduledMessage(models.Model):
  hour = models.IntegerField(null=False)
  minute = models.IntegerField(null=False)
  type = models.TextField(null=False)
  
  class Meta:
    app_label = 'nabweatherd'
