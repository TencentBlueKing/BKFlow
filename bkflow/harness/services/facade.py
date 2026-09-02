"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import logging
import time
from typing import Any, Dict, List

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import (
    AmbiguousCapability,
    CapabilityForbidden,
    CapabilityNotFound,
    CapabilityRefError,
    HarnessUserInputError,
    SchemaDrift,
)
from bkflow.harness.services.draft import create_workflow_draft_with_context
from bkflow.harness.services.projection import catalog_may_match
from bkflow.harness.services.projection import (
    search_workflow_capabilities as search_capabilities,
)
from bkflow.harness.services.resolver import resolve_capability
from bkflow.harness.services.validator import (
    ENVELOPE_KEYS,
    _envelope,
    _error,
    validate_workflow_with_context,
)
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService

logger = logging.getLogger("bkflow.harness.audit")

HARNESS_CONTRACT_VERSION = "1.0.0"
P0_TOOL_OPERATION_MAP = {
    "search_workflow_capabilities": "harness_search_workflow_capabilities",
    "get_plugin_schema": "harness_get_plugin_schema",
    "validate_workflow": "harness_validate_workflow",
    "create_workflow_draft": "harness_create_workflow_draft",
}
P0_ACTION_RISK = {
    "search_workflow_capabilities": "L0",
    "get_plugin_schema": "L0",
    "validate_workflow": "L0",
    "create_workflow_draft": "L1",
}
ERROR_CATEGORIES = (
    "USER_INPUT",
    "CAPABILITY_NOT_FOUND",
    "AMBIGUOUS_CAPABILITY",
    "SCHEMA_DRIFT",
    "VALIDATION",
    "PERMISSION",
    "APPROVAL_REQUIRED",
    "APPROVAL_INVALID",
    "TOKEN_LEASE",
    "DEBUG_CONFLICT",
    "RUNTIME",
    "POSTCONDITION",
    "RETRYABLE_INFRA",
)
_CODE_CATEGORY = {
    "USER_INPUT": "USER_INPUT",
    "CAPABILITY_NOT_FOUND": "CAPABILITY_NOT_FOUND",
    "AMBIGUOUS_CAPABILITY": "AMBIGUOUS_CAPABILITY",
    "SCHEMA_DRIFT": "SCHEMA_DRIFT",
    "SCHEMA_VALIDATION_ERROR": "VALIDATION",
    "A2FLOW_CONVERSION_ERROR": "VALIDATION",
    "PIPELINE_VALIDATION_ERROR": "VALIDATION",
    "PLAN_HASH_MISMATCH": "VALIDATION",
    "VALIDATION_STALE": "VALIDATION",
    "PERMISSION": "PERMISSION",
    "HARNESS_DISABLED": "PERMISSION",
    "HARNESS_APP_FORBIDDEN": "PERMISSION",
    "HARNESS_USER_FORBIDDEN": "PERMISSION",
    "HARNESS_APP_UNAUTHENTICATED": "PERMISSION",
    "HARNESS_USER_UNAUTHENTICATED": "PERMISSION",
    "HARNESS_DEPLOYMENT_INVALID": "PERMISSION",
    "CAPABILITY_FORBIDDEN": "PERMISSION",
    "RETRYABLE_INFRA": "RETRYABLE_INFRA",
}


def normalize_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为 Envelope 错误补齐 category 与建议动作，并去掉敏感字段。"""
    normalized = []
    for item in errors or []:
        code = item.get("code") or "RUNTIME"
        category = _CODE_CATEGORY.get(code, item.get("category") or "RUNTIME")
        normalized.append(
            {
                "category": category,
                "code": code,
                "message": item.get("message") or code,
                "path": item.get("path") or "",
                "repairable": item.get("repairable", True),
                "retryable": item.get("retryable", False),
                "suggested_action": item.get("suggested_action") or _suggested_action(code),
            }
        )
    return normalized


def _suggested_action(code: str) -> str:
    mapping = {
        "AMBIGUOUS_CAPABILITY": "clarify_capability",
        "SCHEMA_DRIFT": "search_and_rebind",
        "VALIDATION_STALE": "validate_workflow",
        "PLAN_HASH_MISMATCH": "reload_latest_revision",
        "PERMISSION": "check_space_authorization",
        "CAPABILITY_FORBIDDEN": "check_space_authorization",
        "RETRYABLE_INFRA": "retry",
    }
    return mapping.get(code, "repair")


def _preview_plugin(plugin: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": plugin.get("name"),
        "code": plugin.get("code"),
        "aliases": plugin.get("aliases") or [],
        "tags": plugin.get("tags") or [],
        "use_cases": [plugin["description"]] if plugin.get("description") else [],
    }


def _to_snapshot(plugin: Dict[str, Any], space_id: int, schema: Dict[str, Any], version: str) -> Dict[str, Any]:
    return {
        "plugin_type": plugin.get("plugin_type"),
        "source_key": plugin.get("source_key"),
        "code": plugin.get("code"),
        "version": version,
        "name": plugin.get("name"),
        "aliases": plugin.get("aliases") or [],
        "tags": plugin.get("tags") or [],
        "use_cases": [plugin["description"]] if plugin.get("description") else [],
        "space_ids": [space_id],
        "schema": schema,
        "required_credentials": [],
    }


def _load_search_snapshots(service, plugins: List[Dict[str, Any]], space_id: int, query: str) -> List[Dict[str, Any]]:
    """先按意图分词召回，再为候选填充真实 Schema；加载失败的候选直接丢弃。"""
    snapshots = []
    for item in plugins:
        if not catalog_may_match(query, _preview_plugin(item)):
            continue
        version = item.get("version") or None
        if version in ("", "unversioned"):
            version = None
        try:
            payload = service.get_plugin_schema(
                code=item.get("code"),
                version=version,
                plugin_type=item.get("plugin_type"),
                source_key=item.get("source_key"),
            )
        except Exception:
            continue
        schema = {"inputs": payload.get("inputs") or [], "outputs": payload.get("outputs") or []}
        resolved = payload.get("resolved_version") or payload.get("version") or version or "unversioned"
        snapshots.append(_to_snapshot({**item, **payload}, space_id, schema, resolved))
    return snapshots


class HarnessFacade:
    """P0 四个控制 Tool 的唯一门面。"""

    def search_workflow_capabilities(self, context: TrustedHarnessContext, request: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        try:
            service = PluginSchemaService(
                space_id=context.space_id,
                username=context.actor,
                scope_type=context.scope_type,
                scope_id=context.scope_value,
            )
            plugins, _ = service.list_plugins(limit=200)
            result = search_capabilities(
                context=context,
                query=request["query"],
                registry_snapshot=_load_search_snapshots(service, plugins, context.space_id, request["query"]),
                top_k=request.get("top_k", 10),
            )
            envelope = _envelope(
                ok=True,
                run_id=request.get("run_id"),
                revision_id=None,
                plan_hash=None,
                status=None,
                summary="found {} capabilities".format(len(result.candidates)),
                artifact_refs=[{"type": "capability_card", "value": item} for item in result.candidates],
                errors=[],
                next_actions=result.next_actions
                or ([{"action": "get_plugin_schema"}] if result.candidates else [{"action": "revise_query"}]),
                correlation_id=context.correlation_id,
            )
        except AmbiguousCapability as exc:
            envelope = _envelope(
                ok=False,
                run_id=request.get("run_id"),
                revision_id=None,
                plan_hash=None,
                status=None,
                summary="ambiguous capabilities",
                artifact_refs=[{"type": "capability_card", "value": item} for item in exc.candidates],
                errors=[_error("AMBIGUOUS_CAPABILITY", str(exc))],
                next_actions=[{"action": "clarify_capability"}],
                correlation_id=context.correlation_id,
            )
        except HarnessUserInputError as exc:
            envelope = _envelope(
                ok=False,
                run_id=None,
                revision_id=None,
                plan_hash=None,
                status=None,
                summary="invalid search input",
                artifact_refs=[],
                errors=[_error(exc.code, exc.message)],
                next_actions=[],
                correlation_id=context.correlation_id,
            )
        return self._finish("search_workflow_capabilities", context, request, envelope, started)

    def get_plugin_schema(self, context: TrustedHarnessContext, request: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        try:
            resolved = resolve_capability(
                context,
                request["capability_ref"],
                expected_schema_hash=request.get("expected_schema_hash"),
            )
            envelope = _envelope(
                ok=True,
                run_id=request.get("run_id"),
                revision_id=None,
                plan_hash=None,
                status=None,
                summary="resolved {}".format(resolved.code),
                artifact_refs=[
                    {
                        "type": "resolved_schema",
                        "value": {
                            "capability_ref": resolved.capability_ref,
                            "plugin_type": resolved.plugin_type,
                            "code": resolved.code,
                            "source_key": resolved.source_key,
                            "resolved_version": resolved.resolved_version,
                            "schema_hash": resolved.schema_hash,
                            "schema": resolved.schema,
                            "risk_level": resolved.risk_level,
                        },
                    }
                ],
                errors=[],
                next_actions=[{"action": "validate_workflow"}],
                correlation_id=context.correlation_id,
            )
        except SchemaDrift as exc:
            envelope = self._schema_error_envelope(context, request, "SCHEMA_DRIFT", exc)
        except CapabilityRefError as exc:
            envelope = self._schema_error_envelope(context, request, "USER_INPUT", exc)
        except CapabilityForbidden as exc:
            envelope = self._schema_error_envelope(context, request, "CAPABILITY_FORBIDDEN", exc)
        except CapabilityNotFound as exc:
            envelope = self._schema_error_envelope(context, request, "CAPABILITY_NOT_FOUND", exc)
        except Exception as exc:
            envelope = self._schema_error_envelope(context, request, "RETRYABLE_INFRA", exc, retryable=True)
        return self._finish("get_plugin_schema", context, request, envelope, started)

    def validate_workflow(self, context: TrustedHarnessContext, request: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        envelope = validate_workflow_with_context(context, request)
        return self._finish("validate_workflow", context, request, envelope, started)

    def create_workflow_draft(self, context: TrustedHarnessContext, request: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        payload = dict(request)
        payload.pop("auto_release", None)
        if payload.get("expected_plan_hash") and not payload.get("plan_hash"):
            payload["plan_hash"] = payload["expected_plan_hash"]
        envelope = create_workflow_draft_with_context(context, payload)
        return self._finish("create_workflow_draft", context, request, envelope, started)

    def _schema_error_envelope(
        self,
        context: TrustedHarnessContext,
        request: Dict[str, Any],
        code: str,
        exc: Exception,
        retryable: bool = False,
    ) -> Dict[str, Any]:
        return _envelope(
            ok=False,
            run_id=request.get("run_id"),
            revision_id=None,
            plan_hash=None,
            status=None,
            summary="schema resolve failed",
            artifact_refs=[],
            errors=[_error(code, str(exc), repairable=not retryable, retryable=retryable)],
            next_actions=[{"action": "retry"}] if retryable else [{"action": "search_workflow_capabilities"}],
            correlation_id=context.correlation_id,
        )

    def _finish(
        self,
        tool_name: str,
        context: TrustedHarnessContext,
        request: Dict[str, Any],
        envelope: Dict[str, Any],
        started: float,
    ) -> Dict[str, Any]:
        envelope = {key: envelope.get(key) for key in ENVELOPE_KEYS}
        envelope["errors"] = normalize_errors(envelope.get("errors") or [])
        logger.info(
            "harness.audit",
            extra={
                "tool": tool_name,
                "operation_id": P0_TOOL_OPERATION_MAP[tool_name],
                "risk": P0_ACTION_RISK[tool_name],
                "platform_app": context.platform_app,
                "actor": context.actor,
                "space_id": context.space_id,
                "run_id": envelope.get("run_id"),
                "revision_id": envelope.get("revision_id"),
                "ok": envelope.get("ok"),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "correlation_id": context.correlation_id,
                "contract_version": HARNESS_CONTRACT_VERSION,
            },
        )
        return envelope
