# Generated by Django 3.0.14 on 2021-05-10 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nabweatherd", "0010_auto_20210329_0921"),
    ]

    operations = [
        migrations.AlterField(
            model_name="config",
            name="location",
            field=models.TextField(
                default='{"insee": "75056", "name": "Paris 14", "lat": 48.8331, "lon": 2.3264, "country": "FR", "admin": "Île-de-France", "admin2": "75", "postCode": "75014"}',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="config",
            name="location_user_friendly",
            field=models.TextField(
                default="Paris 14 - Île-de-France (75) - FR", null=True
            ),
        ),
    ]
