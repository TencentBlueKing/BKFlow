"""The pinned internal SDK must remain reachable after the Django upgrade."""

import pytest
from django.urls import resolve

views = pytest.importorskip("django_bkvision.views")


@pytest.mark.parametrize(
    "path,view,kwargs",
    [
        ("/bkvision/api/v1/datasource/query/", "query_datasource", {}),
        ("/bkvision/api/v1/field/field_1/preview_data/", "preview_field_data", {"uid": "field_1"}),
        ("/bkvision/bkcdn/js/app.js", "proxy_bkcdn", {"path": "js/app.js"}),
        ("/bkvision/api/v1/ai/session/session-1/", "session_instance_handler", {"session_code": "session-1"}),
        ("/bkvision/api/v1/ai/chat_completion/", "create_chat_completion", {}),
    ],
)
def test_sdk_routes_preserve_original_views_and_parameters(path, view, kwargs):
    """Route to the SDK's original decorated view, preserving authentication and parameters."""
    match = resolve(path)
    assert match.func is getattr(views, view)
    assert match.kwargs == kwargs
