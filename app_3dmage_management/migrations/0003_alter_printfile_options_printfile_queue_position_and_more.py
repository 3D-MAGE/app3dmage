# Generated by Django 5.2.3 on 2025-06-10 16:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_3dmage_management', '0002_alter_filament_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='printfile',
            options={'ordering': ['queue_position'], 'verbose_name': 'File di Stampa', 'verbose_name_plural': 'File di Stampa'},
        ),
        migrations.AddField(
            model_name='printfile',
            name='queue_position',
            field=models.PositiveIntegerField(default=0, verbose_name='Posizione in Coda'),
        ),
        migrations.AlterField(
            model_name='printfile',
            name='plate',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='app_3dmage_management.plate', verbose_name='Piatto Usato'),
        ),
        migrations.AlterField(
            model_name='printfile',
            name='printer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='print_files', to='app_3dmage_management.printer', verbose_name='Stampante Usata'),
        ),
    ]
