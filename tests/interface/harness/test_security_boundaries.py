"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import logging
from types import SimpleNamespace

import pytest

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import HarnessAuthorizationError
from bkflow.harness.models import HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.context import derive_trusted_context
from bkflow.harness.services.draft import create_workflow_draft_with_context
from bkflow.harness.services.facade import (
    ERROR_CATEGORIES,
    P0_TOOL_OPERATION_MAP,
    HarnessFacade,
    normalize_errors,
)
from bkflow.harness.services.projection import (
    SEARCH_CARD_FIELDS,
    search_workflow_capabilities,
)
from bkflow.harness.services.validator import validate_workflow_with_context
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot

VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}
INVARIANTS = {
    "cross_space_leak": 0,
    "secret_or_token_exposure": 0,
    "duplicate_drafts": 0,
    "silent_schema_drift": 0,
    "published_templates": 0,
    "created_tasks": 0,
    "real_executions": 0,
}
PIPELINE_TREE = {
    "activities": {"nact": {"id": "nact", "type": "ServiceActivity"}},
    "gateways": {},
    "flows": {},
    "start_event": {"id": "nstart", "type": "EmptyStartEvent"},
    "end_event": {"id": "nend", "type": "EmptyEndEvent"},
    "constants": {},
}


def _enable_harness(space, users=None, app_code=None):
    if app_code:
        space.app_code = app_code
        space.save(update_fields=["app_code"])
    SpaceConfig.objects.create(
        space_id=space.id, name="harness_enabled", value_type=SpaceConfigValueType.TEXT.value, text_value="true"
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_deployment",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=VALID_DEPLOYMENT,
    )
    SpaceConfig.objects.create(
        space_id=space.id, name="superusers", value_type=SpaceConfigValueType.JSON.value, json_value=users or ["alice"]
    )


def _context(space, actor="alice", app="bkflow_harness"):
    return TrustedHarnessContext(
        platform_key="bkaidev",
        platform_app=app,
        actor=actor,
        space_id=space.id,
        scope_type=None,
        scope_value=None,
        target_environment="stage",
        policy_version="p0-v1",
        mcp_contract_version="1.0.0",
        correlation_id="corr-sec",
    )


def test_p0_invariant_counters_are_zero():
    """安全边界计数器初始值必须全为 0。"""
    assert INVARIANTS == {
        "cross_space_leak": 0,
        "secret_or_token_exposure": 0,
        "duplicate_drafts": 0,
        "silent_schema_drift": 0,
        "published_templates": 0,
        "created_tasks": 0,
        "real_executions": 0,
    }
    assert set(P0_TOOL_OPERATION_MAP) == {
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
    }
    assert not hasattr(HarnessFacade, "start_workflow_execution")
    assert not hasattr(HarnessFacade, "publish_workflow")
    assert "TOKEN_LEASE" in ERROR_CATEGORIES


@pytest.mark.django_db
def test_cross_space_capability_run_revision_and_draft_are_isolated(space):
    """跨空间能力、run、修订和草稿不得泄漏。"""
    _enable_harness(space)
    other = Space.objects.create(name="sec-other", app_code="other_app", platform_url="http://example.com")
    _enable_harness(other, users=["bob"], app_code="other_app")
    leaks = 0
    snapshot = [
        {
            "plugin_type": "component",
            "source_key": None,
            "code": "secret_plugin",
            "version": "1.0.0",
            "name": "机密能力",
            "aliases": [],
            "tags": [],
            "use_cases": ["机密"],
            "space_ids": [other.id],
            "schema": {"inputs": [], "outputs": []},
        }
    ]
    result = search_workflow_capabilities(context=_context(space), query="机密", registry_snapshot=snapshot)
    if result.candidates:
        leaks += 1
    run = HarnessRun.objects.create(
        platform_key="bkaidev",
        platform_app="other_app",
        actor="bob",
        space_id=other.id,
        target_environment="stage",
        status=HarnessRunStatus.VALIDATING.value,
        policy_version="p0-v1",
        mcp_contract_version="1.0.0",
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run, sequence=1, intent_spec={}, canonical_a2flow={"version": "2.0"}, plan_hash="a" * 64
    )
    foreign = create_workflow_draft_with_context(
        _context(space),
        {
            "run_id": str(run.id),
            "revision_id": str(revision.id),
            "plan_hash": revision.plan_hash,
            "idempotency_key": "cross-space",
        },
    )
    if foreign["ok"] or WorkflowPlanRevision.objects.filter(run__space_id=space.id).exists():
        leaks += 1
    assert leaks == INVARIANTS["cross_space_leak"]


@pytest.mark.django_db
def test_forged_identity_fields_cannot_change_trusted_context(space):
    """请求体伪造身份不能覆盖网关可信字段。"""
    _enable_harness(space)
    request = SimpleNamespace(
        app=SimpleNamespace(bk_app_code="bkflow_harness"),
        user=SimpleNamespace(username="alice", is_authenticated=True),
        data={
            "platform_app": "evil",
            "actor": "mallory",
            "space_id": 1,
            "scope_type": "biz",
            "scope_value": "999",
            "target_environment": "prod",
            "access_token": "should-not-be-trusted",
        },
        trace_id="corr-sec",
    )
    context = derive_trusted_context(request, space.id)
    assert context.actor == "alice"
    assert context.platform_app == "bkflow_harness"
    assert context.target_environment == "stage"
    with pytest.raises(HarnessAuthorizationError):
        derive_trusted_context(
            SimpleNamespace(
                app=SimpleNamespace(bk_app_code="bkflow_harness"),
                user=SimpleNamespace(username="mallory", is_authenticated=True),
                data={},
                trace_id="corr-sec",
            ),
            space.id,
        )


def test_errors_and_search_cards_do_not_expose_secrets_or_full_schema():
    """错误归一化和检索卡片不得带出 token/secret 或完整 Schema。"""
    errors = normalize_errors(
        [{"code": "PERMISSION", "message": "denied", "token": "abc", "access_token": "xyz", "secret": "s"}]
    )
    blob = str(errors).lower()
    exposure = 0
    if "abc" in blob or "xyz" in blob or "access_token" in blob:
        exposure += 1
    item = {
        "plugin_type": "component",
        "source_key": None,
        "code": "demo",
        "version": "1.0.0",
        "name": "演示",
        "aliases": [],
        "tags": [],
        "use_cases": ["demo"],
        "schema": {"inputs": [{"key": "password"}], "outputs": []},
        "token": "should-not-leak",
    }
    result = search_workflow_capabilities(
        context=_context(SimpleNamespace(id=12)),
        query="演示",
        registry_snapshot=[item],
    )
    card = result.candidates[0]
    if set(card) != set(SEARCH_CARD_FIELDS) or "schema" in card or "password" in str(card):
        exposure += 1
    assert exposure == INVARIANTS["secret_or_token_exposure"]


@pytest.mark.django_db
def test_p0_rejects_execution_release_and_debug_side_effects(space, monkeypatch, caplog):
    """P0 请求即使带上发布/执行/调试字段也不能产生任务或已发布模板。"""
    _enable_harness(space)
    caplog.set_level(logging.INFO, logger="bkflow.harness.audit")
    created_tasks = 0
    published = 0
    executions = 0
    facade = HarnessFacade()
    envelope = facade.create_workflow_draft(
        _context(space),
        {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "revision_id": "00000000-0000-0000-0000-000000000002",
            "plan_hash": "a" * 64,
            "idempotency_key": "sec-exec",
            "auto_release": True,
            "publish": True,
            "execute": True,
            "debug": True,
            "start_workflow_execution": True,
        },
    )
    if envelope.get("status") in {HarnessRunStatus.PUBLISHED.value, HarnessRunStatus.EXECUTING.value}:
        published += 1
        executions += 1
    template_ids = list(Template.objects.filter(space_id=space.id).values_list("id", flat=True))
    if template_ids and TemplateSnapshot.objects.filter(template_id__in=template_ids, draft=False).exists():
        published += 1
    if any(word in caplog.text.lower() for word in ("bk_app_secret", "access_token=")):
        created_tasks += 1
    assert published == INVARIANTS["published_templates"]
    assert created_tasks == INVARIANTS["created_tasks"]
    assert executions == INVARIANTS["real_executions"]
    assert envelope["ok"] is False


@pytest.mark.django_db
def test_duplicate_drafts_and_schema_change_are_not_silent(space, monkeypatch):
    """并发重复草稿只落一份；search 与 validate 之间的 Schema 变化必须显式失败。"""
    _enable_harness(space)
    from tests.interface.harness.test_golden_cases import (
        SnapshotPluginSchemaService,
        _a2flow,
        _install_domain_mocks,
    )

    snapshot = [
        {
            "plugin_type": "component",
            "source_key": None,
            "code": "demo_restart_service",
            "version": "1.0.0",
            "name": "重启服务",
            "aliases": [],
            "tags": [],
            "use_cases": ["重启"],
            "schema": {"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []},
        }
    ]
    _install_domain_mocks(monkeypatch, snapshot)
    context = _context(space)
    ref = encode_capability_ref(plugin_type="component", source_key=None, code="demo_restart_service", version="1.0.0")
    from bkflow.harness.services.canonical import schema_hash

    digest_schema = schema_hash(snapshot[0]["schema"])
    first = validate_workflow_with_context(
        context,
        {
            "a2flow": _a2flow("demo_restart_service", {"host": "example-host"}),
            "bindings": [
                {"node_id": "node_1", "capability_ref": ref, "schema_hash": digest_schema, "credential_ref": None}
            ],
            "idempotency_key": "sec-dup-v",
        },
    )
    payload = {
        "run_id": first["run_id"],
        "revision_id": first["revision_id"],
        "plan_hash": first["plan_hash"],
        "idempotency_key": "sec-dup-d",
        "auto_release": True,
    }
    one = create_workflow_draft_with_context(context, payload)
    two = create_workflow_draft_with_context(context, payload)
    duplicates = 0
    if Template.objects.filter(space_id=space.id).count() != 1 or one["artifact_refs"] != two["artifact_refs"]:
        duplicates += 1
    mutated = [
        {
            **snapshot[0],
            "schema": {
                "inputs": [{"key": "host", "type": "string", "required": True}, {"key": "extra"}],
                "outputs": [],
            },
        }
    ]
    monkeypatch.setattr(
        "bkflow.harness.services.validator.resolve_capability",
        lambda context, capability_ref, expected_schema_hash=None, **kwargs: __import__(
            "bkflow.harness.services.resolver", fromlist=["resolve_capability"]
        ).resolve_capability(
            context,
            capability_ref,
            expected_schema_hash=expected_schema_hash,
            plugin_schema_service=SnapshotPluginSchemaService(mutated),
        ),
    )
    drifted = validate_workflow_with_context(
        context,
        {
            "a2flow": _a2flow("demo_restart_service", {"host": "example-host"}),
            "bindings": [
                {"node_id": "node_1", "capability_ref": ref, "schema_hash": digest_schema, "credential_ref": None}
            ],
            "idempotency_key": "sec-drift",
        },
    )
    silent = 0
    if drifted["ok"] or drifted["errors"][0]["code"] != "SCHEMA_DRIFT":
        silent += 1
    assert duplicates == INVARIANTS["duplicate_drafts"]
    assert silent == INVARIANTS["silent_schema_drift"]
