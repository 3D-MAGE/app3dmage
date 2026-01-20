from django.db import migrations
from collections import defaultdict

def populate_spool_identifiers(apps, schema_editor):
    """
    Assegna un identificatore (A, B, C...) a ogni bobina esistente,
    raggruppandole per tipo di filamento e data di acquisto.
    """
    Spool = apps.get_model('app_3dmage_management', 'Spool')

    spool_groups = defaultdict(list)
    for spool in Spool.objects.all().order_by('pk'):
        spool_groups[(spool.filament_id, spool.purchase_date)].append(spool)

    for group_key, spools_in_group in spool_groups.items():
        for i, spool in enumerate(spools_in_group):
            spool.identifier = chr(ord('A') + i)
            spool.save(update_fields=['identifier'])

class Migration(migrations.Migration):

    dependencies = [
        # MODIFICA FONDAMENTALE: La dipendenza è la migrazione del Passo 2,
        # che ha creato il campo 'identifier'.
        # SOSTITUISCI '0019_spool_identifier' con il nome del file annotato al Passo 2.
        ('app_3dmage_management', '0019_alter_spool_options_spool_identifier_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_spool_identifiers, reverse_code=migrations.RunPython.noop),
    ]
