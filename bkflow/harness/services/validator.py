"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import re
import uuid
from copy import deepcopy

from django.db import DatabaseError, transaction
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from pipeline.exceptions import PipelineException
from pydantic import ValidationError

from bkflow.constants import ValidateType
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import (
    HTTP_HEADER_INPUT,
    MAX_HARNESS_JSON_DEPTH,
    MAX_HARNESS_JSON_ITEMS,
    MAX_HARNESS_JSON_STRING_BYTES,
    MAX_HARNESS_JSON_STRING_CHARS,
    MAX_HARNESS_JSON_TOTAL_BYTES,
    is_bounded_non_secret_json,
    is_harness_sensitive_key,
    is_safe_harness_text,
    is_safe_idempotency_key,
)
from bkflow.harness.services.canonical import (
    canonical_json_bytes,
    canonical_scope,
    plan_hash,
    sha256_json,
)
from bkflow.harness.services.capability_ref import MAX_CAPABILITY_REF_LENGTH
from bkflow.harness.services.idempotency import (
    IdempotencyOutcome,
    IdempotencyScope,
    execute_idempotent,
)
from bkflow.harness.services.resolver import (
    CapabilityResolutionError,
    CapabilityResolver,
    ProviderInfrastructureError,
    SchemaDriftError,
)
from bkflow.harness.services.state import record_validation_outcome, transition_run
from bkflow.pipeline_converter.constants import NodeType, normalize_a2flow_version
from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowPipeline
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
    ErrorTypes,
    SubprocessDraftError,
)
from bkflow.pipeline_validate.handler import ValidatorHandler
from bkflow.space.models import Credential


class WorkflowValidationFailure(ValueError):
    """An expected, safe-to-return validation failure."""

    _DETAILS = {
        "CAPABILITY_NOT_FOUND": (
            "CAPABILITY_NOT_FOUND",
            "The selected capability is unavailable.",
            "search_workflow_capabilities",
        ),
        "AMBIGUOUS_CAPABILITY": (
            "AMBIGUOUS_CAPABILITY",
            "The selected capability needs clarification.",
            "clarify_capability",
        ),
        "CAPABILITY_SCHEMA_UNAVAILABLE": (
            "RETRYABLE_INFRA",
            "The selected capability schema is temporarily unavailable.",
            "retry_search",
        ),
        "CAPABILITY_IDENTITY_INVALID": (
            "VALIDATION",
            "The selected capability identity is invalid.",
            "search_workflow_capabilities",
        ),
        "CAPABILITY_FORBIDDEN": (
            "PERMISSION",
            "The selected capability is not permitted.",
            "search_workflow_capabilities",
        ),
        "TRUSTED_CONTEXT_STALE": ("PERMISSION", "The trusted deployment context changed.", "start_new_validation"),
        "SCHEMA_DRIFT": ("SCHEMA_DRIFT", "The selected capability schema changed.", "get_plugin_schema"),
        "SCHEMA_VALIDATION_ERROR": ("VALIDATION", "The workflow input does not match its schema.", "repair_a2flow"),
        "A2FLOW_NODE_TYPE_INVALID": (
            "VALIDATION",
            "Use an a2flow node type: Activity, SubProcess, StartEvent, EndEvent, ParallelGateway, "
            "ConditionalParallelGateway, ExclusiveGateway or ConvergeGateway. "
            "A plugin code is not a node type; bind the capability to an Activity.",
            "repair_a2flow",
        ),
        "BINDING_FIELD_REQUIRED": (
            "VALIDATION",
            "Each binding requires node_id, capability_ref, schema_hash and credential_ref. "
            "Use credential_ref: null when no credential is needed; do not remove that field.",
            "repair_a2flow",
        ),
        "BINDING_NODE_MISMATCH": (
            "VALIDATION",
            "Provide exactly one binding for every Activity node and no bindings for other node types. "
            "Each binding.node_id must match the Activity id.",
            "repair_a2flow",
        ),
        "BINDING_NODE_DUPLICATE": (
            "VALIDATION",
            "Keep exactly one binding per Activity node. Remove the duplicate binding at the indicated index.",
            "repair_a2flow",
        ),
        "A2FLOW_CONVERSION_ERROR": ("VALIDATION", "The workflow structure cannot be converted.", "repair_a2flow"),
        "FAILURE_STRATEGY_CONFLICT": (
            "VALIDATION",
            "Enable at most one of error_ignorable, auto_retry.enable and timeout_config.enable.",
            "repair_a2flow",
        ),
        "FAILURE_STRATEGY_INVALID_COMBO": (
            "VALIDATION",
            "With error_ignorable enabled, set retryable and skippable to false; "
            "with auto_retry.enable enabled, set retryable to false.",
            "repair_a2flow",
        ),
        "SUBPROCESS_DRAFT_NOT_ALLOWED": (
            "VALIDATION",
            "Select an already published subprocess template in the same space and scope; drafts cannot be referenced.",
            "repair_a2flow",
        ),
        "HOOK_REFERENCE_INVALID": (
            "VALIDATION",
            "Use only declared variable references such as ${variable} with hook=true; "
            "mixed literal interpolation is not supported.",
            "repair_a2flow",
        ),
        "PIPELINE_VALIDATION_ERROR": ("VALIDATION", "The converted workflow is not valid.", "repair_a2flow"),
        "PLAN_HASH_MISMATCH": ("VALIDATION", "The workflow plan changed.", "revalidate_workflow"),
        "VALIDATION_STALE": ("SCHEMA_DRIFT", "The accepted validation is stale.", "validate_workflow"),
        "DEBUG_CONFLICT": (
            "DEBUG_CONFLICT",
            "The managed template already has an active debug operation.",
            "get_debug_session",
        ),
        "DEBUG_CONTEXT_CHANGED": (
            "DEBUG_CONFLICT",
            "The debug context page is stale or unavailable. Read get_debug_session again without node_cursor.",
            "get_debug_session",
        ),
        "APPROVAL_REQUIRED": (
            "APPROVAL",
            "Real-step debug requires an enabled policy and a verifiable approval receipt.",
            "request_debug_approval",
        ),
        "APPROVAL_INVALID": (
            "APPROVAL",
            "The real-step approval receipt is invalid or unavailable.",
            "request_debug_approval",
        ),
        "TOKEN_LEASE": (
            "PERMISSION",
            "Real-step debug requires a live server-side MOCK Token lease.",
            "start_debug_session",
        ),
        "DEBUG_SESSION": (
            "DEBUG_CONFLICT",
            "The debug session is inactive, stale, or incompatible with this request.",
            "start_debug_session",
        ),
        "DEBUG_DEPENDENCY": (
            "VALIDATION",
            "The selected node has unresolved debug dependencies.",
            "run_dependency_node",
        ),
        "DEBUG_EXECUTION_FAILED": (
            "DEBUG_RUNTIME",
            "The debug operation failed before producing a stable result.",
            "get_debug_session",
        ),
        "RELEASE_POLICY_UNAVAILABLE": (
            "VALIDATION",
            "The trusted release policy is unavailable.",
            "prepare_release",
        ),
        "VERSION_CONFLICT": (
            "VALIDATION",
            "The requested workflow version is unavailable.",
            "publish_workflow",
        ),
        "EXECUTION_REJECTED": (
            "RUNTIME",
            "The workflow execution request was rejected.",
            "get_workflow_execution",
        ),
        "EXECUTION_FAILED": (
            "RUNTIME",
            "The workflow execution failed.",
            "get_workflow_execution",
        ),
        "POSTCONDITION_FAILED": (
            "POSTCONDITION",
            "The workflow postconditions were not satisfied.",
            "get_workflow_execution",
        ),
        "RETRYABLE_INFRA": (
            "RETRYABLE_INFRA",
            "Validation infrastructure is temporarily unavailable.",
            "retry_validation",
        ),
        "IDEMPOTENCY_KEY_REQUIRED": ("VALIDATION", "An idempotency key is required.", "retry_validation"),
        "IDEMPOTENCY_CONFLICT": (
            "USER_INPUT",
            "The idempotency key was used for a different request.",
            "start_new_validation",
        ),
        "HARNESS_ACCESS_DENIED": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_APP_UNAUTHENTICATED": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_USER_UNAUTHENTICATED": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_APP_SPACE_FORBIDDEN": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_USER_SPACE_FORBIDDEN": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_DISABLED": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_DEPLOYMENT_INVALID": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_ROUTE_SPACE_INVALID": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_SPACE_UNAVAILABLE": ("PERMISSION", "Harness access denied.", "contact_space_administrator"),
        "HARNESS_TOOL_UNAVAILABLE": (
            "PERMISSION",
            "The Harness tool is unavailable for this connection.",
            "negotiate_harness_contract",
        ),
    }

    def __init__(self, code, path=None, category=None, repairable=True, retryable=False):
        self.code = code
        self.path = path
        default_category, self.message, self.suggested_action = self._DETAILS.get(
            code, ("VALIDATION", "The workflow validation request is invalid.", "repair_a2flow")
        )
        self.category = category or default_category
        self.repairable = repairable
        self.retryable = retryable
        super().__init__(code)

    def as_error(self):
        """Return an action-oriented error without copying client values or secrets."""
        return {
            "category": self.category,
            "code": self.code,
            "path": self.path,
            "repairable": self.repairable,
            "retryable": self.retryable,
            "message": self.message,
            "suggested_action": self.suggested_action,
        }


class RetryableInfrastructureError(RuntimeError):
    """Cause idempotency to become retryable without persisting a semantic report."""


def p0_policy_dto(policy_version):
    """Return the sole versioned, server-owned P0 execution policy."""
    return {
        "execution_policy": {"version": WorkflowValidator.POLICY_DTO_VERSION, "mode": "draft_only"},
        "risk_policy": {"version": policy_version},
        "retry_policy": {"max_attempts": 0},
        "timeout_policy": {"mode": "none"},
        "compensation_policy": {"mode": "none"},
        "postconditions": [],
    }


def recompute_p0_plan_hash(revision):
    """Recompute a persisted P0 plan hash without request-only policy inputs."""
    run = revision.run
    return plan_hash(
        revision.canonical_a2flow,
        revision.capability_bindings.all(),
        space_id=run.space_id,
        scope=run.scope,
        environment=run.environment,
        credential_authorization_scope={"scope": run.scope},
        **p0_policy_dto(run.policy_version),
    )


class WorkflowValidator:
    """Validate a pinned a2flow candidate into an immutable Harness revision."""

    VERSION = "harness-validator-p0-v1"
    TOOL_NAME = "validate_workflow"
    POLICY_DTO_VERSION = "harness-p0-policy-v1"
    _CREDENTIAL_REF = re.compile(r"^credential://id/([1-9][0-9]{0,18})$")
    _TEMPLATE_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]{0,127})\}")
    _MAX_JSON_DEPTH = MAX_HARNESS_JSON_DEPTH
    _MAX_JSON_ITEMS = MAX_HARNESS_JSON_ITEMS
    _MAX_JSON_STRING_CHARS = MAX_HARNESS_JSON_STRING_CHARS
    _MAX_JSON_STRING_BYTES = MAX_HARNESS_JSON_STRING_BYTES
    _MAX_JSON_TOTAL_BYTES = MAX_HARNESS_JSON_TOTAL_BYTES
    # Test-only coordination point for TransactionTestCase.  It is intentionally
    # unset in every production construction and is not part of the public API.
    test_pre_run_lock_hook = None
    test_run_lock_hook = None

    def __init__(
        self, context, plugin_schema_service=None, resolver=None, converter_class=None, pipeline_validator=None
    ):
        """Build a validator from pre-authorized server context and fresh registry access."""
        self.context = context
        self.resolver = resolver or CapabilityResolver(plugin_schema_service)
        self.converter_class = converter_class or A2FlowV2Converter
        self.pipeline_validator = pipeline_validator or self._validate_pipeline_tree

    def validate_workflow(self, request):
        """Return a stable Envelope for a new or repaired P0 workflow plan."""
        request = deepcopy(request)
        idempotency_key = request.get("idempotency_key")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            return self._input_failure(request, "IDEMPOTENCY_KEY_REQUIRED", path="idempotency_key")
        if not is_safe_idempotency_key(idempotency_key):
            return self._input_failure(request, "SCHEMA_VALIDATION_ERROR", path="idempotency_key")

        try:
            run = self._trusted_run(request.get("run_id"))
        except WorkflowValidationFailure as error:
            return self._input_failure(
                request, error.code, path=error.path, category=error.category, repairable=error.repairable
            )
        except DatabaseError:
            return self._input_failure(request, "RETRYABLE_INFRA", path="run_id", repairable=True, retryable=True)
        try:
            # These checks are deliberately structural only.  They close the
            # durable JSON boundary without moving Pydantic semantic parsing
            # ahead of the required fresh capability resolution.
            self._safe_intent(request.get("intent_spec", {}))
            self._safe_client_context(request.get("client_context", {}))
            self._reject_sensitive_json(request.get("a2flow"), "a2flow")
            request["bindings"] = self._closed_bindings(request.get("bindings"))
        except WorkflowValidationFailure as error:
            return self._input_failure(
                request, error.code, path=error.path, category=error.category, repairable=error.repairable
            )
        scope = self._idempotency_scope(run, idempotency_key)
        request_hash = sha256_json(
            {"request": self._idempotency_payload(request), "trusted_context": self._trusted_context_fingerprint()}
        )

        try:
            result = execute_idempotent(
                scope,
                request_hash,
                lambda: self._validate_once(request, existing_run=run),
            )
        except IdempotencyConflict:
            try:
                error = self._idempotency_conflict(scope)
            except DatabaseError:
                return self._input_failure(
                    request, "RETRYABLE_INFRA", path="idempotency", repairable=True, retryable=True
                )
            return self._input_failure(
                request, error.code, path=error.path, category=error.category, repairable=error.repairable
            )
        except (IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError):
            return self._input_failure(
                request,
                "RETRYABLE_INFRA",
                path="idempotency",
                repairable=True,
                retryable=True,
            )
        except WorkflowValidationFailure as error:
            return self._input_failure(
                request,
                error.code,
                path=error.path,
                category=error.category,
                repairable=error.repairable,
                retryable=error.retryable,
            )
        except RetryableInfrastructureError:
            return self._input_failure(
                request,
                "RETRYABLE_INFRA",
                path="validation",
                repairable=True,
                retryable=True,
            )
        return result.response_snapshot

    def _validate_once(self, request, existing_run):
        """Run ordered validation checks and persist either a report or a revision/report pair."""
        safe_intent = self._safe_intent(request.get("intent_spec", {}))
        safe_client_context = self._safe_client_context(request.get("client_context", {}))
        if existing_run is None:
            run = self._create_run(safe_client_context)
        else:
            # This lock intentionally spans state transition, resolve, conversion,
            # outcome and report/revision persistence for one run.
            if self.test_pre_run_lock_hook is not None:
                self.test_pre_run_lock_hook(existing_run)
            run = HarnessRun.objects.select_for_update().get(pk=existing_run.pk)
            if self.test_run_lock_hook is not None:
                self.test_run_lock_hook(run)
        try:
            self._ensure_validating(run)
            resolved_bindings, canonical_a2flow = self._resolve_and_validate(request)
            conversion = self._convert(canonical_a2flow, resolved_bindings)
            self.pipeline_validator(conversion.pipeline_tree)
            calculated_plan_hash = self._plan_hash(canonical_a2flow, resolved_bindings)
            expected_plan_hash = request.get("expected_plan_hash")
            if expected_plan_hash is not None and expected_plan_hash != calculated_plan_hash:
                raise WorkflowValidationFailure("PLAN_HASH_MISMATCH", path="expected_plan_hash")
        except WorkflowValidationFailure as error:
            return self._persist_failure(run, error)
        except ProviderInfrastructureError as error:
            raise RetryableInfrastructureError() from error
        except (CapabilityResolutionError, SchemaDriftError) as error:
            return self._persist_failure(run, self._resolution_failure(error))
        except (A2FlowValidationError, A2FlowConvertError, ValidationError) as error:
            return self._persist_failure(run, self._conversion_failure(error))
        except PipelineException:
            return self._persist_failure(
                run, WorkflowValidationFailure("PIPELINE_VALIDATION_ERROR", path="pipeline_tree")
            )
        except Exception as error:
            raise RetryableInfrastructureError() from error

        with transaction.atomic():
            locked_run = HarnessRun.objects.select_for_update().get(pk=run.pk)
            parent = locked_run.revisions.order_by("-sequence").first()
            revision = WorkflowPlanRevision.objects.create(
                run=locked_run,
                sequence=(parent.sequence + 1) if parent else 1,
                parent_revision=parent,
                intent_spec=safe_intent,
                canonical_a2flow=canonical_a2flow,
                plan_hash=calculated_plan_hash,
            )
            CapabilityBinding.objects.bulk_create(
                [
                    CapabilityBinding(
                        revision=revision,
                        node_id=binding["node_id"],
                        capability_ref=binding["capability_ref"],
                        resolved_version=binding["resolved_version"],
                        schema_hash=binding["schema_hash"],
                        conversion_fingerprint=binding["conversion_fingerprint"],
                        credential_ref=binding["credential_ref"],
                        risk=binding["risk"],
                    )
                    for binding in resolved_bindings
                ]
            )
            pipeline_tree_hash = sha256_json(conversion.pipeline_tree)
            report = ValidationReport.objects.create(
                run=locked_run,
                revision=revision,
                checkpoint="VALIDATE",
                validator_version=self.VERSION,
                result={
                    "valid": True,
                    "converter_fingerprint": conversion.converter_fingerprint,
                    "pipeline_tree_hash": pipeline_tree_hash,
                    "source_map": conversion.source_map,
                    "capability_conversion_fingerprints": {
                        item["node_id"]: item["conversion_fingerprint"] for item in resolved_bindings
                    },
                },
                risk_manifest={"capability_risks": {item["node_id"]: item["risk"] for item in resolved_bindings}},
                errors=[],
                warnings=[],
                correlation_id=self.context.correlation_id,
            )
            record_validation_outcome(locked_run, valid=True)
            response = self._envelope(
                ok=True,
                run=locked_run,
                revision=revision,
                plan_hash_value=calculated_plan_hash,
                status="VALIDATING",
                artifact_refs=[self._evidence_ref(report, conversion.converter_fingerprint, pipeline_tree_hash)],
            )
            return IdempotencyOutcome(response_snapshot=response, run=locked_run, resource_reference=str(revision.id))

    def _resolve_and_validate(self, request):
        """Resolve every binding, then apply exact binding and Schema checks in request order."""
        activity_ids, bindings = self._structural_bindings(request)
        resolved = []
        for binding in bindings:
            node_id = binding["node_id"]
            capability_ref = binding.get("capability_ref")
            expected_schema_hash = binding.get("schema_hash")
            try:
                capability = self.resolver.resolve(capability_ref)
            except ProviderInfrastructureError:
                raise
            except (CapabilityResolutionError, SchemaDriftError) as error:
                raise self._resolution_failure(error, path="bindings.{}.capability_ref".format(node_id)) from error
            resolved.append(
                {
                    "node_id": node_id,
                    "capability_ref": capability.capability_ref,
                    "resolved_version": capability.resolved_version,
                    "schema_hash": capability.schema_hash,
                    "expected_schema_hash": expected_schema_hash,
                    "credential_ref": binding.get("credential_ref"),
                    "risk": capability.risk_level,
                    "schema": capability.schema,
                    "capability": capability,
                    "conversion_fingerprint": capability.conversion_fingerprint,
                }
            )

        # Resolve authorized capabilities first, but diagnose invalid node types before
        # the derived Activity/binding set mismatch can send the Agent down a false repair path.
        valid_types = {
            NodeType.ACTIVITY,
            NodeType.SUBPROCESS,
            NodeType.START_EVENT,
            NodeType.END_EVENT,
            NodeType.PARALLEL_GATEWAY,
            NodeType.CONDITIONAL_PARALLEL_GATEWAY,
            NodeType.EXCLUSIVE_GATEWAY,
            NodeType.CONVERGE_GATEWAY,
        }
        for index, node in enumerate(request["a2flow"]["nodes"]):
            node_type = node.get("type", NodeType.ACTIVITY)
            if not isinstance(node_type, str) or node_type not in valid_types:
                raise WorkflowValidationFailure("A2FLOW_NODE_TYPE_INVALID", path="a2flow.nodes.{}.type".format(index))
        expected_nodes = set(activity_ids)
        binding_node_ids = [binding["node_id"] for binding in resolved]
        seen_binding_nodes = set(binding_node_ids)
        if len(activity_ids) != len(expected_nodes):
            duplicate_node_id = next(node_id for node_id in activity_ids if activity_ids.count(node_id) > 1)
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="nodes.{}.id".format(duplicate_node_id))
        if len(binding_node_ids) != len(seen_binding_nodes):
            duplicate_index = next(
                index for index, node_id in enumerate(binding_node_ids) if node_id in binding_node_ids[:index]
            )
            raise WorkflowValidationFailure(
                "BINDING_NODE_DUPLICATE", path="bindings.{}.node_id".format(duplicate_index)
            )
        actual_nodes = set(seen_binding_nodes)
        if expected_nodes != actual_nodes:
            node_id = sorted((expected_nodes - actual_nodes) or (actual_nodes - expected_nodes))[0]
            raise WorkflowValidationFailure("BINDING_NODE_MISMATCH", path="bindings.{}".format(node_id))
        canonical_a2flow = self._canonical_a2flow(request["a2flow"])
        canonical_nodes = {node["id"]: node for node in canonical_a2flow["nodes"]}
        for node in canonical_nodes.values():
            if HTTP_HEADER_INPUT in node.get("data", {}) and node["type"] != NodeType.ACTIVITY:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="a2flow.<field>")
        variable_keys = {item["key"] for item in canonical_a2flow.get("variables", [])}
        for binding in resolved:
            node = canonical_nodes[binding["node_id"]]
            capability = binding["capability"]
            if binding["expected_schema_hash"] != binding["schema_hash"]:
                raise WorkflowValidationFailure(
                    "SCHEMA_DRIFT", path="bindings.{}.schema_hash".format(binding["node_id"])
                )
            if node.get("code") is not None and node["code"] != capability.code:
                raise WorkflowValidationFailure("SCHEMA_DRIFT", path="nodes.{}.code".format(binding["node_id"]))
            if node.get("plugin_type") is not None and node["plugin_type"] != capability.plugin_type:
                raise WorkflowValidationFailure("SCHEMA_DRIFT", path="nodes.{}.plugin_type".format(binding["node_id"]))
            # opaque capability_ref 不要求模型解码；身份只取自重新授权后的精确 binding。
            node["code"] = capability.code
            node["plugin_type"] = capability.plugin_type
            binding["credential_ref"] = self._credential_ref(binding["credential_ref"], binding["node_id"])
            if HTTP_HEADER_INPUT in node.get("data", {}) and (
                capability.plugin_type != "component" or capability.code != "bk_http_request"
            ):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="a2flow.<field>")
            self._validate_node_inputs(binding["node_id"], node.get("data", {}), binding["schema"], variable_keys)
            binding.pop("schema")
        return resolved, canonical_a2flow

    def _structural_bindings(self, request):
        """Enumerate bounded wire IDs before canonical semantic parsing."""
        a2flow = request.get("a2flow")
        if not isinstance(a2flow, dict) or not isinstance(a2flow.get("nodes"), list):
            raise WorkflowValidationFailure("A2FLOW_CONVERSION_ERROR", path="a2flow")
        bindings = request.get("bindings")
        if not isinstance(bindings, list):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings")
        activity_ids = []
        for node in a2flow["nodes"]:
            if not isinstance(node, dict):
                raise WorkflowValidationFailure("A2FLOW_CONVERSION_ERROR", path="a2flow.nodes.<index>")
            if node.get("type", NodeType.ACTIVITY) == NodeType.ACTIVITY:
                node_id = node.get("id")
                if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
                    raise WorkflowValidationFailure("A2FLOW_CONVERSION_ERROR", path="a2flow.nodes.<index>.id")
                activity_ids.append(node_id)
        for binding in bindings:
            if not isinstance(binding, dict):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>")
            node_id = binding.get("node_id")
            if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>.node_id")
            capability_ref = binding.get("capability_ref")
            schema_value = binding.get("schema_hash")
            if (
                not isinstance(capability_ref, str)
                or not capability_ref
                or len(capability_ref) > MAX_CAPABILITY_REF_LENGTH
            ):
                raise WorkflowValidationFailure(
                    "SCHEMA_VALIDATION_ERROR", path="bindings.{}.capability_ref".format(node_id)
                )
            if not isinstance(schema_value, str) or not re.match(r"^[a-f0-9]{64}$", schema_value):
                raise WorkflowValidationFailure(
                    "SCHEMA_VALIDATION_ERROR", path="bindings.{}.schema_hash".format(node_id)
                )
        return activity_ids, bindings

    def _closed_bindings(self, bindings):
        """Close the untrusted binding wire DTO before it can affect hash or registry work."""
        if not isinstance(bindings, list) or len(bindings) > self._MAX_JSON_ITEMS:
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings")
        result = []
        required = {"node_id", "capability_ref", "schema_hash", "credential_ref"}
        for index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>")
            missing = required - set(binding)
            if missing:
                raise WorkflowValidationFailure(
                    "BINDING_FIELD_REQUIRED", path="bindings.{}.{}".format(index, sorted(missing)[0])
                )
            if set(binding) != required:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>")
            node_id = binding["node_id"]
            capability_ref = binding["capability_ref"]
            schema_value = binding["schema_hash"]
            credential_ref = binding["credential_ref"]
            if not isinstance(node_id, str) or not node_id or len(node_id) > 128:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>.node_id")
            if (
                not isinstance(capability_ref, str)
                or not capability_ref
                or len(capability_ref) > MAX_CAPABILITY_REF_LENGTH
            ):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>.capability_ref")
            if not isinstance(schema_value, str) or not re.match(r"^[a-f0-9]{64}$", schema_value):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>.schema_hash")
            if credential_ref is not None and (
                not isinstance(credential_ref, str) or not self._CREDENTIAL_REF.match(credential_ref)
            ):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings.<index>.credential_ref")
            result.append(
                {
                    "node_id": node_id,
                    "capability_ref": capability_ref,
                    "schema_hash": schema_value,
                    "credential_ref": credential_ref,
                }
            )
        if len(canonical_json_bytes(result)) > self._MAX_JSON_TOTAL_BYTES:
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="bindings")
        return result

    def _validate_node_inputs(self, node_id, inputs, schema, variable_keys):
        """Validate complete resolved JSON Schema, preserving valid a2flow wrappers."""
        if not isinstance(inputs, dict):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="nodes.{}.inputs".format(node_id))
        definitions = {item.get("key"): item for item in schema.get("inputs", []) if item.get("key")}
        for key in inputs:
            if key not in definitions:
                raise WorkflowValidationFailure(
                    "SCHEMA_VALIDATION_ERROR", path="nodes.{}.inputs.{}".format(node_id, key)
                )
        for key, definition in definitions.items():
            if definition.get("required") and key not in inputs:
                raise WorkflowValidationFailure(
                    "SCHEMA_VALIDATION_ERROR", path="nodes.{}.inputs.{}".format(node_id, key)
                )
            if key in inputs:
                self._validate_input_value(node_id, key, inputs[key], definition, variable_keys)

    def _validate_input_value(self, node_id, key, value, definition, variable_keys):
        """Validate a scalar or the closed `{hook, need_render, value}` wrapper."""
        path = "nodes.{}.inputs.{}".format(node_id, key)
        candidate = value
        if isinstance(value, dict) and ("hook" in value or "need_render" in value):
            if (
                set(value) not in ({"hook", "value"}, {"hook", "need_render", "value"})
                or not isinstance(value["hook"], bool)
                or ("need_render" in value and not isinstance(value["need_render"], bool))
            ):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
            if value["hook"]:
                if isinstance(value["value"], str) and "${" in value["value"]:
                    references = self._TEMPLATE_REF.findall(value["value"])
                    if not references or "".join("${{{}}}".format(item) for item in references) != value["value"]:
                        raise WorkflowValidationFailure("HOOK_REFERENCE_INVALID", path="{}.value".format(path))
                    if any("${{{}}}".format(item) not in variable_keys for item in references):
                        raise WorkflowValidationFailure("HOOK_REFERENCE_INVALID", path="{}.value".format(path))
                return
            candidate = value["value"]
        schema = self._field_json_schema(definition)
        try:
            validate_json_schema(candidate, schema)
        except JsonSchemaValidationError as error:
            suffix = ".".join(str(part) for part in error.absolute_path)
            raise WorkflowValidationFailure(
                "SCHEMA_VALIDATION_ERROR", path="{}.{}".format(path, suffix) if suffix else path
            )

    @staticmethod
    def _field_json_schema(definition):
        """Normalize Task 5 field definitions without dropping JSON-Schema constraints."""
        schema = deepcopy(definition.get("schema") or {})
        if not schema:
            schema_type = definition.get("type")
            aliases = {"str": "string", "int": "integer", "bool": "boolean", "list": "array"}
            if schema_type not in (None, "", "any"):
                schema["type"] = aliases.get(schema_type, schema_type)
        schema_keywords = (
            "enum",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "items",
            "properties",
            "additionalProperties",
            "allOf",
            "anyOf",
            "oneOf",
            "not",
            "dependencies",
        )
        for key in schema_keywords:
            if key in definition and key not in schema:
                schema[key] = deepcopy(definition[key])
        return schema

    def _canonical_a2flow(self, a2flow):
        """Persist the normalized closed Pydantic a2flow DTO, never raw wire JSON."""
        self._reject_sensitive_json(a2flow, "a2flow")
        pipeline = A2FlowPipeline(**deepcopy(a2flow))
        pipeline.version = normalize_a2flow_version(pipeline.version)
        if pipeline.version != "2.0":
            raise WorkflowValidationFailure("A2FLOW_CONVERSION_ERROR", path="a2flow.version")
        canonical = pipeline.dict(exclude_none=True)
        for node in canonical["nodes"]:
            for key, value in node.get("data", {}).items():
                if isinstance(value, dict) and set(value) == {"hook", "value"}:
                    node["data"][key] = {"hook": value["hook"], "need_render": True, "value": value["value"]}
        return canonical

    def _convert(self, canonical_a2flow, bindings):
        """Call the metadata-aware converter exactly once for an accepted candidate."""
        converter = self.converter_class(
            canonical_a2flow,
            space_id=self.context.space_id,
            username=self.context.actor,
            scope_type=self.context.scope_type,
            scope_value=self.context.scope_value,
            governed_plugins={item["node_id"]: item["capability"] for item in bindings},
        )
        return converter.convert_with_metadata()

    @staticmethod
    def _validate_pipeline_tree(pipeline_tree):
        """Run the existing template-level pipeline validators."""
        ValidatorHandler.validate(pipeline_tree, validate_type=ValidateType.TEMPLATE)

    def _plan_hash(self, canonical_a2flow, bindings):
        """Use the Task 3 contract and trusted context for every durable plan hash."""
        return plan_hash(
            canonical_a2flow,
            bindings,
            space_id=self.context.space_id,
            scope=self._scope(),
            environment=self.context.target_environment,
            credential_authorization_scope={"scope": self._scope()},
            **self._policy_dto(),
        )

    def _create_run(self, safe_client_context):
        """Create the Spike-approved implicit run using no caller-supplied authority values."""
        return HarnessRun.objects.create(
            platform=self.context.platform_key,
            platform_app=self.context.platform_app,
            actor=self.context.actor,
            space_id=self.context.space_id,
            scope=self._scope(),
            environment=self.context.target_environment,
            status="INTENT_CAPTURED",
            policy_version=self.context.policy_version,
            mcp_contract_version=self.context.mcp_contract_version,
            client_context=safe_client_context,
        )

    def _trusted_run(self, run_id):
        """Resolve a run only when every immutable authority fact still matches."""
        if run_id is None:
            return None
        if not isinstance(run_id, str) or len(run_id) != 36:
            raise WorkflowValidationFailure(
                "CAPABILITY_FORBIDDEN", path="run_id", category="PERMISSION", repairable=False
            )
        try:
            uuid.UUID(run_id)
        except (ValueError, AttributeError, TypeError):
            raise WorkflowValidationFailure(
                "CAPABILITY_FORBIDDEN", path="run_id", category="PERMISSION", repairable=False
            )
        try:
            run = HarnessRun.objects.get(run_id=run_id)
        except (HarnessRun.DoesNotExist, ValueError):
            raise WorkflowValidationFailure(
                "CAPABILITY_FORBIDDEN", path="run_id", category="PERMISSION", repairable=False
            )
        expected = self._trusted_context_fingerprint()
        actual = {
            "platform_key": run.platform,
            "platform_app": run.platform_app,
            "actor": run.actor,
            "space_id": run.space_id,
            "scope": run.scope,
            "environment": run.environment,
            "policy_version": run.policy_version,
            "mcp_contract_version": run.mcp_contract_version,
        }
        if actual != expected:
            raise WorkflowValidationFailure(
                "TRUSTED_CONTEXT_STALE", path="run_id", category="PERMISSION", repairable=False
            )
        return run

    def _ensure_validating(self, run):
        """Move only legal implicit-run states into validation without draft completion."""
        if run.status == "INTENT_CAPTURED":
            transition_run(run, "PLANNING")
            transition_run(run, "VALIDATING")
        elif run.status in ("NEEDS_REPAIR", "DRAFT_READY"):
            transition_run(run, "VALIDATING")
        elif run.status != "VALIDATING":
            raise WorkflowValidationFailure("PLAN_HASH_MISMATCH", path="run_id", repairable=False)

    def _persist_failure(self, run, error):
        """Persist a run-level failure report and a completed replay snapshot without a revision."""
        with transaction.atomic():
            locked_run = HarnessRun.objects.select_for_update().get(pk=run.pk)
            report = ValidationReport.objects.create(
                run=locked_run,
                revision=None,
                checkpoint="VALIDATE",
                validator_version=self.VERSION,
                result={"valid": False},
                risk_manifest={},
                errors=[error.as_error()],
                warnings=[],
                correlation_id=self.context.correlation_id,
            )
            if locked_run.status == "VALIDATING":
                record_validation_outcome(locked_run, valid=False)
                locked_run.refresh_from_db(fields=["status"])
            return IdempotencyOutcome(
                response_snapshot=self._envelope(
                    ok=False,
                    run=locked_run,
                    revision=None,
                    plan_hash_value=None,
                    status=locked_run.status,
                    errors=[error.as_error()],
                    artifact_refs=[{"report_id": report.id, "validator_version": self.VERSION}],
                ),
                run=locked_run,
            )

    def _resolution_failure(self, error, path="bindings"):
        """Map resolver-only safe codes into the public validation taxonomy."""
        code = error.code
        if code == "SCHEMA_DRIFT":
            category = "SCHEMA_DRIFT"
        elif code == "CAPABILITY_FORBIDDEN":
            category = "PERMISSION"
        else:
            category = "CAPABILITY_NOT_FOUND"
        return WorkflowValidationFailure(code, path=path, category=category, repairable=code != "CAPABILITY_FORBIDDEN")

    @staticmethod
    def _conversion_failure(error):
        """Keep safe converter node/field coordinates without surfacing raw values."""
        errors = getattr(error, "errors", None)
        item = errors[0] if isinstance(errors, list) and errors else error
        node_id = getattr(item, "node_id", None)
        field = getattr(item, "field", None)
        if node_id:
            path = "nodes.{}{}".format(node_id, ".{}".format(field) if field else "")
        elif field:
            path = "a2flow.{}".format(field)
        else:
            path = "a2flow"
        if isinstance(item, SubprocessDraftError):
            code = "SUBPROCESS_DRAFT_NOT_ALLOWED"
        elif getattr(item, "error_type", None) in (
            ErrorTypes.FAILURE_STRATEGY_CONFLICT,
            ErrorTypes.FAILURE_STRATEGY_INVALID_COMBO,
        ):
            code = item.error_type
        else:
            code = "A2FLOW_CONVERSION_ERROR"
        return WorkflowValidationFailure(code, path=path)

    def _idempotency_scope(self, run, idempotency_key):
        """Use pre-run scope for the first write and durable run scope thereafter."""
        if run is not None:
            return IdempotencyScope.for_run(
                self.context.platform_app,
                self.context.actor,
                self.context.space_id,
                self.TOOL_NAME,
                run,
                idempotency_key,
            )
        return IdempotencyScope(
            platform_app=self.context.platform_app,
            actor=self.context.actor,
            space_id=self.context.space_id,
            tool_name=self.TOOL_NAME,
            run_scope="pre-run",
            idempotency_key=idempotency_key,
        )

    def _input_failure(self, request, code, path, category=None, repairable=True, retryable=False):
        """Return an unpersisted error only when an idempotency domain cannot be constructed."""
        return self._envelope(
            ok=False,
            run=None,
            revision=None,
            plan_hash_value=None,
            status=None,
            errors=[
                WorkflowValidationFailure(
                    code, path=path, category=category, repairable=repairable, retryable=retryable
                ).as_error()
            ],
        )

    def _idempotency_payload(self, request):
        """Exclude forged authority and transient display data from retry identity."""
        return {
            key: value
            for key, value in request.items()
            if key
            not in {
                "actor",
                "platform",
                "platform_app",
                "space_id",
                "scope",
                "environment",
                "execution_policy",
                "risk_policy",
                "retry_policy",
                "timeout_policy",
                "compensation_policy",
                "postconditions",
            }
        }

    def _scope(self):
        """Serialize trusted scope into the exact Task 3 plan-hash dimension."""
        return canonical_scope(self.context.scope_type, self.context.scope_value)

    def _trusted_context_fingerprint(self):
        """Return the complete server-derived identity used for run and replay isolation."""
        return {
            "platform_key": self.context.platform_key,
            "platform_app": self.context.platform_app,
            "actor": self.context.actor,
            "space_id": self.context.space_id,
            "scope": self._scope(),
            "environment": self.context.target_environment,
            "policy_version": self.context.policy_version,
            "mcp_contract_version": self.context.mcp_contract_version,
        }

    def _policy_dto(self):
        """Return the sole versioned P0 policy: draft-only and server-controlled."""
        return p0_policy_dto(self.context.policy_version)

    def _credential_ref(self, value, node_id):
        """Accept only bounded opaque credential references, never credential material."""
        if value is None:
            return None
        match = self._CREDENTIAL_REF.match(value) if isinstance(value, str) else None
        if not match:
            raise WorkflowValidationFailure(
                "SCHEMA_VALIDATION_ERROR", path="bindings.{}.credential_ref".format(node_id)
            )
        credential = Credential.objects.filter(id=int(match.group(1)), space_id=self.context.space_id).first()
        if not credential or not credential.can_use_in_scope(self.context.scope_type, self.context.scope_value):
            raise WorkflowValidationFailure(
                "CAPABILITY_FORBIDDEN", path="bindings.{}.credential_ref".format(node_id), repairable=False
            )
        return "credential://id/{}".format(credential.id)

    def _safe_intent(self, intent):
        """Persist a bounded JSON intent only after recursive secret rejection."""
        if not isinstance(intent, dict):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="intent_spec")
        self._reject_sensitive_json(intent, "intent_spec")
        return deepcopy(intent)

    def _reject_sensitive_json(self, value, path, depth=0, total_bytes=0):
        """Reject secret-like key aliases recursively before any durable DTO is built."""
        if depth == 0 and path == "a2flow":
            # Structural exception only; exact component identity and live Schema
            # are independently re-authorized before persisting a revision.
            if not is_bounded_non_secret_json(value, allow_public_http_headers=True):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="a2flow.<field>")
            return
        if depth > self._MAX_JSON_DEPTH:
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
        if isinstance(value, dict):
            if len(value) > self._MAX_JSON_ITEMS:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
            for key, item in value.items():
                if not isinstance(key, str) or len(key) > 128:
                    raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
                if is_harness_sensitive_key(key):
                    raise WorkflowValidationFailure(
                        "SCHEMA_VALIDATION_ERROR", path="{}.<field>".format(path.split(".")[0])
                    )
                self._reject_sensitive_json(item, "{}.<field>".format(path.split(".")[0]), depth + 1, total_bytes)
        elif isinstance(value, list):
            if len(value) > self._MAX_JSON_ITEMS:
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
            for index, item in enumerate(value):
                self._reject_sensitive_json(item, "{}.<index>".format(path.split(".")[0]), depth + 1, total_bytes)
        elif isinstance(value, str):
            if not is_safe_harness_text(
                value,
                max_chars=self._MAX_JSON_STRING_CHARS,
                max_bytes=self._MAX_JSON_STRING_BYTES,
            ):
                raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
        elif not isinstance(value, (str, int, float, bool, type(None))):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)
        if depth == 0 and not is_bounded_non_secret_json(value):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path=path)

    def _safe_client_context(self, client_context):
        """Persist only the two P0 opaque client references."""
        if not isinstance(client_context, dict):
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="client_context")
        if set(client_context) - {"conversation_ref", "agent_release"}:
            raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="client_context")
        self._reject_sensitive_json(client_context, "client_context")
        result = {}
        for key in ("conversation_ref", "agent_release"):
            if key in client_context:
                value = client_context[key]
                if not isinstance(value, str) or not value or len(value) > 255:
                    raise WorkflowValidationFailure("SCHEMA_VALIDATION_ERROR", path="client_context.{}".format(key))
                result[key] = value
        return result

    @staticmethod
    def _evidence_ref(report, converter_fingerprint, pipeline_tree_hash):
        """Create the compact metadata-only evidence reference used by later P0 steps."""
        return {
            "validator_version": WorkflowValidator.VERSION,
            "converter_fingerprint": converter_fingerprint,
            "pipeline_tree_hash": pipeline_tree_hash,
            "report_id": report.id,
        }

    def _envelope(self, ok, run, revision, plan_hash_value, status, errors=None, artifact_refs=None):
        """Return the stable P0 response shape before APIGW transport adapters exist."""
        return {
            "ok": ok,
            "run_id": str(run.run_id) if run else None,
            "revision_id": str(revision.id) if revision else None,
            "plan_hash": plan_hash_value,
            "status": status,
            "summary": (
                "Workflow draft created; stop the draft-only workflow."
                if ok and status == "DRAFT_READY"
                else "Workflow validation accepted."
                if ok
                else "Workflow validation requires repair."
            ),
            "artifact_refs": artifact_refs or [],
            "errors": errors or [],
            "next_actions": (
                (["create_workflow_draft"] if status == "VALIDATING" else [])
                if ok
                else list(dict.fromkeys(error["suggested_action"] for error in (errors or [])))
            ),
            "correlation_id": self.context.correlation_id,
        }

    def _idempotency_conflict(self, scope):
        """Separate a user payload collision from a completed stale pre-run context."""
        from bkflow.harness.models import HarnessIdempotencyRecord

        record = HarnessIdempotencyRecord.objects.select_related("run").filter(**scope.lookup()).first()
        if record and scope.matches(record) and record.run and not self._run_matches_context(record.run):
            return WorkflowValidationFailure("TRUSTED_CONTEXT_STALE", path="trusted_context", repairable=False)
        return WorkflowValidationFailure("IDEMPOTENCY_CONFLICT", path="idempotency_key", repairable=False)

    def _run_matches_context(self, run):
        return {
            "platform_key": run.platform,
            "platform_app": run.platform_app,
            "actor": run.actor,
            "space_id": run.space_id,
            "scope": run.scope,
            "environment": run.environment,
            "policy_version": run.policy_version,
            "mcp_contract_version": run.mcp_contract_version,
        } == self._trusted_context_fingerprint()


def validate_workflow(context, request, plugin_schema_service=None, **kwargs):
    """Validate one request through the P0 service without accepting client authority fields."""
    return WorkflowValidator(context, plugin_schema_service=plugin_schema_service, **kwargs).validate_workflow(request)
