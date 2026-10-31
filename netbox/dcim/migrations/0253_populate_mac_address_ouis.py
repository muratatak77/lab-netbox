from django.db import migrations

BATCH_SIZE = 1000


def get_prefix(mac_address):
    """
    Return the OUI prefix of a MAC address, or None if it is locally administered or multicast.
    """
    prefix = str(mac_address)[:8]
    return None if int(prefix[:2], 16) & 0b11 else prefix


def populate_mac_address_ouis(apps, schema_editor):
    """
    Create an OUI for each prefix found among the existing MAC addresses, and link the addresses to them.
    """
    MACAddress = apps.get_model('dcim', 'MACAddress')
    OUI = apps.get_model('dcim', 'OUI')
    db_alias = schema_editor.connection.alias
    mac_addresses = MACAddress.objects.using(db_alias)

    prefixes = {
        get_prefix(mac_address)
        for mac_address in mac_addresses.order_by().values_list('mac_address', flat=True).distinct().iterator()
    }
    prefixes.discard(None)
    OUI.objects.using(db_alias).bulk_create(
        [OUI(prefix=prefix) for prefix in sorted(prefixes)],
        batch_size=BATCH_SIZE,
    )
    oui_ids = dict(OUI.objects.using(db_alias).values_list('prefix', 'pk'))

    # bulk_update() leaves last_updated alone: this does not constitute a change to the MAC address
    pending = []
    for mac_address in mac_addresses.order_by('pk').only('pk', 'mac_address').iterator(chunk_size=BATCH_SIZE):
        if prefix := get_prefix(mac_address.mac_address):
            mac_address.oui_id = oui_ids[prefix]
            pending.append(mac_address)
        if len(pending) >= BATCH_SIZE:
            mac_addresses.bulk_update(pending, ['oui'])
            pending.clear()
    if pending:
        mac_addresses.bulk_update(pending, ['oui'])


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0252_oui'),
    ]

    operations = [
        # Reversing 0252 removes both the table and the column, so there is nothing to undo here
        migrations.RunPython(populate_mac_address_ouis, migrations.RunPython.noop),
    ]
