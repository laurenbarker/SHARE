# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-08-26 15:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('share', '0029_update_trigger_migrations_20160824_0322'),
    ]

    operations = [
        migrations.AddField(
            model_name='rawdata',
            name='app_label',
            field=models.TextField(db_index=True, null=True),
        ),
    ]