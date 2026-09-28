"""P3 release and execution Harness views."""

from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.release_execution import (
    ControlWorkflowExecutionSerializer,
    GetWorkflowExecutionSerializer,
    PrepareReleaseSerializer,
    PublishWorkflowSerializer,
    StartWorkflowExecutionSerializer,
)
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("prepare_release")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def prepare_release(request, space_id):
    return dispatch(request, PrepareReleaseSerializer, "prepare_release")


@harness_view("publish_workflow")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def publish_workflow(request, space_id):
    return dispatch(request, PublishWorkflowSerializer, "publish_workflow")


@harness_view("start_workflow_execution")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def start_workflow_execution(request, space_id):
    return dispatch(request, StartWorkflowExecutionSerializer, "start_workflow_execution")


@harness_view("get_workflow_execution")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def get_workflow_execution(request, space_id):
    return dispatch(request, GetWorkflowExecutionSerializer, "get_workflow_execution")


@harness_view("control_workflow_execution")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def control_workflow_execution(request, space_id):
    return dispatch(request, ControlWorkflowExecutionSerializer, "control_workflow_execution")
