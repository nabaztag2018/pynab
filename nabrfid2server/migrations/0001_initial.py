# Generated by Django 3.0.3 on 2020-02-27 10:44

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Config",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rfid_2_server_test", models.BooleanField(default=False)),
                ("rfid_2_server_mode", models.IntegerField(default=2)),
                (
                    "rfid_2_server_url",
                    models.TextField(
                        default="Ex: https://MY_SERVER/core/api/jeeApi.php?apikey=MY_API_KEY&type=scenario&id=MY_SCENARIO_ID&action=start&tags=rfid=&#34;#RFID_TAG#&#34;%20etat=&#34;#RFID_STATE#&#34;%20flags=#34;#RFID_FLAGS##34;%20app=#34;#RFID_APP##34;"
                    ),
                ),
            ],
        ),
    ]
