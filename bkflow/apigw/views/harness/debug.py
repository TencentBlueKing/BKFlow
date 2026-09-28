"""Revision-bound P2 Harness debug views."""

from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.debug import (
    ControlDebugSessionSerializer,
    GetDebugSessionSerializer,
    RunDebugSerializer,
    StartDebugSessionSerializer,
)
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("start_debug_session")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def start_debug_session(request, space_id):
    """Establish an isolated session for one validated revision."""
    return dispatch(request, StartDebugSessionSerializer, "start_debug_session")


@harness_view("run_debug")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def run_debug(request, space_id):
    """Dispatch one policy-gated step or global debug operation."""
    return dispatch(request, RunDebugSerializer, "run_debug")


@harness_view("get_debug_session")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def get_debug_session(request, space_id):
    """Read one owned session and its bounded Evidence history."""
    return dispatch(request, GetDebugSessionSerializer, "get_debug_session")


@harness_view("control_debug_session")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def control_debug_session(request, space_id):
    """Apply one closed, idempotent control to an owned session."""
    return dispatch(request, ControlDebugSessionSerializer, "control_debug_session")
