"""Capability discovery transport contracts."""

from rest_framework import serializers

from bkflow.harness.services.capability_ref import MAX_CAPABILITY_REF_LENGTH

from .common import ClosedSerializer


class StrictQueryField(serializers.CharField):
    """MCP 查询词必须是 JSON string，不能隐式把数字转换为字符串。"""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class SearchCapabilitiesSerializer(ClosedSerializer):
    query = StrictQueryField(min_length=1, max_length=256)
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=20, default=10)
    plugin_source = serializers.CharField(required=False, max_length=64)


class PluginSchemaSerializer(ClosedSerializer):
    """Accept only a card selected from the governed capability search result."""

    capability_ref = serializers.CharField(max_length=MAX_CAPABILITY_REF_LENGTH)
    expected_schema_hash = serializers.RegexField(r"^[a-f0-9]{64}$", max_length=64)
