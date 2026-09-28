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
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from bkflow.harness.safety import normalize_correlation_id


class HarnessContextError(RuntimeError):
    """Describe a fail-closed trusted-context construction error."""

    def __init__(self, code):
        self.code = code
        super().__init__("Harness context is unavailable.")


@dataclass(frozen=True)
class TrustedHarnessContext:
    """Immutable platform authority derived outside model-controlled input."""

    platform_key: str
    platform_app: str
    actor: str
    space_id: int
    scope_type: Optional[str]
    scope_value: Optional[str]
    target_environment: str
    policy_version: str
    mcp_contract_version: str
    correlation_id: str

    def __post_init__(self):
        """Enforce a safe correlation identifier for direct and HTTP service callers."""
        object.__setattr__(self, "correlation_id", normalize_correlation_id(self.correlation_id))

    @classmethod
    def from_request(cls, request, space_id=None, space=None):
        """Build this context from gateway identities, a route space, and deployment configuration."""
        from bkflow.harness.services.context import build_trusted_harness_context

        return build_trusted_harness_context(request=request, space_id=space_id, space=space)


_KNOWLEDGE_CLASSIFICATION = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class KnowledgeQuery:
    """Bounded request data used by the deterministic knowledge router."""

    query: str
    top_k: int
    data_classification: str
    run_id: Optional[str] = None

    def __post_init__(self):
        """Reject malformed values before they reach ACL or provider boundaries."""
        for field_name, value in (
            ("query", self.query),
            ("data_classification", self.data_classification),
            ("run_id", self.run_id),
        ):
            if isinstance(value, str):
                try:
                    value.encode("utf-8")
                except UnicodeError as error:
                    raise ValueError("{} must be valid UTF-8".format(field_name)) from error
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 2000:
            raise ValueError("query must be a bounded non-empty string")
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or not 1 <= self.top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        if not isinstance(self.data_classification, str) or not _KNOWLEDGE_CLASSIFICATION.fullmatch(
            self.data_classification
        ):
            raise ValueError("data_classification is invalid")
        if self.run_id is not None and (not isinstance(self.run_id, str) or not self.run_id or len(self.run_id) > 64):
            raise ValueError("run_id is invalid")

    @classmethod
    def from_request(cls, request):
        """Build a strict DTO without accepting identity or routing dimensions from model input."""
        if not isinstance(request, Mapping):
            raise ValueError("knowledge request must be an object")
        allowed = {"query", "top_k", "data_classification", "run_id"}
        if set(request) - allowed:
            raise ValueError("knowledge request contains unsupported fields")
        return cls(
            query=request.get("query"),
            top_k=request.get("top_k", 10),
            data_classification=request.get("data_classification", "internal"),
            run_id=request.get("run_id"),
        )


@dataclass(frozen=True)
class KnowledgeHit:
    """One redacted knowledge result that can never carry policy authority."""

    hit_ref: str
    binding_id: int
    tier: str
    provider: str
    title: str
    excerpt: str
    citation_ref: str
    source_ref: str
    snapshot_version: str
    trust_level: str
    applicable_scope: str
    provider_score: float
    final_score: float
    expires_at: Optional[str]
    policy_effect: str = "ADVISORY"

    def __post_init__(self):
        """Prevent untrusted knowledge from claiming Validator or Policy semantics."""
        if self.policy_effect != "ADVISORY":
            raise ValueError("knowledge policy_effect must remain ADVISORY")


@dataclass(frozen=True)
class KnowledgeConflictAnnotation:
    """Bounded, non-executable metadata describing contradictory retrieved guidance."""

    topic_ref: str
    resolution: str
    preferred_hit_ref: str
    alternative_hit_refs: Tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeSearchResult:
    """Router result consumed by the later APIGW Envelope adapter."""

    query_fingerprint: str
    hits: Tuple[KnowledgeHit, ...] = ()
    conflict_annotations: Tuple[KnowledgeConflictAnnotation, ...] = ()
    artifact_refs: Tuple[str, ...] = ()
    warning_codes: Tuple[str, ...] = ()
    error_codes: Tuple[str, ...] = ()
