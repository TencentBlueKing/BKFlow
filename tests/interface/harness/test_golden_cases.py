"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.

Versioned P0 Golden Case execution, not fixture-only schema checks.
"""

from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tests.interface.harness.golden_runner import (
    GoldenCatalog,
    _manifest,
    run_golden_case,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures/harness/golden_cases.yaml"
GROUP_COUNTS = {
    "positive_selection": 8,
    "ambiguous_requires_clarification": 6,
    "zero_candidate": 4,
    "schema_validation_error": 4,
    "schema_drift": 3,
    "idempotent_draft_retry": 3,
    "forged_identity_rejected": 2,
}
pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def golden_cases():
    """Load only the reviewed versioned Golden Case fixture."""
    fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["fixture_version"] == "harness-p0-golden-v1"
    return fixture["cases"]


def test_golden_fixture_has_exactly_the_approved_groups_and_case_contract(golden_cases):
    """A release gate cannot silently shrink, rename, or de-pin its 30 examples."""
    assert len(golden_cases) == 30
    assert Counter(case["group"] for case in golden_cases) == GROUP_COUNTS
    assert len({case["id"] for case in golden_cases}) == 30
    for case in golden_cases:
        assert set(case) == {
            "id",
            "group",
            "query",
            "registry_snapshot",
            "expected_tool_sequence",
            "expected_capability",
            "final_state",
            "forbidden_side_effects",
        }
        assert case["expected_tool_sequence"]
        assert case["forbidden_side_effects"]
        if case["expected_capability"]:
            assert len(case["expected_capability"]["schema_hash"]) == 64
            assert set(case["expected_capability"]) == {
                "capability_ref",
                "plugin_type",
                "source_key",
                "code",
                "resolved_version",
                "schema_hash",
            }
    selected_groups = {
        "positive_selection",
        "schema_validation_error",
        "schema_drift",
        "idempotent_draft_retry",
        "forged_identity_rejected",
    }
    assert all(case["expected_capability"] for case in golden_cases if case["group"] in selected_groups)


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config", return_value=None)
@patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
def test_selected_golden_component_uses_the_real_facade_converter_and_plugin_schema_service(
    mock_library, _space_config, golden_cases
):
    """Golden selection must retain every production boundary after provider I/O."""
    from pipeline.component_framework.models import ComponentModel

    from bkflow.harness.services.capability_ref import encode_capability_ref
    from bkflow.harness.services.projection import CapabilityProjection
    from bkflow.harness.services.resolver import CapabilityResolver, SchemaDriftError
    from bkflow.plugin.services.plugin_schema_service import PluginSchemaService

    ComponentModel.objects.create(code="golden_real_component", version="v1.0.0", name="golden-real", status=True)
    component = MagicMock()
    component.desc = "governed golden component"
    component.inputs_format.return_value = [{"key": "host", "type": "string", "required": True}]
    component.outputs_format.return_value = []
    mock_library.get_component_class.return_value = component
    service = PluginSchemaService(space_id=1, username="golden-actor")
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "none"},
        "capabilities": [],
    }
    card = CapabilityProjection(service, manifest=manifest).search("golden real")["capabilities"][0]
    resolved = CapabilityResolver(service, manifest=manifest).resolve(
        card["capability_ref"], expected_schema_hash=card["schema_hash"]
    )

    assert resolved.capability_ref == encode_capability_ref("component", None, "golden_real_component", "v1.0.0")
    assert resolved.resolved_version == "v1.0.0"
    with pytest.raises(SchemaDriftError):
        CapabilityResolver(service, manifest=manifest).resolve(card["capability_ref"], expected_schema_hash="0" * 64)

    from bkflow.harness.services.facade import HarnessFacade
    from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
    from bkflow.pipeline_validate.handler import ValidatorHandler

    positive = next(case for case in golden_cases if case["id"] == "positive-component-host")
    real_validate = HarnessFacade.validate_workflow
    real_convert = A2FlowV2Converter.convert_with_metadata
    real_pipeline_validate = ValidatorHandler.validate
    with patch.object(HarnessFacade, "validate_workflow", autospec=True, side_effect=real_validate) as facade_spy:
        with patch.object(
            A2FlowV2Converter, "convert_with_metadata", autospec=True, side_effect=real_convert
        ) as converter_spy:
            with patch.object(ValidatorHandler, "validate", side_effect=real_pipeline_validate) as validator_spy:
                observation = run_golden_case(positive)

    assert observation.final_state == "VALIDATING"
    assert facade_spy.call_count == 1
    assert converter_spy.call_count == 1
    assert validator_spy.call_count == 1

    facade_mutation = next(case for case in golden_cases if case["id"] == "positive-remote-endpoint")
    with patch.object(HarnessFacade, "validate_workflow", side_effect=RuntimeError("facade delegation removed")):
        with pytest.raises(RuntimeError, match="facade delegation removed"):
            run_golden_case(facade_mutation)

    converter_mutation = next(case for case in golden_cases if case["id"] == "positive-uniform-v4-region")
    with patch.object(A2FlowV2Converter, "convert_with_metadata", side_effect=RuntimeError("converter failed")):
        with pytest.raises(AssertionError):
            run_golden_case(converter_mutation)


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config", return_value=None)
@patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
def test_selected_golden_remote_uses_the_real_plugin_schema_service(mock_client, _space_config):
    """The remote selected-card path keeps provider version data behind the real service."""
    from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
    from bkflow.harness.services.projection import CapabilityProjection
    from bkflow.harness.services.resolver import CapabilityResolver
    from bkflow.plugin.services.plugin_schema_service import PluginSchemaService

    BKPlugin.objects.create(
        code="golden_remote", name="golden remote", tag=1, logo_url="", introduction="", managers=[]
    )
    BKPluginAuthorization.objects.create(
        code="golden_remote", status=AuthStatus.authorized.value, config={"white_list": ["*"]}
    )
    mock_client.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.0.0", "2.0.0"], "inputs": [], "outputs": []},
    }
    service = PluginSchemaService(space_id=1, username="golden-actor")
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "none"},
        "capabilities": [],
    }
    card = CapabilityProjection(service, manifest=manifest).search("golden remote")["capabilities"][0]
    resolved = CapabilityResolver(service, manifest=manifest).resolve(
        card["capability_ref"], expected_schema_hash=card["schema_hash"]
    )

    assert resolved.plugin_type == "remote_plugin"
    assert resolved.resolved_version == "2.0.0"


def test_selected_golden_v4_and_legacy_paths_use_real_service_without_source_or_version_fallback():
    """The shared Golden adapter proves source/version pins against production service methods."""
    from bkflow.harness.services.capability_ref import encode_capability_ref
    from bkflow.harness.services.resolver import (
        CapabilityResolutionError,
        CapabilityResolver,
        SchemaDriftError,
    )
    from bkflow.plugin.services.plugin_schema_service import PluginSchemaService

    v4 = {
        "plugin_type": "uniform_api",
        "source_key": "golden-source-a",
        "code": "same-code",
        "version": "4.0.0",
        "input_key": "region",
    }
    with GoldenCatalog(v4) as catalog:
        assert isinstance(catalog.service, PluginSchemaService)
        resolver = CapabilityResolver(catalog.service, manifest=_manifest())
        resolved = resolver.resolve(encode_capability_ref("uniform_api", "golden-source-a", "same-code", "4.0.0"))
        assert resolved.source_key == "golden-source-a"
        with pytest.raises(CapabilityResolutionError) as missing_source:
            resolver.resolve(encode_capability_ref("uniform_api", "golden-source-b", "same-code", "4.0.0"))
        assert missing_source.value.code == "CAPABILITY_FORBIDDEN"

    component = {
        "plugin_type": "component",
        "source_key": None,
        "code": "golden-versioned",
        "version": "1.0.0",
        "input_key": "host",
    }
    with GoldenCatalog(component) as catalog:
        with pytest.raises(SchemaDriftError):
            CapabilityResolver(catalog.service, manifest=_manifest()).resolve(
                encode_capability_ref("component", None, "golden-versioned", "9.9.9")
            )

    legacy = {
        "plugin_type": "uniform_api",
        "source_key": None,
        "code": "legacy-source-none",
        "version": "1.0.0",
        "input_key": "cluster",
    }
    with GoldenCatalog(legacy) as catalog:
        resolved = CapabilityResolver(catalog.service, manifest=_manifest()).resolve(
            encode_capability_ref("uniform_api", None, "legacy-source-none", "unversioned")
        )
        assert resolved.source_key is None


@pytest.mark.parametrize("case_index", range(30))
def test_every_golden_case_executes_its_real_governed_chain(golden_cases, case_index):
    """Exercise Task 5--8 behavior and assert its declared outcome and no forbidden action."""
    case = golden_cases[case_index]

    observed = run_golden_case(case)

    assert observed.tool_sequence == case["expected_tool_sequence"]
    assert observed.final_state == case["final_state"]
    assert not set(case["forbidden_side_effects"]).intersection(observed.side_effects)
    if case["group"] in {"ambiguous_requires_clarification", "zero_candidate"}:
        assert observed.candidates == case["registry_snapshot"]["candidate_refs"]
    if case["expected_capability"]:
        assert observed.capability == case["expected_capability"]
