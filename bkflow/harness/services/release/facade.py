"""Stable Harness Envelope boundary for release preparation."""

from django.core.exceptions import ValidationError
from django.db import DatabaseError

from bkflow.harness.contracts import HarnessContextError
from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.contract_versions import require_tool_enabled
from bkflow.harness.services.release.policy import ReleasePolicyUnavailable
from bkflow.harness.services.release.prepare import (
    ReleasePreparationRejected,
    prepare_release,
    validate_prepare_request,
)
from bkflow.harness.services.resolver import (
    CapabilityResolver,
    ProviderInfrastructureError,
)
from bkflow.harness.services.validator import (
    WorkflowValidationFailure,
    WorkflowValidator,
)
from bkflow.template.models import Template, TemplateSnapshot


def _failure(context, rejection, *, run=None, revision=None):
    """Project one safe release rejection into the common Harness Envelope."""
    error = WorkflowValidationFailure(
        rejection.code,
        path=rejection.path,
        category=rejection.category,
        repairable=rejection.repairable,
        retryable=rejection.retryable,
    ).as_error()
    response = WorkflowValidator(context, resolver=object())._envelope(
        ok=False,
        run=run,
        revision=revision,
        plan_hash_value=revision.plan_hash if revision else None,
        status=run.status if run else None,
        errors=[error],
    )
    if rejection.next_action:
        response["next_actions"] = [rejection.next_action]
    if rejection.code == "RELEASE_POLICY_UNAVAILABLE":
        response["next_actions"] = ["configure_release_policy"]
    response["summary"] = "Release preparation is blocked."
    return response


def prepare_release_with_context(
    context,
    payload,
    plugin_schema_service=None,
    *,
    resolver=None,
    release_policy=None,
    converter_class=None,
    pipeline_validator=None,
):
    """Validate a closed request and prepare an immutable release Manifest."""
    try:
        request = validate_prepare_request(payload)
        require_tool_enabled(context, "prepare_release")
        if release_policy is None:
            raise ReleasePreparationRejected("RELEASE_POLICY_UNAVAILABLE", "policy", repairable=False)
        active_resolver = resolver or CapabilityResolver(plugin_schema_service)
        return prepare_release(
            context,
            request,
            resolver=active_resolver,
            release_policy=release_policy,
            converter_class=converter_class,
            pipeline_validator=pipeline_validator,
        )
    except ReleasePreparationRejected as rejection:
        return _failure(context, rejection)
    except HarnessContextError as error:
        return _failure(context, ReleasePreparationRejected(error.code, "release", repairable=False))
    except IdempotencyConflict:
        return _failure(
            context,
            ReleasePreparationRejected("IDEMPOTENCY_CONFLICT", "idempotency_key", repairable=False),
        )
    except (IdempotencyInFlight, IdempotencyRecordImmutable, ProviderInfrastructureError, DatabaseError):
        return _failure(
            context,
            ReleasePreparationRejected("RETRYABLE_INFRA", "release", retryable=True),
        )
    except ReleasePolicyUnavailable:
        return _failure(
            context,
            ReleasePreparationRejected("RELEASE_POLICY_UNAVAILABLE", "policy", repairable=False),
        )
    except (
        HarnessRun.DoesNotExist,
        WorkflowPlanRevision.DoesNotExist,
        Template.DoesNotExist,
        TemplateSnapshot.DoesNotExist,
    ):
        return _failure(
            context,
            ReleasePreparationRejected("CAPABILITY_FORBIDDEN", "run_id", category="PERMISSION", repairable=False),
        )
    except ValidationError:
        return _failure(
            context,
            ReleasePreparationRejected("VALIDATION_STALE", "release", repairable=True),
        )
    except Exception:
        return _failure(
            context,
            ReleasePreparationRejected("RETRYABLE_INFRA", "release", retryable=True),
        )


__all__ = ["prepare_release_with_context"]
