"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.

Minimal real Harness chains used by the versioned P0 Golden Cases.
"""

from contextlib import ExitStack
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.urls import resolve
from pipeline.component_framework.models import ComponentModel
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.capability_ref import decode_capability_ref
from bkflow.harness.services.facade import HarnessFacade
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.models import (
    Credential,
    CredentialScopeLevel,
    CredentialType,
    Space,
    SpaceConfig,
)
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils.api_client import HttpRequestResult

_REAL_SPACE_CONFIG_GET = SpaceConfig.get_config


@dataclass(frozen=True)
class GoldenObservation:
    """The observable P0 result used for the release-gate assertion."""

    tool_sequence: list
    final_state: str
    capability: object
    side_effects: set
    candidates: object = None


class GoldenCatalog:
    """Minimal provider I/O fixture behind the production PluginSchemaService.

    The Golden runner deliberately creates real catalog and authorization rows.
    Only the three provider transports are replaced, so Projection and Resolver
    exercise the exact catalog, ACL, lifecycle, and version code used in P0.
    """

    def __init__(self, snapshot, *, candidates=1, space_id=1, username="golden-actor"):
        self.snapshot = dict(snapshot)
        self.candidates = candidates
        self.space_id = space_id
        self.stack = ExitStack()
        self.service = PluginSchemaService(space_id=space_id, username=username)
        self.schemas = {}
        self.uniform_header_calls = []
        self.uniform_provider_payloads = []

    def __enter__(self):
        cache.clear()
        try:
            self._install_outer_io()
            if self.candidates:
                self._create_catalog_records()
        except BaseException:
            # __exit__ is not invoked when __enter__ fails (e.g. strict MySQL
            # rejects fixture data); never leak provider mocks into later tests.
            self.stack.close()
            cache.clear()
            raise
        return self

    def __exit__(self, *exc):
        self.stack.close()
        cache.clear()

    def _install_outer_io(self):
        self.component_library = self.stack.enter_context(
            patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
        )
        self.remote_client = self.stack.enter_context(
            patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
        )
        self.uniform_client = self.stack.enter_context(
            patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
        )
        self.space_config = self.stack.enter_context(
            patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config")
        )
        self.component_library.get_component_class.side_effect = self._component_class
        self.remote_client.side_effect = self._remote_provider
        self.uniform_client.side_effect = self._uniform_provider
        self.space_config.side_effect = self._space_config

    def _records(self):
        for index in range(self.candidates):
            record = dict(self.snapshot)
            if self.candidates > 1:
                record["code"] = "{}_candidate{}".format(record["code"], index + 1)
            yield record

    def _create_catalog_records(self):
        for record in self._records():
            self.schemas[(record["plugin_type"], record.get("source_key"), record["code"])] = {
                "version": record["version"],
                "inputs": [{"key": record["input_key"], "type": "string", "required": True}],
                "outputs": ([{"key": record["output_key"], "type": "string"}] if record.get("output_key") else []),
            }
            if record["plugin_type"] == "component":
                ComponentModel.objects.create(
                    code=record["code"],
                    version=record["version"],
                    name=record.get("display_name", "golden-{}".format(record["code"])),
                    status=True,
                )
            elif record["plugin_type"] == "remote_plugin":
                BKPlugin.objects.create(
                    code=record["code"], name=record["code"], tag=1, logo_url="", introduction="golden", managers=[]
                )
                BKPluginAuthorization.objects.create(
                    code=record["code"], status=AuthStatus.authorized.value, config={"white_list": ["*"]}
                )
            elif record.get("source_key") is not None:
                OpenPluginCatalogIndex.objects.create(
                    space_id=self.space_id,
                    source_key=record["source_key"],
                    plugin_id=record["code"],
                    plugin_code=record["code"],
                    plugin_name=record["code"],
                    plugin_source="golden",
                    wrapper_version="v4.0.0",
                    default_version=record["version"],
                    latest_version=record["version"],
                    versions=[record["version"]],
                    meta_url_template="https://golden.invalid/{}/{}/{{version}}".format(
                        record["source_key"], record["code"]
                    ),
                    description="golden",
                    status=OpenPluginCatalogIndex.Status.AVAILABLE,
                )
                SpaceOpenPluginAvailability.objects.create(
                    space_id=self.space_id,
                    source_key=record["source_key"],
                    plugin_id=record["code"],
                    enabled=True,
                )
        if self.snapshot["plugin_type"] == "uniform_api" and not self.snapshot.get("use_database_credentials"):
            Credential.objects.create(
                space_id=self.space_id,
                name="golden-gateway-{}".format(self.snapshot["code"]),
                type=CredentialType.BK_APP.value,
                content={
                    "bk_app_code": "golden",
                    "bk_app_secret": self.snapshot.get("credential_secret", "fixture"),
                },
                scope_level=CredentialScopeLevel.ALL.value,
            )

    def _component_class(self, code, version):
        schema = self.schemas[("component", None, code)]
        component = MagicMock()
        component.desc = "Golden component"
        component.inputs_format.return_value = schema["inputs"]
        component.outputs_format.return_value = schema["outputs"]
        assert version == schema["version"]
        return component

    def _remote_provider(self, code):
        schema = self.schemas[("remote_plugin", None, code)]
        client = MagicMock()
        client.get_meta.return_value = {
            "result": True,
            "data": {"versions": [schema["version"]], "inputs": schema["inputs"], "outputs": schema["outputs"]},
        }
        return client

    def _uniform_provider(self):
        client = MagicMock()

        def record_header(**kwargs):
            self.uniform_header_calls.append(dict(kwargs))
            return {}

        client.gen_default_apigw_header.side_effect = record_header

        def request(**kwargs):
            url = kwargs["url"]
            if url == "https://golden.invalid/legacy-list":
                return HttpRequestResult(
                    result=True,
                    message="",
                    json_resp={
                        "data": {
                            "total": self.candidates,
                            "apis": [
                                {
                                    "id": record["code"],
                                    "name": record["code"],
                                    "wrapper_version": "v3.0.0",
                                    "meta_url": "https://golden.invalid/legacy/{}/meta".format(record["code"]),
                                }
                                for record in self._records()
                            ],
                        }
                    },
                )
            code = url.split("/")[-2]
            schema = self.schemas[("uniform_api", self.snapshot.get("source_key"), code)]
            inputs = [dict(item, name=item.get("name", item["key"])) for item in schema["inputs"]]
            outputs = [dict(item, name=item.get("name", item["key"])) for item in schema["outputs"]]
            data = {
                "id": code,
                "name": code,
                "url": "https://runtime.golden.invalid/{}".format(code),
                "methods": ["POST"],
                "inputs": inputs,
                "outputs": outputs,
            }
            if self.snapshot.get("source_key") is not None:
                data["plugin_version"] = schema["version"]
            data.update(self.snapshot.get("provider_extras", {}))
            self.uniform_provider_payloads.append(dict(data))
            return HttpRequestResult(
                result=True,
                message="",
                json_resp={"result": True, "data": data},
            )

        client.request.side_effect = request
        return client

    def _space_config(self, *args, **kwargs):
        config_name = kwargs.get("config_name") or (args[1] if len(args) > 1 else None)
        if (
            config_name == "api_gateway_credential_name"
            and self.snapshot["plugin_type"] == "uniform_api"
            and not self.snapshot.get("use_database_credentials")
        ):
            return "golden-gateway-{}".format(self.snapshot["code"])
        if config_name == "uniform_api" and self.snapshot.get("source_key") is None:
            return {
                "api": {
                    "default": {
                        "meta_apis": "https://golden.invalid/legacy-list",
                        "api_categories": "https://golden.invalid/categories",
                        "display_name": "Golden legacy",
                    }
                }
            }
        return _REAL_SPACE_CONFIG_GET(*args, **kwargs)

    def drift(self, mode):
        """Mutate a provider fact after search, leaving all Harness code real."""
        record = self.snapshot
        if mode == "version":
            ComponentModel.objects.filter(code=record["code"], version=record["version"]).update(status=False)
            ComponentModel.objects.create(
                code=record["code"], version="2.0.0", name="golden-{}".format(record["code"]), status=True
            )
            self.schemas[("component", None, record["code"])]["version"] = "2.0.0"
        elif mode == "schema_hash":
            self.schemas[("uniform_api", record["source_key"], record["code"])]["inputs"] = [
                {"key": "changed", "type": "string", "required": True}
            ]
        else:
            SpaceOpenPluginAvailability.objects.filter(
                space_id=self.space_id, source_key=record["source_key"], plugin_id=record["code"]
            ).update(enabled=False)
        cache.clear()


class GoldenToolCaller:
    """Observe Tool selection outside an otherwise unmodified production Facade."""

    def __init__(self):
        self.facade = HarnessFacade()
        self.calls = []

    def call(self, tool, context, request):
        self.calls.append(tool)
        return getattr(self.facade, tool)(context, request)

    def call_route(self, tool, space_id, request):
        """Exercise real routing, permission, context and transport for forged identity cases."""
        self.calls.append(tool)
        path = "/apigw/space/{}/harness/{}/".format(space_id, tool)
        api_request = APIRequestFactory().post(path, request, format="json", HTTP_X_REQUEST_ID="golden-forged")
        api_request.app = SimpleNamespace(bk_app_code="golden-foreign", verified=True)
        force_authenticate(api_request, user=SimpleNamespace(username="golden-actor", is_authenticated=True))
        response = resolve(path).func(api_request, space_id=str(space_id))
        assert response.status_code == 200
        return response.data


def _manifest():
    """Use no override authority beyond the current provider snapshot."""
    return {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "none"},
        "capabilities": [],
    }


def _context(**overrides):
    """Keep Golden execution free of a real space, token, or credential."""
    values = {
        "platform_key": "golden-platform",
        "platform_app": "golden-app",
        "actor": "golden-actor",
        "space_id": 1,
        "scope_type": "project",
        "scope_value": "golden",
        "target_environment": "test",
        "policy_version": "golden-policy",
        "mcp_contract_version": "1.0.0",
        "correlation_id": "golden",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


def _workflow_request(capability, schema, valid, idempotency_key):
    """Build the closed public validation DTO from the actual selected capability."""
    request = {
        "intent_spec": {"goal": "golden"},
        "a2flow": {
            "version": "2.0",
            "name": "golden",
            "nodes": [
                {
                    "id": "node_1",
                    "name": capability.code,
                    "code": capability.code,
                    "plugin_type": capability.plugin_type,
                    "data": {schema["inputs"][0]["key"]: "value"} if valid else {},
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": capability.capability_ref,
                "schema_hash": capability.schema_hash,
                "credential_ref": None,
            }
        ],
        "idempotency_key": idempotency_key,
        "client_context": {},
    }
    return request


def _selected_snapshot(case):
    """Pin each selected path to a real provider identity before observing it."""
    group = case["group"]
    if group == "positive_selection":
        return dict(case["registry_snapshot"])
    if group == "schema_validation_error":
        return {
            "plugin_type": "component",
            "source_key": None,
            "code": "{}_invalid".format(case["query"].replace(" ", "_")),
            "version": "1.0.0",
            "input_key": case["registry_snapshot"]["input_key"],
        }
    if group == "schema_drift":
        mode = case["registry_snapshot"]["drift"]
        if mode == "version":
            return {
                "plugin_type": "component",
                "source_key": None,
                "code": "drift_version",
                "version": "1.0.0",
                "input_key": "host",
            }
        if mode == "schema_hash":
            return {
                "plugin_type": "uniform_api",
                "source_key": "golden-v4",
                "code": "drift_schema",
                "version": "1.0.0",
                "input_key": "region",
            }
        return {
            "plugin_type": "uniform_api",
            "source_key": "golden-revoked",
            "code": "drift_revoked",
            "version": "1.0.0",
            "input_key": "cluster",
        }
    if group == "idempotent_draft_retry":
        return {
            "draft-retry-component": {
                "plugin_type": "component",
                "source_key": None,
                "code": "restart_host",
                "version": "1.0.0",
                "input_key": "host",
            },
            "draft-retry-remote": {
                "plugin_type": "remote_plugin",
                "source_key": None,
                "code": "probe_endpoint",
                "version": "3.2.0",
                "input_key": "endpoint",
            },
            "draft-retry-uniform": {
                "plugin_type": "uniform_api",
                "source_key": "v4-region",
                "code": "inspect_region",
                "version": "4.0.0",
                "input_key": "region",
            },
        }[case["id"]]
    return {
        "forged-space-wins": {
            "plugin_type": "component",
            "source_key": None,
            "code": "restart_host",
            "version": "1.0.0",
            "input_key": "host",
        },
        "forged-environment-wins": {
            "plugin_type": "uniform_api",
            "source_key": "v4-region",
            "code": "inspect_region",
            "version": "4.0.0",
            "input_key": "region",
        },
    }[case["id"]]


def run_golden_case(case):
    """Execute and query P0 public service effects; fixture data is never used as observation."""
    group = case["group"]
    if group in {"ambiguous_requires_clarification", "zero_candidate"}:
        snapshot = {
            "plugin_type": "component",
            "source_key": None,
            "code": case["query"].replace(" ", "_"),
            "version": "1.0.0",
            "input_key": case["registry_snapshot"].get("input_key", "value"),
        }
        candidates = 2 if group == "ambiguous_requires_clarification" else 0
        with GoldenCatalog(snapshot, candidates=candidates) as catalog:
            caller = GoldenToolCaller()
            response = caller.call("search_workflow_capabilities", _context(), {"query": case["query"]})
            errors = response["errors"]
            cards = response["artifact_refs"][0]["payload"]
            return GoldenObservation(
                caller.calls,
                "NEEDS_CLARIFICATION" if errors else "NEEDS_RECOVERY",
                None,
                set(),
                [card["capability_ref"] for card in cards],
            )

    snapshot = _selected_snapshot(case)
    with GoldenCatalog(snapshot) as catalog:
        caller = GoldenToolCaller()
        context = _context()
        search_query = snapshot["code"].replace("_", " ") if group == "schema_drift" else case["query"]
        search = caller.call("search_workflow_capabilities", context, {"query": search_query})
        cards = search["artifact_refs"][0]["payload"]
        if search["errors"] or len(cards) != 1:
            return GoldenObservation(
                caller.calls,
                "NEEDS_CLARIFICATION" if search["errors"] else "NEEDS_RECOVERY",
                None,
                set(),
                [card["capability_ref"] for card in cards],
            )
        card = cards[0]
        schema_response = caller.call(
            "get_plugin_schema",
            context,
            {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
        )
        assert schema_response["ok"] is True
        schema = schema_response["artifact_refs"][0]["payload"]
        reference = decode_capability_ref(card["capability_ref"])
        selected = SimpleNamespace(
            capability_ref=card["capability_ref"],
            plugin_type=card["plugin_type"],
            source_key=reference.source_key,
            code=reference.code,
            resolved_version=schema["resolved_version"],
            schema_hash=schema["schema_hash"],
        )
        observed_capability = {
            "capability_ref": selected.capability_ref,
            "plugin_type": selected.plugin_type,
            "source_key": selected.source_key,
            "code": selected.code,
            "resolved_version": selected.resolved_version,
            "schema_hash": selected.schema_hash,
        }

        if group == "schema_drift":
            catalog.drift(case["registry_snapshot"]["drift"])
            drifted = caller.call(
                "get_plugin_schema",
                context,
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
            assert drifted["errors"][0]["code"] in {"SCHEMA_DRIFT", "CAPABILITY_FORBIDDEN"}
            final = "SCHEMA_DRIFT" if drifted["errors"][0]["code"] == "SCHEMA_DRIFT" else "PERMISSION_DENIED"
            return GoldenObservation(caller.calls, final, observed_capability, set())

        response = caller.call(
            "validate_workflow",
            context,
            _workflow_request(selected, schema, group != "schema_validation_error", case["id"]),
        )

        if group == "positive_selection":
            assert response["ok"] is True, response
            revision = WorkflowPlanRevision.objects.get(pk=response["revision_id"])
            binding = CapabilityBinding.objects.get(revision=revision)
            report = ValidationReport.objects.get(run=revision.run, revision=revision)
            assert binding.capability_ref == selected.capability_ref
            assert binding.schema_hash == selected.schema_hash
            assert report.result["pipeline_tree_hash"]
            return GoldenObservation(caller.calls, revision.run.status, observed_capability, set())

        if group == "schema_validation_error":
            assert response["ok"] is False, response
            run = HarnessRun.objects.get(run_id=response["run_id"])
            report = ValidationReport.objects.get(run=run, revision=None)
            assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
            assert report.errors == response["errors"]
            return GoldenObservation(caller.calls, run.status, observed_capability, set())

        if group == "idempotent_draft_retry":
            accepted = response
            assert accepted["ok"] is True, accepted
            request = {
                "run_id": accepted["run_id"],
                "revision_id": accepted["revision_id"],
                "plan_hash": accepted["plan_hash"],
                "idempotency_key": "draft-{}".format(case["id"]),
            }
            first = caller.call("create_workflow_draft", context, request)
            second = caller.call("create_workflow_draft", context, request)
            assert first["ok"] is True, first
            template_id = first["artifact_refs"][0]["template_id"]
            assert first == second
            assert Template.objects.filter(pk=template_id).count() == 1
            assert TemplateSnapshot.objects.filter(template_id=template_id, draft=True).count() == 1
            assert (
                HarnessIdempotencyRecord.objects.filter(
                    tool_name="create_workflow_draft", resource_reference=str(template_id), status="COMPLETED"
                ).count()
                == 1
            )
            run = HarnessRun.objects.get(run_id=accepted["run_id"])
            draft_artifacts = [
                artifact
                for artifact in run.artifact_references
                if isinstance(artifact, dict) and artifact.get("type") == "harness_draft"
            ]
            assert len(draft_artifacts) == 1
            assert draft_artifacts[0]["template_id"] == template_id
            return GoldenObservation(caller.calls, run.status, observed_capability, {"draft"})

        accepted = response
        assert accepted["ok"] is True, accepted
        foreign_space = Space.objects.create(
            name="Golden foreign {}".format(case["id"]),
            app_code="golden-owned-foreign",
            platform_url="https://golden.invalid",
            creator="foreign-owner",
            updated_by="foreign-owner",
        )
        draft_request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "forged-{}".format(case["id"]),
        }
        forged_field = case["registry_snapshot"]["forged"]
        draft_request[forged_field] = context.space_id if forged_field == "space_id" else context.target_environment
        denied = caller.call_route(
            "create_workflow_draft",
            foreign_space.id,
            draft_request,
        )
        assert denied["errors"][0]["category"] == "PERMISSION"
        return GoldenObservation(caller.calls, "PERMISSION_DENIED", observed_capability, set())
