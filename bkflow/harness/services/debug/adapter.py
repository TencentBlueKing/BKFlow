"""Narrow adapter over the existing template DebugService response shapes."""

from copy import deepcopy

from django.db import transaction
from django.utils import timezone

from bkflow.harness.models import TokenLease
from bkflow.harness.services.debug.contracts import DebugAdapterSnapshot
from bkflow.harness.services.token_broker import ActiveTokenHandle
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugService, DebugStateError
from bkflow.template.models import DebugContext, DebugNodeState


class DebugContextBusy(RuntimeError):
    """The shared canvas debug context is already serving another run."""


class DebugContextOwnershipConflict(RuntimeError):
    """The shared context points at an Engine task not owned by this session."""


class DebugAdapter:
    """Translate existing DebugService facts without exposing SDK operations."""

    READINESS_FIELDS = (
        "node_id",
        "node_type",
        "execution_mode",
        "status",
        "supports_step",
        "supports_mock",
        "can_step",
        "missing_vars",
    )

    def __init__(self, *, template_id, space_id, pipeline_tree):
        self.service = DebugService(template_id=template_id, space_id=space_id, pipeline_tree=pipeline_tree)

    def prepare(self):
        """Replace idle shared-canvas residue with one clean session baseline."""
        with transaction.atomic():
            context = self.service.get_or_create_context()
            context = DebugContext.objects.select_for_update().get(pk=context.pk)
            if context.status != "idle" or context.active_task_id is not None:
                raise DebugContextBusy("Debug context is busy")
            context.global_vars = {}
            context.tree_fingerprint = {}
            context.status = "idle"
            context.active_task_id = None
            context.active_run_type = ""
            context.active_node_id = ""
            context.last_task_id = None
            context.last_run_type = ""
            context.last_run_status = "not_run"
            context.last_error_detail = {}
            context.last_inputs = {}
            context.locked_by = ""
            context.locked_at = None
            context.save(
                update_fields=[
                    "global_vars",
                    "tree_fingerprint",
                    "status",
                    "active_task_id",
                    "active_run_type",
                    "active_node_id",
                    "last_task_id",
                    "last_run_type",
                    "last_run_status",
                    "last_error_detail",
                    "last_inputs",
                    "locked_by",
                    "locked_at",
                ]
            )
            # Node rows contain both transient execution residue and per-user
            # Mock presets. Rebuilding lets the trusted template-level legacy
            # scheme be the sole baseline configuration.
            DebugNodeState.objects.filter(debug_context=context).delete()
            context_view = self.service.build_context_view()
            readiness = [
                {field: deepcopy(node.get(field)) for field in self.READINESS_FIELDS} for node in context_view["nodes"]
            ]
            return DebugAdapterSnapshot(
                debug_context_id=context.id,
                input_schema=deepcopy(self.service.input_schema()),
                node_readiness=readiness,
                tree_fingerprint=compute_tree_fingerprint(self.service.pipeline_tree),
            )

    def _owned_context(self, debug_context_id):
        """Lock the exact template context persisted on the Harness session."""
        try:
            return DebugContext.objects.select_for_update().get(
                pk=debug_context_id,
                template_id=self.service.template_id,
            )
        except DebugContext.DoesNotExist:
            raise DebugContextOwnershipConflict("Debug context is unavailable") from None

    def context_view(self, debug_context_id, *, current_task_id=None):
        """Sync and project only the Engine task explicitly owned by the session."""
        self.require_context_ownership(debug_context_id, current_task_id=current_task_id)
        view = self.service.build_context_view()
        if current_task_id is not None and not (
            view.get("active_task_id") == current_task_id
            or (view.get("active_task_id") is None and view.get("last_task_id") == current_task_id)
        ):
            raise DebugContextOwnershipConflict("Debug context changed task ownership")
        return view

    def require_context_ownership(self, debug_context_id, *, current_task_id=None):
        """Check the persisted canvas task before any read or control side effect."""
        context = self._owned_context(debug_context_id)
        if current_task_id is None:
            if context.active_task_id is not None:
                raise DebugContextOwnershipConflict("Debug context is owned by another task")
        elif not (
            context.active_task_id == current_task_id
            or (context.active_task_id is None and context.last_task_id == current_task_id)
        ):
            raise DebugContextOwnershipConflict("Debug context task does not match the session")
        return context

    def reset_impact(self):
        """Expose the existing read-only impact calculation through the adapter."""
        return self.service.reset_impact()

    def reset(self, debug_context_id, *, node_ids):
        """Reset selected results after confirming the bound context."""
        self._owned_context(debug_context_id)
        impact = self.service.reset_impact()
        return self.service.reset(node_ids=node_ids), impact

    def terminate(self, debug_context_id, *, current_task_id, node_id, operator):
        """Terminate only the Engine task currently bound to the session."""
        context = self._owned_context(debug_context_id)
        if context.active_task_id != current_task_id:
            raise DebugContextOwnershipConflict("Debug context task does not match the session")
        # A successful global terminate request deliberately leaves the shared
        # context in ``terminating`` until Engine convergence. Repeated status
        # reads must not dispatch another revoke for the same owned task.
        if node_id is None and context.status == "terminating":
            return {"status": "terminating"}
        return self.service.terminate(node_id=node_id, operator=operator)

    def set_node_mock(
        self,
        debug_context_id,
        *,
        node_id,
        enabled,
        mock_result,
        mock_outputs,
        mock_error,
    ):
        """Update one node's Mock preset after confirming the bound context."""
        self._owned_context(debug_context_id)
        return self.service.node_mock(
            node_id,
            enable=enabled,
            mock_result=mock_result,
            mock_outputs=mock_outputs,
            mock_error=mock_error,
        )

    def set_context_var(self, debug_context_id, *, key, value):
        """Update one context variable after confirming the bound context."""
        self._owned_context(debug_context_id)
        return self.service.set_context_var(key, value)

    def run_step(self, request, *, operator, token_handle=None):
        """Dispatch one already-authorized step through the existing service."""
        if request.execution_mode == "real":
            # In-process DebugService does not use the canvas SDK transport
            # token. The handle is server-side authorization proof only; its
            # plaintext secret must stay unread at this adapter boundary.
            if (
                not isinstance(token_handle, ActiveTokenHandle)
                or token_handle.permission != TokenLease.Permission.MOCK
                or token_handle.resource_type != TokenLease.Resource.TEMPLATE
                or token_handle.resource_id != str(self.service.template_id)
                or token_handle.expires_at <= timezone.now()
            ):
                raise DebugStateError("real step requires a trusted token handle")
        context = self.service.sync_node_states()
        can_step, missing = self.service.compute_can_step(context, request.node_id)
        if not request.input_overrides and not can_step:
            raise DebugStateError({"detail": "dependencies missing", "missing_vars": missing})
        return self.service.step_run(
            node_id=request.node_id,
            operator=operator,
            mode=request.execution_mode,
            input_overrides=request.input_overrides or None,
            mock_result=request.mock_result,
            mock_outputs=request.mock_outputs,
            mock_error=request.mock_error,
        )

    def run_global(self, request, *, operator):
        """Force every executable activity to Mock before global dispatch."""
        context = self.service.sync_node_states()
        activity_ids = list(self.service.pipeline_tree.get("activities", {}))
        DebugNodeState.objects.filter(debug_context=context, node_id__in=activity_ids).update(execution_mode="mock")
        return self.service.global_run(inputs=request.inputs, operator=operator)
