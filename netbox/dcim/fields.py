from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext as _
from netaddr import EUI, AddrFormatError, eui64_unix_expanded, mac_unix_expanded

from .lookups import PathContains

__all__ = (
    'MACAddressField',
    'OUIField',
    'PathField',
    'WWNField',
    'get_oui_prefix',
)


class mac_unix_expanded_uppercase(mac_unix_expanded):
    word_fmt = '%.2X'


class eui64_unix_expanded_uppercase(eui64_unix_expanded):
    word_fmt = '%.2X'


#
# Fields
#

class MACAddressField(models.Field):
    description = 'PostgreSQL MAC Address field'

    def python_type(self):
        return EUI

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_internal_type(self):
        return 'CharField'

    def to_python(self, value):
        if value is None:
            return value
        if type(value) is str:
            value = value.replace(' ', '')
        try:
            return EUI(value, version=48, dialect=mac_unix_expanded_uppercase)
        except AddrFormatError:
            raise ValidationError(_("Invalid MAC address format: {value}").format(value=value))

    def db_type(self, connection):
        return 'macaddr'

    def get_prep_value(self, value):
        if not value:
            return None
        return str(self.to_python(value))


class OUIField(models.CharField):
    """
    The first three octets of a MAC address, always stored as colon-separated uppercase hexadecimal (AA:BB:CC). Hyphens
    and lowercase digits are also accepted on input, as REST API serializers validate a value before it is normalized.
    """
    description = 'Organizationally unique identifier'
    default_validators = [
        RegexValidator(
            regex=r'^[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){2}$',
            message=_("Enter three hexadecimal octets (for example, 00:1B:21)."),
        ),
    ]

    @staticmethod
    def normalize(value):
        return value.strip().upper().replace('-', ':')

    def to_python(self, value):
        value = super().to_python(value)
        return value if value is None else self.normalize(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return value if value is None else self.normalize(value)

    def pre_save(self, model_instance, add):
        value = self.to_python(super().pre_save(model_instance, add))
        setattr(model_instance, self.attname, value)
        return value


class WWNField(models.Field):
    description = 'World Wide Name field'

    def python_type(self):
        return EUI

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_internal_type(self):
        return 'CharField'

    def to_python(self, value):
        if value is None:
            return value
        try:
            return EUI(value, version=64, dialect=eui64_unix_expanded_uppercase)
        except AddrFormatError:
            raise ValidationError(_("Invalid WWN format: {value}").format(value=value))

    def db_type(self, connection):
        return 'macaddr8'

    def get_prep_value(self, value):
        if not value:
            return None
        return str(self.to_python(value))


class PathField(ArrayField):
    """
    An ArrayField which holds a set of objects, each identified by a (type, ID) tuple.
    """
    def __init__(self, **kwargs):
        kwargs['base_field'] = models.CharField(max_length=40)
        super().__init__(**kwargs)


PathField.register_lookup(PathContains)


#
# Utilities
#

def get_oui_prefix(mac_address):
    """
    Return the OUI portion (AA:BB:CC) of a MAC address, or None if the address does not carry one: locally administered
    and multicast addresses are identified by the two lowest bits of the first octet.
    """
    prefix = str(MACAddressField().to_python(mac_address))[:8]
    return None if int(prefix[:2], 16) & 0b11 else prefix
