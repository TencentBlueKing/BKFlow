"""Capability Harness P0 views."""
from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.capabilities import (
    PluginSchemaSerializer,
    SearchCapabilitiesSerializer,
)
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("search_workflow_capabilities")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def search_workflow_capabilities(request, space_id):
    return dispatch(request, SearchCapabilitiesSerializer, "search_workflow_capabilities")


@harness_view("get_plugin_schema")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def get_plugin_schema(request, space_id):
    return dispatch(request, PluginSchemaSerializer, "get_plugin_schema")
