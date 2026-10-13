"""Administrative governance for Harness knowledge bindings and audits."""

from django.contrib import admin

from bkflow.harness.models import (
    GenerationFeedback,
    HarnessEvalCase,
    HarnessEvalRun,
    ImprovementCandidate,
    KnowledgeCandidate,
    KnowledgeRetrievalAudit,
    KnowledgeSourceBinding,
)


class ReadOnlyHarnessEvidenceAdmin(admin.ModelAdmin):
    """Expose evidence to authorized Django viewers without creating a mutation bypass."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeSourceBinding)
class KnowledgeSourceBindingAdmin(admin.ModelAdmin):
    """Expose synchronized binding state without bypassing governed manifests."""

    list_display = ("provider", "source_ref", "tier", "status", "owner", "environment", "update_at")
    list_filter = ("tier", "status", "owner")
    search_fields = ("provider", "source_ref", "owner", "reviewer")
    readonly_fields = tuple(field.name for field in KnowledgeSourceBinding._meta.get_fields())

    def has_add_permission(self, request):
        """Bindings enter the product only through the controlled synchronizer."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent direct activation, ownership, and trust changes through Admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Preserve governance history by requiring synchronized retirement."""
        return False


@admin.register(KnowledgeRetrievalAudit)
class KnowledgeRetrievalAuditAdmin(admin.ModelAdmin):
    """Expose retrieval evidence as an immutable administrative view."""

    list_display = ("correlation_id", "outcome", "duration_ms", "run", "create_at")
    search_fields = ("correlation_id", "query_fingerprint")
    readonly_fields = tuple(field.name for field in KnowledgeRetrievalAudit._meta.get_fields())

    def has_add_permission(self, request):
        """Audits are written by the retrieval path, never through Admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Deny audit mutation while retaining Django's separate view permission."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Retain audit evidence by denying both soft and hard deletion."""
        return False


@admin.register(GenerationFeedback)
class GenerationFeedbackAdmin(ReadOnlyHarnessEvidenceAdmin):
    list_display = ("id", "feedback_type", "space_id", "run", "create_at")
    list_filter = ("feedback_type", "space_id")
    readonly_fields = tuple(field.name for field in GenerationFeedback._meta.get_fields())


@admin.register(ImprovementCandidate)
class ImprovementCandidateAdmin(ReadOnlyHarnessEvidenceAdmin):
    """Owner actions use locked services; Admin is intentionally evidence-only."""

    list_display = ("id", "candidate_type", "status", "owner_ref", "reviewer_ref", "target_system", "update_at")
    list_filter = ("candidate_type", "status", "target_system")
    search_fields = ("id", "owner_ref", "reviewer_ref", "target_system")
    readonly_fields = tuple(field.name for field in ImprovementCandidate._meta.get_fields())


@admin.register(KnowledgeCandidate)
class KnowledgeCandidateAdmin(ReadOnlyHarnessEvidenceAdmin):
    list_display = ("candidate", "target_binding", "target_source_ref", "create_at")
    readonly_fields = tuple(field.name for field in KnowledgeCandidate._meta.get_fields())


@admin.register(HarnessEvalCase)
class HarnessEvalCaseAdmin(ReadOnlyHarnessEvidenceAdmin):
    list_display = ("case_id", "case_version", "tier", "source_candidate", "create_at")
    list_filter = ("tier",)
    readonly_fields = tuple(field.name for field in HarnessEvalCase._meta.get_fields())


@admin.register(HarnessEvalRun)
class HarnessEvalRunAdmin(ReadOnlyHarnessEvidenceAdmin):
    list_display = ("id", "runner_mode", "status", "safety_result", "candidate", "finalized_at")
    list_filter = ("runner_mode", "status", "safety_result")
    readonly_fields = tuple(field.name for field in HarnessEvalRun._meta.get_fields())
