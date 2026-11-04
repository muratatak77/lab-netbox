from django.db import migrations
from django.db.models import CharField, OuterRef, Subquery
from django.db.models.functions import Cast, Left, Upper

BATCH_SIZE = 1000


def get_prefix(mac_address):
    """
    Return the OUI prefix of a MAC address, or None if it is locally administered or multicast.
    """
    prefix = str(mac_address)[:8].upper()
    return None if int(prefix[:2], 16) & 0b11 else prefix


def populate_mac_address_ouis(apps, schema_editor):
    """
    Create an OUI for each prefix found among the existing MAC addresses, and link the addresses to them.
    """
    MACAddress = apps.get_model('dcim', 'MACAddress')
    OUI = apps.get_model('dcim', 'OUI')
    db_alias = schema_editor.connection.alias
    mac_addresses = MACAddress.objects.using(db_alias)

    # Reduce the addresses to their distinct prefixes in the database (PostgreSQL renders macaddr as aa:bb:cc:dd:ee:ff)
    address_prefix = Upper(Left(Cast('mac_address', CharField()), 8))
    prefixes = {
        get_prefix(prefix)
        for prefix in mac_addresses.order_by().annotate(prefix=address_prefix)
        .values_list('prefix', flat=True).distinct().iterator()
    }
    prefixes.discard(None)
    OUI.objects.using(db_alias).bulk_create(
        [OUI(prefix=prefix) for prefix in sorted(prefixes)],
        batch_size=BATCH_SIZE,
    )

    # Link every address in a single UPDATE. Locally administered and multicast addresses have no matching OUI, so they
    # are left without one. update() leaves last_updated alone: this does not constitute a change to the MAC address.
    mac_addresses.filter(oui__isnull=True).update(
        oui=Subquery(
            OUI.objects.using(db_alias).filter(
                prefix=Upper(Left(Cast(OuterRef('mac_address'), CharField()), 8))
            ).values('pk')[:1]
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0252_oui'),
    ]

    operations = [
        # Reversing 0252 removes both the table and the column, so there is nothing to undo here
        migrations.RunPython(populate_mac_address_ouis, migrations.RunPython.noop),
    ]
