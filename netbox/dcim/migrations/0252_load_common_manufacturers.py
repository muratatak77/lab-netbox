from django.db import migrations

MANUFACTURERS = (
    ('Arista', 'arista'),
    ('Fortinet', 'fortinet'),
    ('MikroTik', 'mikrotik'),
    ('Palo Alto Networks', 'palo-alto-networks'),
    ('Ubiquiti', 'ubiquiti'),
)


def load_manufacturers(apps, schema_editor):
    """
    Create the manufacturers most installations add by hand on their first day.
    """
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    db_alias = schema_editor.connection.alias
    Manufacturer.objects.using(db_alias).bulk_create(
        [Manufacturer(name=name, slug=slug) for name, slug in MANUFACTURERS]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0251_fix_ltree_cascade_triggers'),
    ]

    operations = [
        migrations.RunPython(load_manufacturers, migrations.RunPython.noop),
    ]
