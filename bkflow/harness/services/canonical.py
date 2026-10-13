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

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from bkflow.harness.constants import MAX_SCOPE_KEY_LENGTH


def canonical_scope(scope_type, scope_value):
    """Serialize one trusted scope pair as an injective JSON array for every consumer."""
    if scope_type is None and scope_value is None:
        return ""
    if not isinstance(scope_type, str) or not scope_type or not isinstance(scope_value, str) or not scope_value:
        raise ValueError("scope type and value must both be present")
    try:
        scope_type.encode("utf-8")
        scope_value.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("scope contains invalid text") from error
    serialized = json.dumps([scope_type, scope_value], ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > MAX_SCOPE_KEY_LENGTH:
        raise ValueError("scope exceeds persistence limit")
    return serialized


def canonical_json_bytes(value):
    """Encode JSON using the one approved deterministic Harness representation.

    :param value: JSON-compatible value to serialize.
    :return: UTF-8 bytes using sorted object keys and compact separators.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value):
    """Return the lowercase SHA-256 digest of a canonical JSON value."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def schema_hash(schema):
    """Return a stable schema fingerprint using the common JSON hash contract."""
    return sha256_json(schema)


@dataclass(frozen=True)
class CanonicalCapabilityBinding:
    """The persisted CapabilityBinding facts that participate in ``plan_hash``."""

    node_id: str
    capability_ref: str
    resolved_version: str
    schema_hash: str
    conversion_fingerprint: Optional[str]
    credential_ref: Optional[str]
    risk: str

    @classmethod
    def from_value(cls, binding):
        """Build a strict binding DTO from mapping or persisted-model input."""
        required = ("node_id", "capability_ref", "resolved_version", "schema_hash", "risk")
        values = {}
        for key in required:
            if isinstance(binding, Mapping):
                value = binding.get(key)
            else:
                value = getattr(binding, key, None)
            if value is None or value == "":
                raise ValueError("capability binding requires {}".format(key))
            values[key] = value
        credential_ref = (
            binding.get("credential_ref") if isinstance(binding, Mapping) else getattr(binding, "credential_ref", None)
        )
        conversion_fingerprint = (
            binding.get("conversion_fingerprint")
            if isinstance(binding, Mapping)
            else getattr(binding, "conversion_fingerprint", None)
        )
        return cls(credential_ref=credential_ref, conversion_fingerprint=conversion_fingerprint, **values)

    def as_dict(self):
        """Return the only per-binding fields persisted by the P0 data model."""
        return {
            "node_id": self.node_id,
            "capability_ref": self.capability_ref,
            "resolved_version": self.resolved_version,
            "schema_hash": self.schema_hash,
            "conversion_fingerprint": self.conversion_fingerprint,
            "credential_ref": self.credential_ref,
            "risk": self.risk,
        }


def plan_hash(
    canonical_a2flow,
    capability_bindings,
    *,
    space_id,
    scope,
    environment,
    credential_authorization_scope,
    execution_policy,
    risk_policy,
    retry_policy,
    timeout_policy,
    compensation_policy,
    postconditions,
    model_name=None,
    conversation_wording=None,
    display_copy=None,
    token_plaintext=None,
    trace_metadata=None,
):
    """Fingerprint exactly the approved, durable plan security and execution data.

    Presentation, model, token, and trace parameters are deliberately accepted
    only so callers can pass a full request object without making those values
    durable plan facts.
    """
    del model_name, conversation_wording, display_copy, token_plaintext, trace_metadata
    bindings = [CanonicalCapabilityBinding.from_value(binding).as_dict() for binding in capability_bindings]
    bindings.sort(key=canonical_json_bytes)
    value = {
        "canonical_a2flow": canonical_a2flow,
        "capability_bindings": bindings,
        "trusted_context": {"space_id": space_id, "scope": scope, "environment": environment},
        "credential_authorization_scope": credential_authorization_scope,
        "execution_policy": execution_policy,
        "risk_policy": risk_policy,
        "retry_policy": retry_policy,
        "timeout_policy": timeout_policy,
        "compensation_policy": compensation_policy,
        "postconditions": postconditions,
    }
    return sha256_json(value)
