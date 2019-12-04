from django.db import models
from nabcommon import singleton_model


# ici on defini le modele de donnes pour la config


class Config(singleton_model.SingletonModel):

    airquality = models.TextField(null=True)
    localisation = models.TextField(null=True)
    index_airquality = models.TextField(null=True)

    # necessaire pour declencher via le site web
    next_performance_date = models.DateTimeField(null=True)

    class Meta:
        app_label = "nabairqualityd"
