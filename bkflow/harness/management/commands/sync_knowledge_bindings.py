"""Synchronize a versioned knowledge binding manifest with explicit apply gating."""

from pathlib import Path

import yaml
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from bkflow.harness.services.knowledge.bindings import (
    DenyAllKnowledgeBindingGovernanceEvidence,
    KnowledgeBindingManifestError,
    KnowledgeBindingSynchronizer,
    KnowledgeBindingSyncLockError,
)
from bkflow.harness.services.knowledge.providers import KnowledgeProviderRegistry

MAX_MANIFEST_BYTES = 1024 * 1024


def production_provider_registry():
    """Stay fail-closed until DG-P1-01 supplies an authenticated production adapter."""
    return KnowledgeProviderRegistry()


def production_governance_evidence():
    """Deny all self-asserted governance facts until an authenticated evidence adapter exists."""
    return DenyAllKnowledgeBindingGovernanceEvidence()


def _load_document(path):
    """Load a bounded YAML document without reflecting untrusted content in failures."""
    try:
        raw = Path(path).read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            raise KnowledgeBindingManifestError()
        document = yaml.safe_load(raw.decode("utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise KnowledgeBindingManifestError()
    return document


def _ids(values):
    return ",".join(str(value) for value in values) or "-"


class Command(BaseCommand):
    help = "Preview or atomically apply the complete governed knowledge binding manifest."

    def add_arguments(self, parser):
        parser.add_argument("manifest")
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        try:
            document = _load_document(options["manifest"])
            synchronizer = KnowledgeBindingSynchronizer(
                production_provider_registry(),
                production_governance_evidence(),
            )
            if options["apply"]:
                result = synchronizer.apply(document)
                mode = "apply"
                create_count = len(result.created_ids)
                update_count = len(result.updated_ids)
                retire_count = len(result.retired_ids)
                created_ids = result.created_ids
                updated_ids = result.updated_ids
                retired_ids = result.retired_ids
            else:
                plan = synchronizer.plan(document)
                mode = "dry-run"
                create_count = len(plan.creates)
                update_count = len(plan.updates)
                retire_count = len(plan.retires)
                created_ids = ()
                updated_ids = tuple(existing.id for existing, _candidate in plan.updates)
                retired_ids = tuple(binding.id for binding in plan.retires)
        except (IntegrityError, KnowledgeBindingManifestError, ValidationError):
            raise CommandError(KnowledgeBindingManifestError.code)
        except KnowledgeBindingSyncLockError:
            raise CommandError(KnowledgeBindingSyncLockError.code)

        self.stdout.write(
            "knowledge_binding_sync mode={} create={} update={} retire={} "
            "created_ids={} updated_ids={} retired_ids={}".format(
                mode,
                create_count,
                update_count,
                retire_count,
                _ids(created_ids),
                _ids(updated_ids),
                _ids(retired_ids),
            )
        )
