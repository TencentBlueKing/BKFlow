"""Admin storage selection must not require dummy text for JSON values."""

import json

import pytest
from django.contrib.admin.sites import AdminSite

from bkflow.space.admin import SpaceConfigAdmin
from bkflow.space.models import SpaceConfig


def _form(data):
    form_class = SpaceConfigAdmin(SpaceConfig, AdminSite()).get_form(None)
    return form_class(data=data)


@pytest.mark.django_db
def test_json_deployment_form_allows_empty_text():
    binding = {
        "platform_key": "test-platform",
        "allowed_scope_types": [],
        "scope_type": None,
        "scope_value": None,
        "target_environment": "stag",
        "risk_policy_version": "test-policy",
        "mcp_contract_version": "1.4.0",
    }
    form = _form(
        {
            "space_id": 999,
            "name": "harness_deployment",
            "value_type": "JSON",
            "text_value": "",
            "json_value": json.dumps(binding),
        }
    )
    assert form.is_valid(), form.errors
    assert form.save().text_value == ""


@pytest.mark.django_db
def test_deployment_form_rejects_invalid_binding_before_save():
    form = _form(
        {"space_id": 999, "name": "harness_deployment", "value_type": "JSON", "text_value": "{}", "json_value": "{}"}
    )
    assert not form.is_valid()
    assert "json_value" in form.errors


@pytest.mark.django_db
def test_text_config_still_requires_text():
    form = _form({"space_id": 999, "name": "harness_enabled", "value_type": "TEXT", "text_value": ""})
    assert not form.is_valid()
    assert "text_value" in form.errors


@pytest.mark.django_db
def test_deployment_form_rejects_wrong_storage_type():
    form = _form({"space_id": 999, "name": "harness_deployment", "value_type": "TEXT", "text_value": "{}"})
    assert not form.is_valid()
    assert "value_type" in form.errors
