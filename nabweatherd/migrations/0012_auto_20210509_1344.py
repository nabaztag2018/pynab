# Generated by Django 3.0.14 on 2021-05-09 13:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nabweatherd', '0011_auto_20210509_1321'),
    ]

    operations = [
        migrations.AlterField(
            model_name='config',
            name='location_user_friendly',
            field=models.TextField(default='Concarneau - Bretagne (29) - FR'),
        ),
    ]
