"""P4 generation-feedback Harness view."""

from rest_framework.decorators import api_view, permission_classes

from bkflow.apigw.serializers.harness.feedback import SubmitGenerationFeedbackSerializer
from bkflow.apigw.views.harness.common import dispatch, harness_view
from bkflow.harness.permissions import HarnessPermission


@harness_view("submit_generation_feedback")
@api_view(["POST"])
@permission_classes([HarnessPermission])
def submit_generation_feedback(request, space_id):
    """Record one consent-bound observation through the trusted Harness facade."""
    return dispatch(request, SubmitGenerationFeedbackSerializer, "submit_generation_feedback")
