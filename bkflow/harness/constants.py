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
from django.db import models

MAX_SCOPE_KEY_LENGTH = 255


class DebugContextEvidenceType(models.TextChoices):
    """Display-only debug snapshots, never trusted failure-attribution signals."""

    SNAPSHOT = "DEBUG_CONTEXT_SNAPSHOT", "Debug context snapshot"
    NODES = "DEBUG_CONTEXT_NODES", "Debug context nodes"


class HarnessRunStatus(models.TextChoices):
    """Lifecycle states for a Harness run, independent from Engine execution states."""

    INTENT_CAPTURED = "INTENT_CAPTURED", "Intent captured"
    PLANNING = "PLANNING", "Planning"
    VALIDATING = "VALIDATING", "Validating"
    NEEDS_REPAIR = "NEEDS_REPAIR", "Needs repair"
    DRAFT_READY = "DRAFT_READY", "Draft ready"
    DEBUGGING = "DEBUGGING", "Debugging"
    RELEASE_READY = "RELEASE_READY", "Release ready"
    APPROVAL_PENDING = "APPROVAL_PENDING", "Approval pending"
    PUBLISHING = "PUBLISHING", "Publishing"
    PUBLISHED = "PUBLISHED", "Published"
    EXECUTING = "EXECUTING", "Executing"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"
    EVIDENCE_FINALIZED = "EVIDENCE_FINALIZED", "Evidence finalized"


class ValidationCheckpoint(models.TextChoices):
    """Harness checkpoints that can emit a validation report."""

    VALIDATE = "VALIDATE", "Validate"
    DRAFT = "DRAFT", "Draft"
    DEBUG = "DEBUG", "Debug"
    RELEASE = "RELEASE", "Release"
    EXECUTE = "EXECUTE", "Execute"
    START_DEBUG_SESSION = "START_DEBUG_SESSION", "Start debug session"
    RUN_DEBUG = "RUN_DEBUG", "Run debug"
    PREPARE_RELEASE = "PREPARE_RELEASE", "Prepare release"
    PUBLISH = "PUBLISH", "Publish"
    PRE_EXECUTE = "PRE_EXECUTE", "Pre execute"
    POSTCONDITION = "POSTCONDITION", "Postcondition"
    FEEDBACK_INTAKE = "FEEDBACK_INTAKE", "Feedback intake"
    PROMOTION_EVAL = "PROMOTION_EVAL", "Promotion evaluation"


class DebugMode(models.TextChoices):
    """Scope of a Harness debug session, as accepted by P2 Tool requests."""

    STEP = "step", "Step"
    GLOBAL = "global", "Global"


class DebugExecutionMode(models.TextChoices):
    """Execution strategy for one debug request."""

    MOCK = "mock", "Mock"
    REAL = "real", "Real"


class DebugSessionStatus(models.TextChoices):
    """Lifecycle states for a revision-bound Harness debug session."""

    ACTIVE = "ACTIVE", "Active"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    TERMINATED = "TERMINATED", "Terminated"
    EXPIRED = "EXPIRED", "Expired"


class DebugControlAction(models.TextChoices):
    """Tagged control actions accepted by control_debug_session."""

    RESET = "reset", "Reset"
    TERMINATE = "terminate", "Terminate"
    SET_NODE_MOCK = "set_node_mock", "Set node mock"
    SET_CONTEXT_VAR = "set_context_var", "Set context variable"


class RiskLevel(models.TextChoices):
    """Risk tiers attached to exact capability bindings."""

    L0 = "L0", "L0"
    L1 = "L1", "L1"
    L2 = "L2", "L2"
    L3 = "L3", "L3"


class HarnessAction(models.TextChoices):
    """Stable policy actions for P3 release, execution, and global-real gates."""

    PREPARE_RELEASE = "prepare_release", "Prepare release"
    PUBLISH_WORKFLOW = "publish_workflow", "Publish workflow"
    START_WORKFLOW_EXECUTION = "start_workflow_execution", "Start workflow execution"
    GET_WORKFLOW_EXECUTION = "get_workflow_execution", "Get workflow execution"
    PAUSE = "pause", "Pause"
    RESUME = "resume", "Resume"
    REVOKE = "revoke", "Revoke"
    RETRY = "retry", "Retry"
    SKIP = "skip", "Skip"
    CALLBACK = "callback", "Callback"
    FORCED_FAIL = "forced_fail", "Forced fail"
    SKIP_EXG = "skip_exg", "Skip exclusive gateway"
    SKIP_CPG = "skip_cpg", "Skip conditional parallel gateway"
    RUN_DEBUG_GLOBAL_REAL = "run_debug_global_real", "Run global real debug"


class IdempotencyRecordStatus(models.TextChoices):
    """Persisted lifecycle for a write idempotency record."""

    IN_FLIGHT = "IN_FLIGHT", "In flight"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class KnowledgeTier(models.TextChoices):
    """Trusted identity dimensions required by a knowledge source."""

    GLOBAL = "GLOBAL", "Global"
    PUBLIC = "PUBLIC", "Public"
    PLATFORM = "PLATFORM", "Platform"
    SPACE = "SPACE", "Space"
    SCOPE = "SCOPE", "Scope"


class KnowledgeTrustLevel(models.TextChoices):
    """Review assurance attached to knowledge returned by a provider."""

    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"
    TRUSTED = "TRUSTED", "Trusted"


class KnowledgeBindingStatus(models.TextChoices):
    """Lifecycle states for a knowledge source binding."""

    ACTIVE = "ACTIVE", "Active"
    DISABLED = "DISABLED", "Disabled"
    DEPRECATED = "DEPRECATED", "Deprecated"
    RETIRED = "RETIRED", "Retired"


class KnowledgeRetrievalMode(models.TextChoices):
    """Supported provider retrieval strategies."""

    KEYWORD = "KEYWORD", "Keyword"
    VECTOR = "VECTOR", "Vector"
    HYBRID = "HYBRID", "Hybrid"


class GenerationFeedbackType(models.TextChoices):
    """Bounded observations accepted by the P4 feedback intake."""

    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    CORRECTION = "CORRECTION", "Correction"
    RUNTIME_ISSUE = "RUNTIME_ISSUE", "Runtime issue"
    BUSINESS_OUTCOME = "BUSINESS_OUTCOME", "Business outcome"


class FeedbackAttributionCategory(models.TextChoices):
    """Deterministic root-cause categories backed by typed Evidence."""

    REQUIREMENT = "REQUIREMENT", "Requirement"
    KNOWLEDGE = "KNOWLEDGE", "Knowledge"
    PROMPT = "PROMPT", "Prompt"
    SCHEMA = "SCHEMA", "Schema"
    RESOLVER = "RESOLVER", "Resolver"
    VALIDATOR = "VALIDATOR", "Validator"
    PERMISSION = "PERMISSION", "Permission"
    PLUGIN = "PLUGIN", "Plugin"
    ENVIRONMENT = "ENVIRONMENT", "Environment"
    POSTCONDITION = "POSTCONDITION", "Postcondition"


class ImprovementCandidateType(models.TextChoices):
    """Owner-routed artifacts P4 may draft but never auto-publish."""

    KNOWLEDGE = "KNOWLEDGE", "Knowledge"
    REGISTRY = "REGISTRY", "Registry"
    VALIDATOR_POLICY = "VALIDATOR_POLICY", "Validator policy"
    PROMPT_SKILL = "PROMPT_SKILL", "Prompt or skill"
    EVAL = "EVAL", "Evaluation"


class ImprovementCandidateStatus(models.TextChoices):
    """Owner-controlled lifecycle independent from Harness run outcomes."""

    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "In review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    PUBLISHED = "PUBLISHED", "Published"
    RETIRED = "RETIRED", "Retired"
