"""Federated knowledge-search Harness P1 view."""

from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.knowledge import KnowledgeSearchSerializer
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("search_workflow_knowledge")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def search_workflow_knowledge(request, space_id):
    """Search only knowledge sources authorized by the trusted route context."""
    return dispatch(request, KnowledgeSearchSerializer, "search_workflow_knowledge")
