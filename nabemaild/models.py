from django.db import models
from nabcommon import singleton_model


# Create your models here.
class Config(singleton_model.SingletonModel):

    gmail_account = models.TextField(null=True, default="")
    gmail_passwd = models.TextField(null=True, default="")
    json_data_base = models.TextField(null=True, default="")
