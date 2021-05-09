from django.core import validators
from django.db import models

from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    location = models.TextField(null=True, default='{"insee": "29039", "name": "Concarneau", "lat": 47.87528, "lon": -3.91889, "country": "FR", "admin": "Bretagne", "admin2": "29", "postCode": "29900"}')
    location_user_friendly = models.TextField(default='Concarneau - Bretagne (29) - FR')
    unit = models.IntegerField(null=False, default=1)
    next_performance_date = models.DateTimeField(null=True)
    next_performance_type = models.TextField(null=True)
    weather_animation_type = models.TextField(null=True, default="weather_and_rain")
    weather_frequency = models.IntegerField(default=3)

    next_performance_weather_vocal_date = models.DateTimeField(null=True)
    next_performance_weather_vocal_flag = models.IntegerField(
        null=False, default=0
    )

    weather_playtime_hour = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    weather_playtime_min = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )

    class Meta:
        app_label = "nabweatherd"


class ScheduledMessage(models.Model):
    hour = models.IntegerField(null=False)
    minute = models.IntegerField(null=False)
    type = models.TextField(null=False)

    class Meta:
        app_label = "nabweatherd"
