# Generated by Django 3.2.15 on 2022-11-04 09:09

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
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("streaming_url", models.TextField(default="", null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
