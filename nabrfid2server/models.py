from django.db import models

from nabcommon import singleton_model


class Config(singleton_model.SingletonModel):
    rfid_2_server_test = models.BooleanField(default=False)
    rfid_2_server_mode = models.IntegerField(default=2)
    rfid_2_server_url = models.TextField(
        default="Ex: https://MY_SERVER/core/api/jeeApi.php?apikey=MY_API_KEY&"
        "type=scenario&id=MY_SCENARIO_ID&action=start&"
        "tags=rfid=&#34;#RFID_TAG#&#34;%20etat=&#34;"
        "#RFID_STATE#&#34;%20flags=#34;#RFID_FLAGS##34;"
        "%20app=#34;#RFID_APP##34; "
    )

    class Meta:
        app_label = "nabrfid2server"
