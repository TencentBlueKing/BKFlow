# Generated by Django 3.2.15 on 2024-10-09 03:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('space', '0006_auto_20240823_1544'),
    ]

    operations = [
        migrations.AlterField(
            model_name='space',
            name='app_code',
            field=models.CharField(max_length=32, verbose_name='应用ID'),
        ),
    ]
