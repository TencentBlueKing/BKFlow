"""APIGW and BKAIDev configuration contracts for versioned Harness tools."""

from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from django.urls import resolve

from bkflow.harness.services.capability_ref import MAX_CAPABILITY_REF_LENGTH

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESOURCE_FILE = REPOSITORY_ROOT / "bkflow/apigw/management/commands/data/api-resources.yml"
DOCS_ROOT = REPOSITORY_ROOT / "bkflow/apigw/docs"
SPIKE_FILE = REPOSITORY_ROOT / "docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md"
P2_SPIKE_FILE = REPOSITORY_ROOT / "docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md"
P3_SPIKE_FILE = REPOSITORY_ROOT / "docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md"
P4_SPIKE_FILE = REPOSITORY_ROOT / "docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md"
HARNESS_OPERATIONS = {
    "harness_search_workflow_capabilities": "search_workflow_capabilities",
    "harness_get_plugin_schema": "get_plugin_schema",
    "harness_validate_workflow": "validate_workflow",
    "harness_create_workflow_draft": "create_workflow_draft",
    "harness_search_workflow_knowledge": "search_workflow_knowledge",
    "harness_start_debug_session": "start_debug_session",
    "harness_run_debug": "run_debug",
    "harness_get_debug_session": "get_debug_session",
    "harness_control_debug_session": "control_debug_session",
    "harness_prepare_release": "prepare_release",
    "harness_publish_workflow": "publish_workflow",
    "harness_start_workflow_execution": "start_workflow_execution",
    "harness_get_workflow_execution": "get_workflow_execution",
    "harness_control_workflow_execution": "control_workflow_execution",
    "harness_submit_generation_feedback": "submit_generation_feedback",
}
MUTATING_OPERATIONS = {
    "harness_start_debug_session",
    "harness_run_debug",
    "harness_control_debug_session",
    "harness_prepare_release",
    "harness_publish_workflow",
    "harness_start_workflow_execution",
    "harness_control_workflow_execution",
    "harness_submit_generation_feedback",
}


def _resource_contracts():
    """Return the expected public operation, route, view and documentation identity."""
    return {
        "harness_search_workflow_capabilities": {
            "route": "/space/{space_id}/harness/search_workflow_capabilities/",
            "view": "search_workflow_capabilities",
        },
        "harness_get_plugin_schema": {
            "route": "/space/{space_id}/harness/get_plugin_schema/",
            "view": "get_plugin_schema",
        },
        "harness_validate_workflow": {
            "route": "/space/{space_id}/harness/validate_workflow/",
            "view": "validate_workflow",
        },
        "harness_create_workflow_draft": {
            "route": "/space/{space_id}/harness/create_workflow_draft/",
            "view": "create_workflow_draft",
        },
        "harness_search_workflow_knowledge": {
            "route": "/space/{space_id}/harness/search_workflow_knowledge/",
            "view": "search_workflow_knowledge",
        },
        "harness_start_debug_session": {
            "route": "/space/{space_id}/harness/start_debug_session/",
            "view": "start_debug_session",
        },
        "harness_run_debug": {
            "route": "/space/{space_id}/harness/run_debug/",
            "view": "run_debug",
        },
        "harness_get_debug_session": {
            "route": "/space/{space_id}/harness/get_debug_session/",
            "view": "get_debug_session",
        },
        "harness_control_debug_session": {
            "route": "/space/{space_id}/harness/control_debug_session/",
            "view": "control_debug_session",
        },
        "harness_prepare_release": {
            "route": "/space/{space_id}/harness/prepare_release/",
            "view": "prepare_release",
        },
        "harness_publish_workflow": {
            "route": "/space/{space_id}/harness/publish_workflow/",
            "view": "publish_workflow",
        },
        "harness_start_workflow_execution": {
            "route": "/space/{space_id}/harness/start_workflow_execution/",
            "view": "start_workflow_execution",
        },
        "harness_get_workflow_execution": {
            "route": "/space/{space_id}/harness/get_workflow_execution/",
            "view": "get_workflow_execution",
        },
        "harness_control_workflow_execution": {
            "route": "/space/{space_id}/harness/control_workflow_execution/",
            "view": "control_workflow_execution",
        },
        "harness_submit_generation_feedback": {
            "route": "/space/{space_id}/harness/submit_generation_feedback/",
            "view": "submit_generation_feedback",
        },
    }


def _resources():
    """Load APIGW source definitions structurally, never by text substitution."""
    return yaml.safe_load(RESOURCE_FILE.read_text(encoding="utf-8"))


def _operation_inventory(resources):
    """Index each OpenAPI operation once by operation ID and path/method pair."""
    inventory = []
    for route, methods in resources["paths"].items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and "operationId" in operation:
                inventory.append((operation["operationId"], route, method))
    return inventory


def test_harness_resources_are_exact_post_routes_with_closed_gateway_authentication():
    """Four P0 and one P1 resource mirror the real Harness views."""
    resources = _resources()
    inventory = _operation_inventory(resources)
    operation_ids = [operation_id for operation_id, _route, _method in inventory]
    path_methods = [(route, method) for _operation_id, route, method in inventory]

    assert len(operation_ids) == len(set(operation_ids))
    assert len(path_methods) == len(set(path_methods))
    assert set(HARNESS_OPERATIONS).issubset(operation_ids)
    assert {operation_id for operation_id in operation_ids if operation_id.startswith("harness_")} == set(
        HARNESS_OPERATIONS
    )
    for operation_id, contract in _resource_contracts().items():
        route = contract["route"]
        operation = resources["paths"][route]["post"]
        resource = operation["x-bk-apigateway-resource"]

        assert operation["operationId"] == operation_id
        expected_parameters = [
            {
                "in": "header",
                "name": "X-Bk-Tenant-Id",
                "required": False,
                "schema": {"type": "string", "maxLength": 32},
                "description": "多租户开启时，全租户应用必填，单租户应用可省略（使用已认证应用租户）；必须与资源空间租户一致。若有已认证用户，其租户也必须一致。关闭多租户时忽略。",
            },
            {"in": "path", "name": "space_id", "schema": {"type": "string"}, "required": True, "description": ""},
        ]
        if operation_id in MUTATING_OPERATIONS:
            header_max_length = (
                128
                if operation_id in {"harness_start_workflow_execution", "harness_control_workflow_execution"}
                else 255
            )
            expected_parameters.append(
                {
                    "in": "header",
                    "name": "X-Idempotency-Key",
                    "schema": {"type": "string", "minLength": 1, "maxLength": header_max_length},
                    "required": False,
                    "description": "可选；提供时必须与 Body idempotency_key 完全一致",
                }
            )
        assert operation["parameters"] == expected_parameters
        assert resource["backend"] == {
            "method": "post",
            "path": "/{{env.api_sub_path}}apigw{}".format(route),
            "matchSubpath": False,
            "timeout": 0,
            "name": "default",
        }
        assert resource["authConfig"] == {
            "userVerifiedRequired": True,
            "appVerifiedRequired": True,
            "resourcePermissionRequired": True,
        }
        resolved_route = route.replace("{space_id}", "1")
        assert resolve("/apigw{}".format(resolved_route)).func.__name__ == contract["view"]


def test_schema_resource_accepts_only_a_governed_card_and_pinned_hash():
    """The APIGW contract cannot reopen raw code/source/version schema selection."""
    resources = _resources()
    schema = resources["paths"]["/space/{space_id}/harness/get_plugin_schema/"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]

    assert schema == {
        "type": "object",
        "required": ["capability_ref", "expected_schema_hash"],
        "additionalProperties": False,
        "properties": {
            "capability_ref": {"type": "string", "maxLength": MAX_CAPABILITY_REF_LENGTH},
            "expected_schema_hash": {
                "type": "string",
                "minLength": 64,
                "maxLength": 64,
                "pattern": "^[a-f0-9]{64}$",
            },
        },
    }


def test_knowledge_resource_exposes_only_bounded_query_data():
    """APIGW cannot advertise identity or routing fields that the closed serializer rejects."""
    resources = _resources()
    schema = resources["paths"]["/space/{space_id}/harness/search_workflow_knowledge/"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]

    assert schema == {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 2000},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
            "run_id": {"type": "string", "format": "uuid"},
            "data_classification": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "pattern": "^[A-Za-z][A-Za-z0-9_.-]{0,63}$",
                "default": "internal",
            },
            "client_context": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "conversation_ref": {"type": "string", "maxLength": 255},
                    "agent_release": {"type": "string", "maxLength": 255},
                },
            },
        },
    }


def test_p2_resources_publish_closed_tagged_debug_schemas():
    """The gateway advertises only the four bounded P2 domain request unions."""
    resources = _resources()
    schemas = {
        name: resources["paths"][contract["route"]]["post"]["requestBody"]["content"]["application/json"]["schema"]
        for name, contract in _resource_contracts().items()
        if name.startswith("harness_")
        and name in HARNESS_OPERATIONS
        and name
        not in {
            "harness_search_workflow_capabilities",
            "harness_get_plugin_schema",
            "harness_validate_workflow",
            "harness_create_workflow_draft",
            "harness_search_workflow_knowledge",
            "harness_prepare_release",
            "harness_publish_workflow",
            "harness_start_workflow_execution",
            "harness_get_workflow_execution",
            "harness_control_workflow_execution",
            "harness_submit_generation_feedback",
        }
    }

    assert schemas["harness_start_debug_session"] == {
        "type": "object",
        "required": ["run_id", "revision_id", "expected_plan_hash", "mode", "idempotency_key"],
        "additionalProperties": False,
        "properties": {
            "run_id": {"type": "string", "format": "uuid"},
            "revision_id": {"type": "string", "format": "uuid"},
            "expected_plan_hash": {
                "type": "string",
                "minLength": 64,
                "maxLength": 64,
                "pattern": "^[a-f0-9]{64}$",
            },
            "mode": {"type": "string", "enum": ["step", "global"]},
            "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 255},
        },
    }
    assert schemas["harness_get_debug_session"] == {
        "type": "object",
        "required": ["session_id"],
        "additionalProperties": False,
        "properties": {
            "session_id": {"type": "string", "format": "uuid"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            "cursor": {"type": "string", "maxLength": 512, "pattern": "^[A-Za-z0-9_-]+$"},
        },
    }
    run_schema = schemas["harness_run_debug"]
    control_schema = schemas["harness_control_debug_session"]
    step_mock, step_real, global_mock = run_schema["oneOf"]
    assert step_mock["properties"]["mode"] == {"type": "string", "enum": ["step"]}
    assert step_mock["properties"]["execution_mode"] == {"type": "string", "enum": ["mock"]}
    assert "approval_receipt_ref" not in step_mock["properties"]
    assert step_real["properties"]["mode"] == {"type": "string", "enum": ["step"]}
    assert step_real["properties"]["execution_mode"] == {"type": "string", "enum": ["real"]}
    assert step_real["properties"]["approval_receipt_ref"] == {"type": "string", "maxLength": 255}
    assert global_mock["properties"]["mode"] == {"type": "string", "enum": ["global"]}
    assert global_mock["properties"]["execution_mode"] == {"type": "string", "enum": ["mock"]}
    assert [branch["properties"]["action"]["enum"][0] for branch in control_schema["oneOf"]] == [
        "reset",
        "terminate",
        "set_node_mock",
        "set_context_var",
    ]


def test_harness_resource_documents_are_archived_byte_for_byte():
    """Every public Harness operation has the exact Chinese document in the generated archive."""
    with ZipFile(DOCS_ROOT / "apigw-docs.zip") as archive:
        archive_names = set(archive.namelist())
        for operation_id in HARNESS_OPERATIONS:
            document = DOCS_ROOT / "zh/{}.md".format(operation_id)
            archive_name = "zh/{}.md".format(operation_id)

            assert document.exists()
            assert archive_name in archive_names
            assert archive.read(archive_name) == document.read_bytes()
            text = document.read_text(encoding="utf-8")
            for required_text in ("可信字段", "不可信字段", "Envelope"):
                assert required_text in text
            assert "顶层固定为 10 个键" in text
            assert "顶层固定为 11 个键" not in text
            assert "bk_app_secret" not in text
            assert "credential://" not in text

            if operation_id == "harness_search_workflow_knowledge":
                for required_text in (
                    "ACL-before-retrieval",
                    "ADVISORY",
                    "Global",
                    "Public",
                    "Platform",
                    "Space",
                    "Scope",
                    "citation",
                    "64 KiB",
                ):
                    assert required_text in text
            elif operation_id not in {"harness_get_debug_session", "harness_get_workflow_execution"}:
                for required_text in ("idempotency_key", "DRAFT"):
                    assert required_text in text


def test_p3_resources_publish_closed_release_execution_schemas():
    """The five P3 OpenAPI schemas expose identifiers and safe intent, never authority or SDK material."""
    resources = _resources()
    schemas = {
        operation_id: resources["paths"][contract["route"]]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]
        for operation_id, contract in _resource_contracts().items()
        if operation_id
        in {
            "harness_prepare_release",
            "harness_publish_workflow",
            "harness_start_workflow_execution",
            "harness_get_workflow_execution",
            "harness_control_workflow_execution",
        }
    }

    assert schemas["harness_prepare_release"] == {
        "type": "object",
        "required": ["run_id", "revision_id", "expected_plan_hash", "idempotency_key"],
        "additionalProperties": False,
        "properties": {
            "run_id": {"type": "string", "format": "uuid"},
            "revision_id": {"type": "string", "format": "uuid"},
            "expected_plan_hash": {
                "type": "string",
                "minLength": 64,
                "maxLength": 64,
                "pattern": "^[a-f0-9]{64}$",
            },
            "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 255},
        },
    }
    assert schemas["harness_get_workflow_execution"] == {
        "type": "object",
        "required": ["execution_id"],
        "additionalProperties": False,
        "properties": {
            "execution_id": {"type": "string", "format": "uuid"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            "cursor": {"type": "string", "minLength": 1, "maxLength": 512},
        },
    }
    publish_branches = schemas["harness_publish_workflow"]["oneOf"]
    start_branches = schemas["harness_start_workflow_execution"]["oneOf"]
    control_branches = schemas["harness_control_workflow_execution"]["oneOf"]
    assert len(publish_branches) == 2
    assert len(start_branches) == 2
    assert len(control_branches) == 18
    assert "approval_request_id" not in publish_branches[0]["properties"]
    assert set(publish_branches[1]["required"][-2:]) == {"approval_request_id", "approval_receipt_ref"}
    assert "approval_request_id" not in start_branches[0]["properties"]
    assert set(start_branches[1]["required"][-2:]) == {"approval_request_id", "approval_receipt_ref"}
    assert [branch["properties"]["action"]["enum"][0] for branch in control_branches[::2]] == [
        "pause",
        "resume",
        "revoke",
        "retry",
        "skip",
        "callback",
        "forced_fail",
        "skip_exg",
        "skip_cpg",
    ]
    for operation_id, schema in schemas.items():
        rendered = repr(schema).lower()
        for forbidden in ("actor", "space_id", "task_ref", "runtime_node_id", "sdk", "token", "credential"):
            assert forbidden not in rendered, operation_id


def test_p3_documents_and_spike_freeze_the_single_mcp_agent_loop_and_external_gates():
    documents = "\n".join(
        (DOCS_ROOT / "zh/{}.md".format(operation_id)).read_text(encoding="utf-8")
        for operation_id in HARNESS_OPERATIONS
        if operation_id
        in {
            "harness_prepare_release",
            "harness_publish_workflow",
            "harness_start_workflow_execution",
            "harness_get_workflow_execution",
            "harness_control_workflow_execution",
        }
    )
    spike = P3_SPIKE_FILE.read_text(encoding="utf-8")

    for required_text in (
        "contract `1.3.0`",
        "14 cumulative Tools",
        "BKFlow Workflow Harness MCP",
        "BKAIDev Agent",
        "prepare → approve → publish → start → poll/control → poll",
        "CONTROL_UNCERTAIN",
        "START_UNCERTAIN",
        "get_workflow_execution",
        "SDK/token path",
        "deny",
    ):
        assert required_text in documents + spike
    for required_text in (
        "ReleasePolicy",
        "BLOCKED_BY_EXTERNAL_EVIDENCE",
        "NOT_RUN_EXTERNAL",
        "single Harness MCP",
    ):
        assert required_text in spike


def test_p4_resource_publishes_only_bounded_untrusted_feedback_fields():
    resources = _resources()
    schema = resources["paths"]["/space/{space_id}/harness/submit_generation_feedback/"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]

    assert schema == {
        "type": "object",
        "required": [
            "run_id",
            "revision_id",
            "expected_plan_hash",
            "feedback_type",
            "consent_scope",
            "idempotency_key",
        ],
        "additionalProperties": False,
        "properties": {
            "run_id": {"type": "string", "format": "uuid"},
            "revision_id": {"type": "string", "format": "uuid"},
            "expected_plan_hash": {
                "type": "string",
                "minLength": 64,
                "maxLength": 64,
                "pattern": "^[a-f0-9]{64}$",
            },
            "feedback_type": {
                "type": "string",
                "enum": ["ACCEPTED", "REJECTED", "CORRECTION", "RUNTIME_ISSUE", "BUSINESS_OUTCOME"],
            },
            "consent_scope": {"type": "string", "minLength": 1, "maxLength": 64},
            "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 255},
            "rating": {"type": "integer", "minimum": 1, "maximum": 5},
            "summary": {"type": "string", "minLength": 1, "maxLength": 4096},
            "correction_artifact_ref": {"type": "string", "minLength": 1, "maxLength": 255},
            "execution_id": {"type": "string", "format": "uuid"},
            "observed_outcome": {},
        },
    }
    rendered = repr(schema).lower()
    for forbidden in (
        "owner_ref",
        "reviewer_ref",
        "status",
        "target_system",
        "target_tier",
        "platform_app",
        "actor",
        "space_id",
    ):
        assert forbidden not in rendered


def test_p4_document_and_spike_freeze_single_agent_feedback_boundary_and_external_gates():
    document = (DOCS_ROOT / "zh/harness_submit_generation_feedback.md").read_text(encoding="utf-8")
    spike = P4_SPIKE_FILE.read_text(encoding="utf-8")

    for required_text in (
        "不可信 Evidence",
        "consent",
        "不自动学习",
        "Owner 控制面",
        "DRAFT",
        "contract `1.4.0`",
        "15 Tools",
    ):
        assert required_text in document
    for required_text in (
        "one SaaS-native Agent",
        "one logical Harness MCP",
        "contract `1.4.0`",
        "exactly 15 Tools",
        "pinned Prompt/model/policy/knowledge snapshots",
        "feedback Tool available only to intended spaces",
        "NOT_RUN_EXTERNAL",
        "BLOCKED_BY_EXTERNAL_EVIDENCE",
    ):
        assert required_text in spike
    for forbidden_text in ("Agent SDK", "second runtime"):
        assert "不引入 {}".format(forbidden_text) in spike


def test_p2_documents_publish_the_mock_first_agent_safe_debug_contract():
    """The generated user contract explains the P2 runtime without exposing a Token path."""
    documents = "\n".join(
        (DOCS_ROOT / "zh/{}.md".format(operation_id)).read_text(encoding="utf-8")
        for operation_id in HARNESS_OPERATIONS
        if operation_id.startswith("harness_")
        and operation_id
        in {
            "harness_start_debug_session",
            "harness_run_debug",
            "harness_get_debug_session",
            "harness_control_debug_session",
        }
    )

    for required_text in (
        "contract `1.2.0`",
        "BKFlow Workflow Harness MCP",
        "Mock",
        "approval receipt",
        "Token Broker",
        "fast acknowledgement + poll",
        "Token",
        "Agent",
    ):
        assert required_text in documents
    assert "global real 明确禁止" in documents
    assert "对 BKAIDev Agent 不可见" in documents


def test_p2_debug_documents_match_the_exact_domain_tagged_fields():
    """Published examples cannot invent fields or misstate optional control members."""
    run_document = (DOCS_ROOT / "zh/harness_run_debug.md").read_text(encoding="utf-8")
    control_document = (DOCS_ROOT / "zh/harness_control_debug_session.md").read_text(encoding="utf-8")

    for required_text in (
        "global 请求只接受 `inputs`",
        "Mock 决策必须先通过 `control_debug_session` 的 `set_node_mock`",
    ):
        assert required_text in run_document
    assert "mock_scheme" not in run_document

    for required_text in (
        "reset 的 `node_ids` 必填",
        "空数组不会重置任何节点",
        "terminate 的 `node_id` 可选",
        "set_node_mock 精确要求 `node_id`、`enabled`、`mock_result`、`mock_outputs`、`mock_error`",
    ):
        assert required_text in control_document


def test_control_document_freezes_the_four_terminate_state_semantics():
    """ACTIVE and RUNNING termination must not be collapsed into one misleading rule."""
    document = (DOCS_ROOT / "zh/harness_control_debug_session.md").read_text(encoding="utf-8")

    for required_text in (
        "ACTIVE | 缺省 | 无 Engine task，直接关闭 Session",
        "ACTIVE | 提供 | 拒绝",
        "RUNNING | 缺省 | 终止当前 Session 绑定的 task",
        "RUNNING | 提供 | 终止该 task 的指定节点",
    ):
        assert required_text in document
    for misleading_text in (
        "未提供时终止全局 task",
        "不提供时终止全局调试 task",
    ):
        assert misleading_text not in document


def test_p2_spike_records_nine_direct_agent_tools_without_claiming_external_acceptance():
    """Repository mapping stays distinct from live BKAIDev mounting/readback evidence."""
    spike = P2_SPIKE_FILE.read_text(encoding="utf-8")

    for tool, operation_id in {
        "start_debug_session": "harness_start_debug_session",
        "run_debug": "harness_run_debug",
        "get_debug_session": "harness_get_debug_session",
        "control_debug_session": "harness_control_debug_session",
    }.items():
        assert tool in spike
        assert operation_id in spike
    for required_text in (
        "nine cumulative",
        "only LLM caller",
        "selects these public Tools directly",
        "NOT_RUN_EXTERNAL / BLOCKED_BY_EXTERNAL_EVIDENCE",
    ):
        assert required_text in spike


def test_spike_records_only_provisional_bkaidev_agent_configuration_and_external_evidence_block():
    """The local configuration contract cannot turn unavailable BKAIDev probes into PASS evidence."""
    spike = SPIKE_FILE.read_text(encoding="utf-8")

    for probe_id in range(1, 8):
        assert "SP-{:02d}".format(probe_id) in spike
    for required_text in (
        "BLOCKED_BY_EXTERNAL_EVIDENCE",
        "NOT_RUN_EXTERNAL",
        "mcp_adapter = bkaidev_managed",
        "run_creation = validate_workflow_implicit",
        "BKFlow Workflow Harness MCP",
        "mcp_contract_version",
        "harness_enabled",
        "只读",
        "Knowledge Router",
        "Prompt 版本",
        "模型版本",
        "clarify intent",
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
        "DRAFT",
        "sdk_xxx",
    ):
        assert required_text in spike
    for forbidden_text in ("第二个 Agent", "自主 MCP", "直接插件执行", "发布", "真实执行"):
        assert forbidden_text in spike
    assert "SP-01 | PASS" not in spike


def test_spike_loop_selects_only_governed_capability_cards_before_exact_schema_reads():
    """Prompt ordering forbids model-invented code identities between search and exact Schema lookup."""
    spike = SPIKE_FILE.read_text(encoding="utf-8")
    search_step = "-> search capabilities"
    select_step = "-> select candidates"
    schema_step = "-> fetch exact schemas"

    assert search_step in spike
    assert select_step in spike
    assert schema_step in spike
    assert spike.index(search_step) < spike.index(select_step) < spike.index(schema_step)
    for required_text in (
        "受治理搜索卡片",
        "capability_ref",
        "expected_schema_hash",
        "只在服务端进行",
        "不能凭 code 自行构造",
    ):
        assert required_text in spike


@pytest.mark.parametrize("operation_id", HARNESS_OPERATIONS)
def test_harness_operation_document_name_is_prefixed_and_unique(operation_id):
    """The MCP-visible Tool name remains separate from the collision-safe APIGW operation ID."""
    assert operation_id.startswith("harness_")
    assert operation_id.removeprefix("harness_") in HARNESS_OPERATIONS.values()
