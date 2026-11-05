import importlib
import importlib.util
import io
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from dcim.models import OUI, MACAddress, Manufacturer


class PopulateMACAddressOUIsTestCase(TestCase):
    """
    Exercise the data migration against the current models.
    """

    @staticmethod
    def populate():
        migration = importlib.import_module('dcim.migrations.0253_populate_mac_address_ouis')
        migration.populate_mac_address_ouis(apps, SimpleNamespace(connection=connection))

    @classmethod
    def setUpTestData(cls):
        # bulk_create() bypasses MACAddress.save(), leaving rows as they stand prior to the migration
        MACAddress.objects.bulk_create((
            MACAddress(mac_address='00:1B:21:00:00:01'),
            MACAddress(mac_address='00:1B:21:00:00:02'),
            MACAddress(mac_address='3C:FD:FE:00:00:01'),
            MACAddress(mac_address='02:00:00:00:00:01'),
            MACAddress(mac_address='01:00:5E:00:00:01'),
        ))

    def test_ouis_created_and_linked(self):
        self.populate()

        self.assertEqual(sorted(OUI.objects.values_list('prefix', flat=True)), ['00:1B:21', '3C:FD:FE'])
        self.assertEqual(OUI.objects.get(prefix='00:1B:21').mac_addresses.count(), 2)
        self.assertEqual(OUI.objects.get(prefix='3C:FD:FE').mac_addresses.count(), 1)
        self.assertIsNone(OUI.objects.first().manufacturer)

    def test_non_universal_addresses_skipped(self):
        self.populate()

        unlinked = MACAddress.objects.filter(oui__isnull=True).values_list('mac_address', flat=True)
        self.assertEqual(sorted(str(mac) for mac in unlinked), ['01:00:5E:00:00:01', '02:00:00:00:00:01'])

    def test_linked_in_single_update(self):
        with CaptureQueriesContext(connection) as ctx:
            self.populate()
        updates = [q['sql'] for q in ctx.captured_queries if q['sql'].startswith('UPDATE "dcim_macaddress"')]
        self.assertEqual(len(updates), 1)

    def test_last_updated_preserved(self):
        before = dict(MACAddress.objects.values_list('pk', 'last_updated'))
        self.populate()
        self.assertEqual(dict(MACAddress.objects.values_list('pk', 'last_updated')), before)

    def test_rerun_keeps_existing_ouis(self):
        self.populate()
        manufacturer = Manufacturer.objects.create(name='Intel', slug='intel')
        OUI.objects.filter(prefix='00:1B:21').update(manufacturer=manufacturer)

        # Running again (as after migrating back to 0252 and forward) must not fail on the unique prefix
        self.populate()
        self.assertEqual(sorted(OUI.objects.values_list('prefix', flat=True)), ['00:1B:21', '3C:FD:FE'])
        self.assertEqual(OUI.objects.get(prefix='00:1B:21').manufacturer, manufacturer)
        self.assertEqual(MACAddress.objects.filter(oui__isnull=False).count(), 3)

    def test_batches(self):
        migration = importlib.import_module('dcim.migrations.0253_populate_mac_address_ouis')
        original_batch_size = migration.BATCH_SIZE
        migration.BATCH_SIZE = 2
        self.addCleanup(setattr, migration, 'BATCH_SIZE', original_batch_size)

        self.populate()
        self.assertEqual(MACAddress.objects.filter(oui__isnull=False).count(), 3)


class OUIToCSVScriptTestCase(SimpleTestCase):
    """
    Test the conversion of the IEEE registry by scripts/oui_to_csv.py.
    """

    REGISTRY = (
        'Registry,Assignment,Organization Name,Organization Address\n'
        'MA-L,001B21,Intel Corporate,"Lot 8, Jalan Hi-Tech 2/3 Kulim Kedah MY 09000"\n'
        'MA-L,3CFDFE,Intel Corporate,"Lot 8, Jalan Hi-Tech 2/3 Kulim Kedah MY 09000"\n'
        'MA-L,00000C,"Cisco Systems, Inc",170 WEST TASMAN DRIVE San Jose CA US 95134\n'
        'MA-L,ACDE48,Private,\n'
        'MA-M,8C1F64,Intel Corporate,\n'
    )
    MANUFACTURERS = (
        'organization,manufacturer\n'
        'Intel Corporate,intel\n'
        '"CISCO SYSTEMS, INC",cisco\n'
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Path(settings.BASE_DIR).parent / 'scripts' / 'oui_to_csv.py'
        spec = importlib.util.spec_from_file_location('oui_to_csv', path)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

    def convert(self, **existing):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / 'oui.csv'
            manufacturers = Path(tmp) / 'manufacturers.csv'
            registry.write_text(self.REGISTRY, encoding='utf-8')
            manufacturers.write_text(self.MANUFACTURERS, encoding='utf-8')

            output = io.StringIO()
            self.script.convert(
                self.script.read_csv(registry),
                self.script.load_manufacturers(manufacturers),
                existing.get('existing', {}),
                output,
            )
        return output.getvalue().splitlines()

    def test_convert(self):
        self.assertEqual(self.convert(), [
            'id,prefix,manufacturer,description',
            ',00:1B:21,intel,Intel Corporate',
            ',3C:FD:FE,intel,Intel Corporate',
            ',00:00:0C,cisco,"Cisco Systems, Inc"',
        ])

    def test_existing_objects_identified(self):
        rows = self.convert(existing={'00:1B:21': '42'})
        self.assertEqual(rows[1], '42,00:1B:21,intel,Intel Corporate')
        self.assertEqual(rows[2], ',3C:FD:FE,intel,Intel Corporate')

    def test_load_existing_accepts_netbox_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            export = Path(tmp) / 'export.csv'
            export.write_text('ID,Prefix,Manufacturer\n42,00:1b:21,Intel\n', encoding='utf-8')
            self.assertEqual(self.script.load_existing(export), {'00:1B:21': '42'})

    def test_contrib_mapping_has_expected_columns(self):
        path = Path(settings.BASE_DIR).parent / 'contrib' / 'oui_manufacturers.csv'
        manufacturers = self.script.load_manufacturers(path)
        self.assertEqual(manufacturers['juniper networks'], 'juniper')
        for slug in manufacturers.values():
            self.assertEqual(Manufacturer._meta.get_field('slug').clean(slug, None), slug)
