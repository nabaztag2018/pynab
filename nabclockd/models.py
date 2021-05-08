from django.core import validators
from django.db import models

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
    # Monday
    wakeup_hour_monday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_monday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_monday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_monday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Tuesday
    wakeup_hour_tuesday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_tuesday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_tuesday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_tuesday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Wednesday
    wakeup_hour_wednesday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_wednesday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_wednesday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_wednesday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Thursday
    wakeup_hour_thursday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_thursday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_thursday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_thursday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Friday
    wakeup_hour_friday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_friday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_friday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_friday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Saturday
    wakeup_hour_saturday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_saturday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_saturday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_saturday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    # Sunday
    wakeup_hour_sunday = models.IntegerField(
        default=7,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    wakeup_min_sunday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    sleep_hour_sunday = models.IntegerField(
        default=22,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(23),
        ],
    )
    sleep_min_sunday = models.IntegerField(
        default=0,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(59),
        ],
    )
    chime_hour = models.BooleanField(default=True)
    play_wakeup_sleep_sounds = models.BooleanField(default=True)
    settings_per_day = models.BooleanField(default=False)

    class Meta:
        app_label = "nabclockd"
