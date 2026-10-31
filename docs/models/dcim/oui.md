# OUIs

An organizationally unique identifier (OUI) is the 24-bit prefix which the IEEE assigns to an organization, and which forms the first three octets of every universally administered [MAC address](./macaddress.md) that organization issues. Assigning a [manufacturer](./manufacturer.md) to an OUI identifies the vendor of all MAC addresses bearing that prefix, which can then be filtered by manufacturer.

NetBox creates an OUI automatically the first time a MAC address with a new prefix is saved. These records have no manufacturer until one is assigned, either individually or by bulk import. Locally administered and multicast MAC addresses are not issued under an OUI, and are not linked to one.

!!! tip "Importing the IEEE registry"
    `scripts/oui_to_csv.py` converts the [IEEE MA-L registry](https://standards-oui.ieee.org/oui/oui.csv) into a CSV file suitable for bulk import, using a list of manufacturer names such as `contrib/oui_manufacturers.csv`. Pass it an export of the existing OUIs using `--existing` so that rows for prefixes NetBox already knows about update those objects rather than being rejected as duplicates.

## Fields

### Prefix

The first three octets of the MAC address. This value is stored in colon-separated uppercase form (for example, `00:1B:21`) and must be unique. A prefix with the multicast or locally administered bit set is not valid, and the prefix of an OUI cannot be changed while any MAC addresses are linked to it.

### Manufacturer

The [manufacturer](./manufacturer.md) to which this OUI is assigned (optional). A manufacturer can't be deleted while OUIs are assigned to it.

### Description

An optional human-readable description of the OUI.

### Comments

Free-form Markdown-supported notes regarding the OUI.
