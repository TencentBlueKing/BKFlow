"""Stable Envelope boundary for ``start_debug_session``."""

from django.core.exceptions import ValidationError
from django.db import DatabaseError

from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import DebugSession, HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.contract_versions import (
    is_harness_debug_enabled,
    require_tool_enabled,
)
from bkflow.harness.services.debug.control import control_debug_session
from bkflow.harness.services.debug.policy import (
    DebugStartRejected,
    validate_control_request,
    validate_get_request,
    validate_run_request,
    validate_start_request,
)
from bkflow.harness.services.debug.read import get_debug_session
from bkflow.harness.services.debug.run import run_debug
from bkflow.harness.services.debug.session import start_debug_session
from bkflow.harness.services.resolver import (
    CapabilityResolutionError,
    CapabilityResolver,
    ProviderInfrastructureError,
    SchemaDriftError,
)
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.template.models import Template, TemplateSnapshot


def _failure(context, rejection):
    validator = WorkflowValidator(context, resolver=object())
    return validator._input_failure(
        {},
        rejection.code,
        path=rejection.path,
        category=rejection.category,
        repairable=rejection.repairable,
        retryable=rejection.retryable,
    )


def start_debug_session_with_context(context, payload, plugin_schema_service=None, *, resolver=None):
    """Validate a closed request and return one common Harness Envelope."""
    try:
        request = validate_start_request(payload)
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        return start_debug_session(context, request, resolver=active_resolver)
    except DebugStartRejected as rejection:
        return _failure(context, rejection)
    except IdempotencyConflict:
        return _failure(
            context,
            DebugStartRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
        )
    except ProviderInfrastructureError:
        return _failure(
            context,
            DebugStartRejected("RETRYABLE_INFRA", "bindings", retryable=True),
        )
    except (CapabilityResolutionError, SchemaDriftError):
        return _failure(context, DebugStartRejected("VALIDATION_STALE", "bindings"))
    except (IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError):
        return _failure(
            context,
            DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True),
        )
    except (
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        return _failure(
            context,
            DebugStartRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False),
        )
    except Exception:
        return _failure(
            context,
            DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True),
        )


def run_debug_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    approval_verifier=None,
    token_broker=None,
    allow_real=False,
    adapter_class=None,
):
    """Validate and dispatch a closed run request behind the common Envelope."""
    try:
        request = validate_run_request(payload)
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        kwargs = {
            "resolver": active_resolver,
            "approval_verifier": approval_verifier,
            "token_broker": token_broker,
            "allow_real": allow_real,
        }
        if adapter_class is not None:
            kwargs["adapter_class"] = adapter_class
        return run_debug(context, request, **kwargs)
    except DebugStartRejected as rejection:
        return _failure(context, rejection)
    except IdempotencyConflict:
        return _failure(context, DebugStartRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False))
    except ProviderInfrastructureError:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "bindings", retryable=True))
    except (CapabilityResolutionError, SchemaDriftError):
        return _failure(context, DebugStartRejected("VALIDATION_STALE", "bindings"))
    except (IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError):
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))
    except (
        DebugSession.DoesNotExist,
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        Template.DoesNotExist,
    ):
        return _failure(
            context,
            DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False),
        )
    except Exception:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))


def get_debug_session_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    adapter_class=None,
    token_broker=None,
    artifact_writer=None,
):
    """Validate and project one owned debug session through the common Envelope."""
    try:
        require_tool_enabled(context, "get_debug_session")
        request = validate_get_request(payload)
        runtime_enabled = is_harness_debug_enabled(context.space_id)
        active_resolver = resolver or (CapabilityResolver(plugin_schema_service) if runtime_enabled else None)
        kwargs = {
            "resolver": active_resolver,
            "token_broker": token_broker,
            "artifact_writer": artifact_writer,
            "runtime_enabled": runtime_enabled,
        }
        if adapter_class is not None:
            kwargs["adapter_class"] = adapter_class
        return get_debug_session(context, request, **kwargs)
    except DebugStartRejected as rejection:
        return _failure(context, rejection)
    except HarnessContextError as error:
        return _failure(context, DebugStartRejected(error.code, "debug", repairable=False))
    except ProviderInfrastructureError:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "bindings", retryable=True))
    except (CapabilityResolutionError, SchemaDriftError):
        return _failure(context, DebugStartRejected("VALIDATION_STALE", "bindings"))
    except (DatabaseError, ValidationError):
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))
    except (
        DebugSession.DoesNotExist,
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        return _failure(
            context,
            DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False),
        )
    except Exception:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))


def control_debug_session_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    adapter_class=None,
    token_broker=None,
):
    """Validate and apply one closed debug control behind the common Envelope."""
    try:
        require_tool_enabled(context, "control_debug_session")
        request = validate_control_request(payload)
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        kwargs = {"resolver": active_resolver, "token_broker": token_broker}
        if adapter_class is not None:
            kwargs["adapter_class"] = adapter_class
        return control_debug_session(context, request, **kwargs)
    except DebugStartRejected as rejection:
        return _failure(context, rejection)
    except HarnessContextError as error:
        return _failure(context, DebugStartRejected(error.code, "debug", repairable=False))
    except IdempotencyConflict:
        return _failure(context, DebugStartRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False))
    except ProviderInfrastructureError:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "bindings", retryable=True))
    except (CapabilityResolutionError, SchemaDriftError):
        return _failure(context, DebugStartRejected("VALIDATION_STALE", "bindings"))
    except (IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError, ValidationError):
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))
    except (
        DebugSession.DoesNotExist,
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        return _failure(
            context,
            DebugStartRejected("CAPABILITY_FORBIDDEN", "session_id", category="PERMISSION", repairable=False),
        )
    except Exception:
        return _failure(context, DebugStartRejected("RETRYABLE_INFRA", "debug", retryable=True))


__all__ = [
    "control_debug_session_with_context",
    "get_debug_session_with_context",
    "run_debug_with_context",
    "start_debug_session_with_context",
    "WorkflowValidationFailure",
]
