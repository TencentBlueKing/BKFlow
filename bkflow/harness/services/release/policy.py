"""Closed server-owned risk and action-digest policy."""

import re
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType

from django.core.exceptions import ValidationError

from bkflow.harness.constants import HarnessAction, RiskLevel
from bkflow.harness.safety import (
    is_bounded_non_secret_json,
    is_safe_harness_text,
    safe_opaque_identifier,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.evidence import is_safe_evidence_ref

ACTION_RISK = MappingProxyType(
    {
        HarnessAction.PREPARE_RELEASE: RiskLevel.L0,
        HarnessAction.GET_WORKFLOW_EXECUTION: RiskLevel.L0,
        HarnessAction.PUBLISH_WORKFLOW: RiskLevel.L2,
        HarnessAction.START_WORKFLOW_EXECUTION: RiskLevel.L2,
        HarnessAction.PAUSE: RiskLevel.L2,
        HarnessAction.RESUME: RiskLevel.L2,
        HarnessAction.REVOKE: RiskLevel.L2,
        HarnessAction.RETRY: RiskLevel.L2,
        HarnessAction.SKIP: RiskLevel.L3,
        HarnessAction.CALLBACK: RiskLevel.L3,
        HarnessAction.FORCED_FAIL: RiskLevel.L3,
        HarnessAction.SKIP_EXG: RiskLevel.L3,
        HarnessAction.SKIP_CPG: RiskLevel.L3,
        HarnessAction.RUN_DEBUG_GLOBAL_REAL: RiskLevel.L3,
    }
)


@dataclass(frozen=True)
class ActionDecision:
    """Deterministic risk decision bound to one normalized action payload."""

    action: str
    risk_level: str
    requires_approval: bool
    action_digest: str
    policy_version: str


class ReleasePolicyUnavailable(ValueError):
    """The trusted policy version has no server-owned release profile."""


class ReleasePolicy:
    """Resolve immutable postconditions from an injected versioned server policy."""

    def __init__(self, *, profiles):
        if not isinstance(profiles, dict):
            raise ValidationError("Release policy profiles are invalid")
        copied = deepcopy(profiles)
        for version, postconditions in copied.items():
            if safe_opaque_identifier(version) is None or not is_bounded_non_secret_json(postconditions):
                raise ValidationError("Release policy profile is invalid")
        self._profiles = MappingProxyType(copied)

    def postconditions_for(self, policy_version):
        """Return a detached policy DTO or fail closed for an unknown version."""
        if safe_opaque_identifier(policy_version) is None or policy_version not in self._profiles:
            raise ReleasePolicyUnavailable("Release policy is unavailable")
        return deepcopy(self._profiles[policy_version])


class ActionPolicy:
    """Evaluate only declared Harness actions using immutable server policy."""

    @staticmethod
    def _has_unsafe_uri(value):
        if isinstance(value, dict):
            return any(ActionPolicy._has_unsafe_uri(item) for item in value.values())
        if isinstance(value, list):
            return any(ActionPolicy._has_unsafe_uri(item) for item in value)
        return isinstance(value, str) and "://" in value and not is_safe_evidence_ref(value)

    def requirements_for(self, actions, policy_version):
        """Return canonical approval requirements before a Manifest hash exists."""
        if not isinstance(actions, (list, tuple)) or safe_opaque_identifier(policy_version) is None:
            raise ValidationError("Approval requirement input is invalid")
        if any(not isinstance(action, str) for action in actions):
            raise ValidationError("Unknown Harness action")
        requested = set(actions)
        if any(action not in ACTION_RISK for action in requested):
            raise ValidationError("Unknown Harness action")
        requirements = []
        for action, risk_level in ACTION_RISK.items():
            if action not in requested or risk_level not in {RiskLevel.L2, RiskLevel.L3}:
                continue
            requirements.append(
                {
                    "action": action,
                    "risk_level": risk_level,
                    "policy_ref": "policy://{}/{}/{}".format(policy_version, action, risk_level.lower()),
                }
            )
        return requirements

    def evaluate(
        self,
        *,
        action,
        manifest_hash,
        plan_hash,
        target_resource,
        normalized_params,
        policy_version,
    ):
        """Return a closed risk decision or fail before hashing unsafe input."""
        if not isinstance(action, str) or action not in ACTION_RISK:
            raise ValidationError("Unknown Harness action")
        if not isinstance(manifest_hash, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_hash) is None:
            raise ValidationError("Manifest hash is invalid")
        if not isinstance(plan_hash, str) or re.fullmatch(r"[0-9a-f]{64}", plan_hash) is None:
            raise ValidationError("Plan hash is invalid")
        if (
            not isinstance(target_resource, dict)
            or not is_bounded_non_secret_json(target_resource)
            or self._has_unsafe_uri(target_resource)
        ):
            raise ValidationError("Target resource is invalid")
        if (
            not isinstance(normalized_params, dict)
            or not is_bounded_non_secret_json(normalized_params)
            or self._has_unsafe_uri(normalized_params)
        ):
            raise ValidationError("Action parameters are invalid")
        if not is_safe_harness_text(policy_version, max_chars=64, max_bytes=256, allow_empty=False):
            raise ValidationError("Policy version is invalid")
        risk_level = ACTION_RISK[action]
        action_digest = sha256_json(
            {
                "action": action,
                "manifest_hash": manifest_hash,
                "normalized_params": normalized_params,
                "plan_hash": plan_hash,
                "policy_version": policy_version,
                "target_resource": target_resource,
            }
        )
        return ActionDecision(
            action=action,
            risk_level=risk_level,
            requires_approval=risk_level in {RiskLevel.L2, RiskLevel.L3},
            action_digest=action_digest,
            policy_version=policy_version,
        )
