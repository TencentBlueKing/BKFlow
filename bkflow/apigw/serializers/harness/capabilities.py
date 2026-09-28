"""Capability discovery transport contracts."""
from rest_framework import serializers

from bkflow.harness.services.capability_ref import MAX_CAPABILITY_REF_LENGTH

from .common import ClosedSerializer


class SearchCapabilitiesSerializer(ClosedSerializer):
    query = serializers.CharField(max_length=256)
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=20, default=10)
    plugin_source = serializers.CharField(required=False, max_length=64)


class PluginSchemaSerializer(ClosedSerializer):
    """Accept only a card selected from the governed capability search result."""

    capability_ref = serializers.CharField(max_length=MAX_CAPABILITY_REF_LENGTH)
    expected_schema_hash = serializers.RegexField(r"^[a-f0-9]{64}$", max_length=64)
