"""Workflow Harness P0 views."""
from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.workflow import (
    CreateDraftSerializer,
    ValidateWorkflowSerializer,
)
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("validate_workflow")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def validate_workflow(request, space_id):
    return dispatch(request, ValidateWorkflowSerializer, "validate_workflow")


@harness_view("create_workflow_draft")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def create_workflow_draft(request, space_id):
    return dispatch(request, CreateDraftSerializer, "create_workflow_draft")
