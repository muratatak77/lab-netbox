from dcim.models import OUI
from netbox.api.fields import RelatedObjectCountField
from netbox.api.serializers import PrimaryModelSerializer

from .manufacturers import ManufacturerSerializer

__all__ = (
    'OUISerializer',
)


class OUISerializer(PrimaryModelSerializer):
    manufacturer = ManufacturerSerializer(nested=True, required=False, allow_null=True)

    # Related object counts
    mac_address_count = RelatedObjectCountField('mac_addresses')

    class Meta:
        model = OUI
        fields = [
            'id', 'url', 'display_url', 'display', 'prefix', 'manufacturer', 'description', 'owner', 'comments', 'tags',
            'custom_fields', 'created', 'last_updated', 'mac_address_count',
        ]
        brief_fields = ('id', 'url', 'display', 'prefix', 'manufacturer', 'description')
