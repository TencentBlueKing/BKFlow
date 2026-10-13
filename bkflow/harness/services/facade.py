"""Versioned public Harness operations over governed service boundaries."""

from dataclasses import asdict

from bkflow.harness.models import HarnessRun
from bkflow.harness.services.canonical import canonical_scope
from bkflow.harness.services.draft import create_workflow_draft
from bkflow.harness.services.knowledge.audit import record_denied_knowledge_retrieval
from bkflow.harness.services.knowledge.providers import KnowledgeProviderRegistry
from bkflow.harness.services.knowledge.router import KnowledgeRouter
from bkflow.harness.services.projection import CapabilityProjection
from bkflow.harness.services.resolver import (
    CapabilityResolutionError,
    CapabilityResolver,
)
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService

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
P1_ACTION_RISK = {"search_workflow_knowledge": "L0"}
P2_ACTION_RISK = {
    "start_debug_session": "L1",
    "run_debug": "L2",
    "get_debug_session": "L0",
    "control_debug_session": "L1",
}
P3_ACTION_RISK = {
    "prepare_release": "L0",
    "publish_workflow": "L2",
    "start_workflow_execution": "L2",
    "get_workflow_execution": "L0",
    # Unknown or unparsed control requests are audited conservatively. A valid
    # tagged request is refined to its action-specific L2/L3 risk by APIGW.
    "control_workflow_execution": "L3",
}
P4_ACTION_RISK = {"submit_generation_feedback": "L0"}

_PRODUCTION_KNOWLEDGE_PROVIDER_REGISTRY = None


def production_feedback_retention_policy():
    """Fail closed until an approved deployment retention policy is wired in."""
    from bkflow.harness.services.feedback.contracts import FeedbackRetentionPolicy

    return FeedbackRetentionPolicy.disabled()


class HarnessFacade:
    """Delegate public operations to the existing governed service boundaries."""

    def _service(self, context):
        return PluginSchemaService(
            space_id=context.space_id,
            username=context.actor,
            scope_type=context.scope_type,
            scope_id=context.scope_value,
        )

    def _knowledge_router(self):
        """Use one explicit, fail-closed production provider registry per process."""
        global _PRODUCTION_KNOWLEDGE_PROVIDER_REGISTRY
        if _PRODUCTION_KNOWLEDGE_PROVIDER_REGISTRY is None:
            _PRODUCTION_KNOWLEDGE_PROVIDER_REGISTRY = KnowledgeProviderRegistry()
        return KnowledgeRouter(provider_registry=_PRODUCTION_KNOWLEDGE_PROVIDER_REGISTRY)

    @staticmethod
    def _run_matches_context(context, run_id):
        """Resolve an optional run only inside the complete trusted authority scope."""
        if run_id is None:
            return True
        try:
            scope = canonical_scope(context.scope_type, context.scope_value)
            return HarnessRun.objects.filter(
                run_id=run_id,
                platform=context.platform_key,
                platform_app=context.platform_app,
                actor=context.actor,
                space_id=context.space_id,
                scope=scope,
                environment=context.target_environment,
                policy_version=context.policy_version,
                mcp_contract_version=context.mcp_contract_version,
            ).exists()
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _read_envelope(context, artifact_type, payload, errors=None, run_id=None):
        """Put governed read results into the same frozen response shape as writes."""
        errors = [HarnessFacade._read_error(error) for error in errors or []]
        return {
            "ok": not errors,
            "run_id": run_id,
            "revision_id": None,
            "plan_hash": None,
            "status": "COMPLETED" if not errors else None,
            "summary": "Harness capability lookup accepted.",
            "artifact_refs": [{"type": artifact_type, "payload": payload}],
            "errors": errors,
            "next_actions": list(dict.fromkeys(error["suggested_action"] for error in errors)),
            "correlation_id": context.correlation_id,
        }

    @staticmethod
    def _read_error(error):
        """Build a complete safe error before a read result leaves the Facade boundary."""
        error = error if isinstance(error, dict) else {}
        code = error.get("code")
        if code not in WorkflowValidationFailure._DETAILS:
            code = "RETRYABLE_INFRA"
        return WorkflowValidationFailure(
            code,
            path="request",
            repairable=error.get("repairable") is True,
            retryable=error.get("retryable") is True,
        ).as_error()

    def search_workflow_capabilities(self, context, request):
        """Search the bounded Task 5 capability projection."""
        result = CapabilityProjection(self._service(context)).search(
            request.get("query", ""), top_k=request.get("top_k", 10), plugin_source=request.get("plugin_source")
        )
        errors = [
            {"code": error.get("code"), "retryable": error.get("retryable") is True}
            for error in result.get("errors", [])
            if isinstance(error, dict)
        ]
        return self._read_envelope(context, "capability_search", result.get("capabilities", []), errors=errors)

    def get_plugin_schema(self, context, request):
        """Resolve a selected opaque reference against the fresh governed catalog."""
        try:
            capability = CapabilityResolver(self._service(context)).resolve(
                request["capability_ref"], expected_schema_hash=request["expected_schema_hash"]
            )
        except CapabilityResolutionError as error:
            retryable = error.code == "RETRYABLE_INFRA"
            return self._read_envelope(
                context, "plugin_schema", {}, errors=[{"code": error.code, "retryable": retryable}]
            )
        return self._read_envelope(
            context,
            "plugin_schema",
            {
                "capability_ref": capability.capability_ref,
                "plugin_type": capability.plugin_type,
                "resolved_version": capability.resolved_version,
                "schema_hash": capability.schema_hash,
                "risk_level": capability.risk_level,
                "inputs": capability.schema["inputs"],
                "outputs": capability.schema["outputs"],
            },
        )

    def validate_workflow(self, context, request):
        """Delegate validation/revision persistence to Task 6."""
        return WorkflowValidator(context, plugin_schema_service=self._service(context)).validate_workflow(request)

    def create_workflow_draft(self, context, request):
        """Delegate draft-only materialization to Task 7."""
        return create_workflow_draft(context, request, plugin_schema_service=self._service(context))

    def search_workflow_knowledge(self, context, request):
        """Return only advisory federated knowledge selected by the trusted Router."""
        run_id = request.get("run_id")
        empty_payload = {
            "query_fingerprint": None,
            "hits": [],
            "conflict_annotations": [],
            "artifact_refs": [],
            "warning_codes": [],
            "policy_effect": "ADVISORY",
        }
        router_request = {
            key: request[key] for key in ("query", "top_k", "run_id", "data_classification") if key in request
        }
        if not self._run_matches_context(context, run_id):
            record_denied_knowledge_retrieval(context, router_request)
            return self._read_envelope(
                context,
                "knowledge_search",
                empty_payload,
                errors=[{"code": "CAPABILITY_FORBIDDEN"}],
            )

        result = self._knowledge_router().search(context, router_request)
        payload = {
            "query_fingerprint": result.query_fingerprint,
            "hits": [asdict(hit) for hit in result.hits],
            "conflict_annotations": [
                {**asdict(annotation), "alternative_hit_refs": list(annotation.alternative_hit_refs)}
                for annotation in result.conflict_annotations
            ],
            "artifact_refs": list(result.artifact_refs),
            "warning_codes": list(result.warning_codes),
            "policy_effect": "ADVISORY",
        }
        errors = [{"code": code, "retryable": code == "RETRYABLE_INFRA"} for code in result.error_codes]
        return self._read_envelope(
            context,
            "knowledge_search",
            payload,
            errors=errors,
            run_id=run_id,
        )

    def start_debug_session(self, context, request):
        """Establish one revision-bound session through the P2 domain facade."""
        from bkflow.harness.services.debug.facade import (
            start_debug_session_with_context,
        )

        return start_debug_session_with_context(context, request, self._service(context))

    def run_debug(self, context, request):
        """Dispatch one policy-gated debug request through the P2 domain facade."""
        from bkflow.harness.services.debug.facade import run_debug_with_context

        return run_debug_with_context(context, request, self._service(context))

    def get_debug_session(self, context, request):
        """Read and converge one owned P2 debug session."""
        from bkflow.harness.services.contract_versions import is_harness_debug_enabled
        from bkflow.harness.services.debug.facade import get_debug_session_with_context

        service = self._service(context) if is_harness_debug_enabled(context.space_id) else None
        return get_debug_session_with_context(context, request, service)

    def control_debug_session(self, context, request):
        """Apply one deterministic P2 session control."""
        from bkflow.harness.services.debug.facade import (
            control_debug_session_with_context,
        )

        return control_debug_session_with_context(context, request, self._service(context))

    def prepare_release(self, context, request):
        """Prepare only through the release service; absent server policy remains deny-real."""
        from bkflow.harness.services.release.facade import prepare_release_with_context

        return prepare_release_with_context(context, request, self._service(context))

    def publish_workflow(self, context, request):
        """Publish only through the approval-bound release service."""
        from bkflow.harness.services.release.publish import (
            publish_workflow_with_context,
        )

        return publish_workflow_with_context(context, request, self._service(context))

    def start_workflow_execution(self, context, request):
        """Start only through the publication-bound durable execution Saga."""
        from bkflow.harness.services.execution.saga import (
            start_workflow_execution_with_context,
        )

        return start_workflow_execution_with_context(context, request, self._service(context))

    def get_workflow_execution(self, context, request):
        """Read and converge only through the owned execution projection."""
        from bkflow.harness.services.execution.read import (
            get_workflow_execution_with_context,
        )

        return get_workflow_execution_with_context(context, request)

    def control_workflow_execution(self, context, request):
        """Control only through the approval and idempotency service boundary."""
        from bkflow.harness.services.execution.control import (
            control_workflow_execution_with_context,
        )

        return control_workflow_execution_with_context(context, request)

    def submit_generation_feedback(self, context, request):
        """Record feedback only when deployment policy explicitly allows retention."""
        from bkflow.harness.services.feedback.facade import (
            submit_generation_feedback_with_context,
        )

        return submit_generation_feedback_with_context(
            context,
            request,
            retention_policy=production_feedback_retention_policy(),
        )
