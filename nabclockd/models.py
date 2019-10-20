from django.db import models
from django.core import validators
from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    wakeup_hour = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    chime_hour = models.BooleanField(default=True)

    class Meta:
        app_label = "nabclockd"
