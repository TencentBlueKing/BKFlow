"""Regressions from the real Agent's schema/type repair loop."""

import pytest

from bkflow.harness.services.validator import WorkflowValidator
from tests.interface.harness.services.test_validator import (
    FixtureConverter,
    FixtureResolver,
)

pytest_plugins = ("tests.interface.harness.services.test_validator",)


@pytest.mark.django_db
@pytest.mark.parametrize("node_type", ["pause_node", "ServiceActivity", [], {}])
def test_plugin_code_is_not_a_workflow_node_type(context, resolved_capability, request_data, node_type):
    request_data["a2flow"]["nodes"][0]["type"] = node_type
    response = WorkflowValidator(context, resolver=FixtureResolver(resolved_capability, [])).validate_workflow(
        request_data
    )
    error = response["errors"][0]
    assert error["code"] == "A2FLOW_NODE_TYPE_INVALID"
    assert error["path"] == "a2flow.nodes.0.type"
    assert "Activity" in error["message"]
    assert "plugin code" in error["message"]


@pytest.mark.django_db
def test_missing_credential_ref_teaches_explicit_null(context, resolved_capability, request_data):
    del request_data["bindings"][0]["credential_ref"]
    response = WorkflowValidator(context, resolver=FixtureResolver(resolved_capability, [])).validate_workflow(
        request_data
    )
    error = response["errors"][0]
    assert error["code"] == "BINDING_FIELD_REQUIRED"
    assert error["path"] == "bindings.0.credential_ref"
    assert "null" in error["message"]


@pytest.mark.django_db
def test_null_credential_remains_valid(context, resolved_capability, request_data):
    response = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)
    assert request_data["bindings"][0]["credential_ref"] is None
    assert response["ok"] is True


@pytest.mark.django_db
def test_duplicate_binding_points_to_second_binding(context, resolved_capability, request_data):
    request_data["bindings"].append(dict(request_data["bindings"][0]))
    resolver = FixtureResolver(resolved_capability, [])
    response = WorkflowValidator(context, resolver=resolver).validate_workflow(request_data)
    assert len(resolver.calls) == 2  # Keep fresh authorization before semantic validation.
    error = response["errors"][0]
    assert error["code"] == "BINDING_NODE_DUPLICATE"
    assert error["path"] == "bindings.1.node_id"
    assert "exactly one binding" in error["message"]
