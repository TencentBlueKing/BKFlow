"""Database-locking contracts for the real Task 6 validation service."""

from copy import deepcopy
from threading import Event, Lock, Thread
from unittest import skipIf

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.resolver import CapabilityResolver
from bkflow.harness.services.validator import WorkflowValidator


@skipIf(connection.vendor == "sqlite", "SQLite does not provide the row-locking semantics exercised here")
class TestWorkflowValidatorTwoConnectionTransactions(TransactionTestCase):
    """Exercise whole-run locks through two independent database connections."""

    def setUp(self):
        self.context = TrustedHarnessContext(
            platform_key="bkfara",
            platform_app="bkfara_app",
            actor="transaction-tester",
            space_id=42,
            scope_type="project",
            scope_value="42",
            target_environment="stag",
            policy_version="2026.09",
            mcp_contract_version="1.0.0",
            correlation_id="two-connection",
        )
        self.capability_ref = encode_capability_ref("component", None, "sleep_timer", "v1.0.0")
        self.schema = {
            "version": "v1.0.0",
            "resolved_version": "v1.0.0",
            "inputs": [{"key": "bk_timing", "type": "int", "required": True}],
            "outputs": [],
            "conversion_metadata": {
                "kind": "component",
                "wrapper_code": "sleep_timer",
                "wrapper_version": "v1.0.0",
            },
        }

    def _validator(self):
        schema = self.schema

        class RegistryBoundary:
            def list_plugins(self, limit=100, offset=0, **kwargs):
                plugins = [{"plugin_type": "component", "source_key": None, "code": "sleep_timer", "version": "v1.0.0"}]
                return plugins[offset : offset + limit], len(plugins)

            def get_plugin_schema(self, **kwargs):
                return schema

            def manifest_identity_exists(self, *args):
                return True

        resolver = CapabilityResolver(
            RegistryBoundary(),
            manifest={
                "manifest_version": "p0-v1",
                "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
                "capabilities": [],
            },
        )
        return WorkflowValidator(self.context, resolver=resolver)

    def _request(self, key, run_id=None, valid=True):
        request = {
            "intent_spec": {"goal": "two connection"},
            "a2flow": {
                "version": "2.0",
                "name": "two connection",
                "nodes": [
                    {
                        "id": "node_1",
                        "name": "sleep",
                        "code": "sleep_timer",
                        "plugin_type": "component",
                        "inputs": {"bk_timing": 1} if valid else {},
                        "next": "end",
                    }
                ],
            },
            "bindings": [
                {
                    "node_id": "node_1",
                    "capability_ref": self.capability_ref,
                    "schema_hash": schema_hash({"inputs": self.schema["inputs"], "outputs": []}),
                    "credential_ref": None,
                }
            ],
            "idempotency_key": key,
            "client_context": {"conversation_ref": "two-connection"},
        }
        if run_id:
            request["run_id"] = run_id
        return request

    def _two_connections(self, left_request, right_request):
        """Prove B reaches the lock SQL boundary but cannot pass A's held row lock."""
        first_locked, release_first, second_pre_lock, allow_second_query, second_entered = (
            Event(),
            Event(),
            Event(),
            Event(),
            Event(),
        )
        hook_guard = Lock()
        hook_calls = []
        results, errors = [], []

        def hook(_run):
            with hook_guard:
                hook_calls.append(1)
                is_first = len(hook_calls) == 1
            if is_first:
                first_locked.set()
                release_first.wait(timeout=10)
            else:
                second_entered.set()

        def pre_lock_hook(_run):
            with hook_guard:
                is_second = len(hook_calls) == 1
            if is_second:
                second_pre_lock.set()
                allow_second_query.wait(timeout=10)

        def call(request):
            close_old_connections()
            try:
                validator = self._validator()
                validator.test_pre_run_lock_hook = pre_lock_hook
                validator.test_run_lock_hook = hook
                response = validator.validate_workflow(deepcopy(request))
                results.append(response)
                return
            except Exception as error:  # pragma: no cover - asserted by the parent thread
                errors.append(error)
            finally:
                close_old_connections()

        left = Thread(target=call, args=(left_request,))
        right = Thread(target=call, args=(right_request,))
        left.start()
        self.assertTrue(first_locked.wait(timeout=10))
        right.start()
        self.assertTrue(second_pre_lock.wait(timeout=10))
        self.assertFalse(second_entered.is_set(), "second connection passed the lock before issuing its SQL query")
        allow_second_query.set()
        self.assertFalse(second_entered.wait(timeout=1), "second connection bypassed the shared run lock")
        release_first.set()
        threads = [left, right]
        for thread in threads:
            thread.join(timeout=30)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        if errors:
            raise errors[0]
        return results

    def _seed_run(self, key="seed"):
        """Every concurrent case starts from one durable run so the whole-run lock is exercised."""
        seed = self._validator().validate_workflow(self._request(key))
        self.assertTrue(seed["ok"])
        return seed

    def _assert_serialized_artifacts(self, run_id, success_reports, failure_reports):
        revisions = list(WorkflowPlanRevision.objects.filter(run__run_id=run_id).order_by("sequence"))
        self.assertEqual([item.sequence for item in revisions], list(range(1, len(revisions) + 1)))
        self.assertTrue(
            all(item.parent_revision_id == revisions[index - 1].id for index, item in enumerate(revisions) if index)
        )
        reports = list(ValidationReport.objects.filter(run__run_id=run_id).order_by("id"))
        self.assertEqual(len(reports), success_reports + failure_reports)
        self.assertEqual(sum(bool(report.revision_id) for report in reports), success_reports)
        self.assertEqual(sum(report.revision_id is None for report in reports), failure_reports)
        self.assertEqual(
            HarnessIdempotencyRecord.objects.filter(run__run_id=run_id, status="COMPLETED").count(), len(reports)
        )
        run = HarnessRun.objects.get(run_id=run_id)
        expected_state = "VALIDATING" if reports[-1].revision_id else "NEEDS_REPAIR"
        self.assertEqual(run.status, expected_state)

    def test_two_connections_success_success(self):
        seed = self._seed_run()
        results = self._two_connections(
            self._request("success-a", run_id=seed["run_id"]), self._request("success-b", run_id=seed["run_id"])
        )

        self.assertEqual(sorted(result["ok"] for result in results), [True, True])
        self._assert_serialized_artifacts(seed["run_id"], success_reports=3, failure_reports=0)

    def test_two_connections_repair_repair(self):
        seed = self._seed_run("repair-seed")
        failure = self._validator().validate_workflow(
            self._request("repair-seed-failure", run_id=seed["run_id"], valid=False)
        )
        self.assertFalse(failure["ok"])
        results = self._two_connections(
            self._request("repair-a", run_id=seed["run_id"]), self._request("repair-b", run_id=seed["run_id"])
        )

        self.assertEqual(sorted(result["ok"] for result in results), [True, True])
        self._assert_serialized_artifacts(seed["run_id"], success_reports=3, failure_reports=1)

    def test_two_connections_success_failure(self):
        seed = self._seed_run()
        results = self._two_connections(
            self._request("success", run_id=seed["run_id"]),
            self._request("failure", run_id=seed["run_id"], valid=False),
        )

        self.assertEqual(sorted(result["ok"] for result in results), [False, True])
        self._assert_serialized_artifacts(seed["run_id"], success_reports=2, failure_reports=1)

    def test_two_connections_failure_success(self):
        seed = self._seed_run()
        results = self._two_connections(
            self._request("failure", run_id=seed["run_id"], valid=False),
            self._request("success", run_id=seed["run_id"]),
        )

        self.assertEqual(sorted(result["ok"] for result in results), [False, True])
        self._assert_serialized_artifacts(seed["run_id"], success_reports=2, failure_reports=1)

    def test_two_connections_contention_uses_distinct_idempotency_keys(self):
        seed = self._seed_run("contention-seed")
        results = self._two_connections(
            self._request("contention-a", run_id=seed["run_id"]),
            self._request("contention-b", run_id=seed["run_id"]),
        )

        self.assertEqual(sorted(result["ok"] for result in results), [True, True])
        self._assert_serialized_artifacts(seed["run_id"], success_reports=3, failure_reports=0)
