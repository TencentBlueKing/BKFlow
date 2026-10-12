"""Federated knowledge-search transport contracts."""

from rest_framework import serializers

from .common import ClientContextSerializer, ClosedSerializer
from .workflow import UUIDStringField


class KnowledgeSearchSerializer(ClosedSerializer):
    """Accept only bounded query data; all routing identity comes from trusted context."""

    query = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=20, default=10)
    run_id = UUIDStringField(required=False)
    data_classification = serializers.RegexField(
        r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$", required=False, default="internal", max_length=64
    )
    client_context = ClientContextSerializer(required=False, default=dict)
