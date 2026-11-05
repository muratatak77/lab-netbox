#!/usr/bin/env python3
"""Convert the IEEE MA-L registry into a CSV file for NetBox's OUI bulk import.

Usage: oui_to_csv.py <oui.csv> <manufacturers.csv> [--existing <export.csv>] > import.csv

<oui.csv> is the registry published at https://standards-oui.ieee.org/oui/oui.csv.
<manufacturers.csv> maps IEEE organization names to NetBox manufacturer slugs; registry
entries for any organization not listed are skipped, since the IEEE names thousands of
organizations which won't exist as manufacturers. contrib/oui_manufacturers.csv is a
starting point.

NetBox creates OUIs on its own as MAC addresses are saved, and the bulk import rejects a
duplicate prefix unless the row carries the ID of the existing object. To update these,
export the OUI list from NetBox (including the ID and Prefix columns) and pass it using
--existing.
"""

import argparse
import csv
import sys


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        yield from csv.DictReader(f)


def load_manufacturers(path):
    """Return a mapping of IEEE organization name (casefolded) to manufacturer slug."""
    return {row['organization'].strip().casefold(): row['manufacturer'].strip() for row in read_csv(path)}


def load_existing(path):
    """Return a mapping of prefix to object ID from a NetBox export, whose headers may be title-cased."""
    rows = ({key.lower(): value for key, value in row.items()} for row in read_csv(path))
    return {row['prefix'].upper(): row['id'] for row in rows}


def format_prefix(assignment):
    return ':'.join(assignment[i:i + 2] for i in (0, 2, 4)).upper()


def convert(registry, manufacturers, existing, output):
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(('id', 'prefix', 'manufacturer', 'description'))
    for row in registry:
        organization = row['Organization Name'].strip()
        if row['Registry'] != 'MA-L' or (slug := manufacturers.get(organization.casefold())) is None:
            continue
        prefix = format_prefix(row['Assignment'])
        writer.writerow((existing.get(prefix, ''), prefix, slug, organization[:200]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('registry', help='IEEE MA-L registry (oui.csv)')
    parser.add_argument('manufacturers', help='mapping of IEEE organization names to manufacturer slugs')
    parser.add_argument('--existing', help='OUI list exported from NetBox')
    args = parser.parse_args()

    existing = load_existing(args.existing) if args.existing else {}
    convert(read_csv(args.registry), load_manufacturers(args.manufacturers), existing, sys.stdout)


if __name__ == '__main__':
    main()
