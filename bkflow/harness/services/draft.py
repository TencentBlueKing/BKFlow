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

Draft-only materialization of a previously accepted Harness revision.
"""

from django.db import DatabaseError, transaction

from bkflow.harness.exceptions import (
    IdempotencyConflict,
    IdempotencyInFlight,
    IdempotencyRecordImmutable,
)
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.safety import is_safe_idempotency_key
from bkflow.harness.services.canonical import canonical_scope, sha256_json
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
from bkflow.harness.services.state import complete_draft_creation
from bkflow.template.models import Template
from bkflow.template.services.a2flow_template import (
    create_template_draft_from_pipeline_tree,
    update_template_draft_from_pipeline_tree,
)

TOOL_NAME = "create_workflow_draft"


class DraftValidationStale(ValueError):
    """The accepted validation facts no longer reproduce from current server facts."""


class DraftPermissionError(ValueError):
    """Caller supplied a run or revision outside its trusted server context."""


class DraftRequestInvalid(ValueError):
    """A closed draft request contains an unsafe raw persistence identifier."""


def _scope(context, run, key):
    return IdempotencyScope.for_run(context.platform_app, context.actor, context.space_id, TOOL_NAME, run, key)


def _context_matches(run, context):
    """Require every server-owned run dimension to equal the caller context."""
    return (
        run.platform == context.platform_key
        and run.platform_app == context.platform_app
        and run.actor == context.actor
        and run.space_id == context.space_id
        and run.scope == canonical_scope(context.scope_type, context.scope_value)
        and run.environment == context.target_environment
        and run.policy_version == context.policy_version
        and run.mcp_contract_version == context.mcp_contract_version
    )


def _managed_template(run):
    """Return the one server-recorded managed draft, if it still exists."""
    for artifact in run.artifact_references:
        if isinstance(artifact, dict) and artifact.get("type") == "harness_draft":
            return Template.objects.get(pk=artifact["template_id"])
    return None


def _create_workflow_draft(context, request, plugin_schema_service=None):
    """Create or update exactly one trusted draft; no release, debug or execution is performed."""
    required = {"run_id", "revision_id", "plan_hash", "idempotency_key"}
    if set(request) != required or not all(isinstance(request[key], str) and request[key] for key in required):
        raise DraftPermissionError("draft request must contain only trusted artifact identifiers")
    if not is_safe_idempotency_key(request["idempotency_key"]):
        raise DraftRequestInvalid("draft idempotency key is unsafe")
    with transaction.atomic():
        run = HarnessRun.objects.select_for_update().get(run_id=request["run_id"])
        if not _context_matches(run, context):
            raise DraftPermissionError("run is not eligible for draft creation")
        scope = _scope(context, run, request["idempotency_key"])
        request_hash = sha256_json(request)
        existing_idempotency = HarnessIdempotencyRecord.objects.filter(**scope.as_dict()).first()
        if existing_idempotency is not None and existing_idempotency.request_hash != request_hash:
            raise IdempotencyConflict("idempotency key was already used for a different request")
        if run.status == "DRAFT_READY" and existing_idempotency is not None:
            if existing_idempotency.status == "COMPLETED":
                return existing_idempotency.response_snapshot
            raise DraftPermissionError("run is not eligible for draft creation")
        if run.status not in ("VALIDATING", "DRAFT_READY"):
            raise DraftPermissionError("run is not eligible for draft creation")
        revision = WorkflowPlanRevision.objects.select_for_update().get(pk=request["revision_id"], run=run)
        if revision.plan_hash != request["plan_hash"]:
            raise DraftValidationStale("plan hash changed")
        report = (
            ValidationReport.objects.select_for_update()
            .filter(run=run, revision=revision, checkpoint="VALIDATE")
            .order_by("-id")
            .first()
        )
        if not report or report.result.get("valid") is not True or report.errors:
            raise DraftValidationStale("accepted validation report is missing")
        latest_report = (
            ValidationReport.objects.select_for_update().filter(run=run, checkpoint="VALIDATE").order_by("-id").first()
        )
        if latest_report is None or latest_report.id != report.id:
            raise DraftValidationStale("accepted validation report is stale")

        def materialize():
            resolver = CapabilityResolver(plugin_schema_service)
            governed = []
            for binding in CapabilityBinding.objects.filter(revision=revision).order_by("node_id"):
                capability = resolver.resolve(binding.capability_ref, expected_schema_hash=binding.schema_hash)
                if (
                    capability.resolved_version != binding.resolved_version
                    or capability.conversion_fingerprint != binding.conversion_fingerprint
                ):
                    raise DraftValidationStale("capability facts changed")
                governed.append({"node_id": binding.node_id, "capability": capability})
            from bkflow.harness.services.validator import WorkflowValidator

            validator = WorkflowValidator(context, resolver=resolver)
            if (
                validator._plan_hash(
                    revision.canonical_a2flow,
                    CapabilityBinding.objects.filter(revision=revision).order_by("node_id"),
                )
                != revision.plan_hash
            ):
                raise DraftValidationStale("plan facts changed")
            conversion = validator._convert(revision.canonical_a2flow, governed)
            validator._validate_pipeline_tree(conversion.pipeline_tree)
            if (
                report.validator_version != WorkflowValidator.VERSION
                or report.result.get("converter_fingerprint") != conversion.converter_fingerprint
                or report.result.get("pipeline_tree_hash") != sha256_json(conversion.pipeline_tree)
            ):
                raise DraftValidationStale("conversion facts changed")
            template = _managed_template(run)
            if template is None:
                template = create_template_draft_from_pipeline_tree(
                    pipeline_tree=conversion.pipeline_tree,
                    name=revision.canonical_a2flow.get("name", ""),
                    desc=revision.canonical_a2flow.get("desc", ""),
                    space_id=context.space_id,
                    username=context.actor,
                    scope_type=context.scope_type,
                    scope_value=context.scope_value,
                    bind_app_code=context.platform_app,
                )
                run.artifact_references = list(run.artifact_references) + [
                    {
                        "type": "harness_draft",
                        "template_id": template.id,
                        "revision_id": str(revision.id),
                        "pipeline_tree_hash": sha256_json(conversion.pipeline_tree),
                    }
                ]
                run.save(update_fields=["artifact_references", "update_at"])
            else:
                update_template_draft_from_pipeline_tree(
                    template=template,
                    username=context.actor,
                    pipeline_tree=conversion.pipeline_tree,
                    expected_space_id=context.space_id,
                    expected_bind_app_code=context.platform_app,
                )
                artifacts = list(run.artifact_references)
                for artifact in artifacts:
                    if isinstance(artifact, dict) and artifact.get("type") == "harness_draft":
                        artifact["revision_id"] = str(revision.id)
                        artifact["pipeline_tree_hash"] = sha256_json(conversion.pipeline_tree)
                run.artifact_references = artifacts
                run.save(update_fields=["artifact_references", "update_at"])
            if run.status == "VALIDATING":
                complete_draft_creation(run, revision, report)
                run.refresh_from_db(fields=["status"])
            response = validator._envelope(
                ok=True,
                run=run,
                revision=revision,
                plan_hash_value=revision.plan_hash,
                status="DRAFT_READY",
                artifact_refs=[
                    {
                        "template_id": template.id,
                        "pipeline_tree_hash": sha256_json(conversion.pipeline_tree),
                    }
                ],
            )
            return IdempotencyOutcome(response_snapshot=response, run=run, resource_reference=str(template.id))

        outcome = execute_idempotent(scope, request_hash, materialize)
        return outcome.response_snapshot


def create_workflow_draft(context, request, plugin_schema_service=None):
    """Return the frozen Harness envelope for every public draft outcome."""
    from bkflow.harness.services.validator import WorkflowValidator

    validator = WorkflowValidator(context)
    try:
        return _create_workflow_draft(context, request, plugin_schema_service=plugin_schema_service)
    except DraftRequestInvalid:
        return validator._input_failure(request, "SCHEMA_VALIDATION_ERROR", path="idempotency_key")
    except DraftPermissionError:
        return validator._input_failure(
            request, "CAPABILITY_FORBIDDEN", path="run_id", category="PERMISSION", repairable=False
        )
    except DraftValidationStale:
        return validator._input_failure(request, "VALIDATION_STALE", path="revision_id")
    except (CapabilityResolutionError, SchemaDriftError):
        return validator._input_failure(request, "VALIDATION_STALE", path="bindings")
    except IdempotencyConflict:
        return validator._input_failure(request, "IDEMPOTENCY_CONFLICT", path="idempotency_key", repairable=False)
    except (ProviderInfrastructureError, IdempotencyInFlight, IdempotencyRecordImmutable, DatabaseError):
        return validator._input_failure(request, "RETRYABLE_INFRA", path="draft", retryable=True)
    except (HarnessRun.DoesNotExist, WorkflowPlanRevision.DoesNotExist, Template.DoesNotExist, ValueError):
        return validator._input_failure(
            request, "CAPABILITY_FORBIDDEN", path="run_id", category="PERMISSION", repairable=False
        )
    except Exception:
        return validator._input_failure(request, "RETRYABLE_INFRA", path="draft", retryable=True)
