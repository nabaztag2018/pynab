from django.db import models

from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    instance = models.TextField()
    mqtt_host = models.TextField(null=True)
    mqtt_port = models.TextField(null=True)
    mqtt_user = models.TextField(null=True)
    mqtt_pw = models.TextField(null=True)
    mqtt_topic = models.TextField(null=True)
    display_name = models.TextField(null=True)
    avatar = models.TextField(null=True)


    class Meta:
        app_label = "nabmqttd"
