from django.db import models
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    instance = models.TextField()
    client_id = models.TextField(null=True)
    client_secret = models.TextField(null=True)
    redirect_uri = models.TextField(null=True)
    access_token = models.TextField(null=True)
    username = models.TextField(null=True)
    display_name = models.TextField(null=True)
    avatar = models.TextField(null=True)
    spouse_handle = models.TextField(null=True)
    spouse_pairing_state = models.TextField(null=True)
    spouse_pairing_date = models.DateTimeField(null=True)
    spouse_left_ear_position = models.IntegerField(null=True)
    spouse_right_ear_position = models.IntegerField(null=True)
    last_processed_status_id = models.BigIntegerField(null=True)
    last_processed_status_date = models.DateTimeField(null=True)

    class Meta:
        app_label = "nabmastodond"
