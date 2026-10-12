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
import pytest

from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import UNVERSIONED, encode_capability_ref
from bkflow.harness.services.resolver import (
    CapabilityResolutionError,
    CapabilityResolver,
    ProviderInfrastructureError,
    SchemaDriftError,
)
from bkflow.plugin.services.plugin_schema_service import PluginSchemaInfrastructureError


class FixturePluginSchemaService:
    """An ACL-filtered registry fake that only returns authorized current entries."""

    def __init__(self, plugins, schemas, global_identities=None):
        self.plugins = plugins
        self.schemas = schemas
        self.schema_calls = []
        self.refresh_values = []
        self.list_refresh_values = []
        self.global_identities = global_identities or {
            (item["plugin_type"], item.get("source_key"), item["code"]) for item in plugins
        }

    def list_plugins(self, limit=100, offset=0, **kwargs):
        self.list_refresh_values.append(kwargs.get("refresh", False))
        return self.plugins[offset : offset + limit], len(self.plugins)

    def get_plugin_schema(self, code, version=None, plugin_type=None, source_key=None, **kwargs):
        self.schema_calls.append((code, version, plugin_type, source_key))
        self.refresh_values.append(kwargs.get("refresh", False))
        schema = dict(self.schemas[(plugin_type, source_key, code)])
        if kwargs.get("include_conversion_metadata") and "conversion_metadata" not in schema:
            resolved_version = schema.get("resolved_version") or schema.get("version") or UNVERSIONED
            if plugin_type == "component":
                schema["conversion_metadata"] = {
                    "kind": "component",
                    "wrapper_code": code,
                    "wrapper_version": resolved_version,
                }
            elif plugin_type == "remote_plugin":
                schema["conversion_metadata"] = {
                    "kind": "remote_plugin",
                    "wrapper_code": "remote_plugin",
                    "wrapper_version": "1.0.0",
                    "remote_plugin_version": resolved_version,
                }
            else:
                schema["conversion_metadata"] = {
                    "kind": "uniform_api",
                    "wrapper_code": "uniform_api",
                    "wrapper_version": "4.0.0",
                    "source_key": source_key,
                    "plugin_id": code,
                    "plugin_version": resolved_version,
                    "url": "https://fixture.invalid/{}".format(code),
                    "method": "POST",
                    "credential_key": None,
                }
        return schema

    def manifest_identity_exists(self, plugin_type, source_key, code):
        return (plugin_type, source_key, code) in self.global_identities


@pytest.fixture
def manifest():
    """Provide one governed capability override."""
    return {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [
            {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "risk_level": "L2"},
        ],
    }


def test_resolver_rechecks_access_and_returns_the_current_exact_schema(manifest):
    """Removing a catalog entry after search must prevent a stale reference from resolving."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}
    schema = {"code": "restart", "version": "1.0.0", "inputs": [{"key": "host"}], "outputs": []}
    registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    resolved = CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert resolved.capability_ref == capability_ref
    assert resolved.plugin_type == "uniform_api"
    assert resolved.code == "restart"
    assert resolved.source_key == "source-a"
    assert resolved.resolved_version == "1.0.0"
    assert resolved.schema_hash == schema_hash({"inputs": [{"key": "host"}], "outputs": []})
    assert resolved.schema == {"inputs": [{"key": "host"}], "outputs": []}
    assert resolved.risk_level == "L2"
    assert registry.schema_calls == [("restart", "1.0.0", "uniform_api", "source-a")]
    assert registry.refresh_values == [True]
    assert registry.list_refresh_values == [True]


def test_resolver_keeps_legacy_none_source_distinct_from_v4_source_key_collision():
    """A legacy ref must not resolve a V4 row even when a V4 source uses the former sentinel name."""
    plugins = [
        {"plugin_type": "uniform_api", "source_key": None, "code": "shared", "version": "1"},
        {"plugin_type": "uniform_api", "source_key": "legacy_uniform_api", "code": "shared", "version": "1"},
    ]
    schemas = {
        ("uniform_api", None, "shared"): {"version": "1", "inputs": [{"key": "legacy"}], "outputs": []},
        ("uniform_api", "legacy_uniform_api", "shared"): {"version": "1", "inputs": [{"key": "v4"}], "outputs": []},
    }
    registry = FixturePluginSchemaService(plugins, schemas)

    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [],
    }
    capability_ref = encode_capability_ref("uniform_api", None, "shared", "1")
    resolved = CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert resolved.source_key is None
    assert resolved.schema["inputs"] == [{"key": "legacy"}]


def test_resolver_replays_all_authorized_catalog_pages_before_exact_match(manifest):
    """Using a presentation page for authorization would deny a valid capability beyond the first 100 rows."""
    plugins = [
        {"plugin_type": "component", "source_key": None, "code": "cap-{}".format(index), "version": "1.0.0"}
        for index in range(200)
    ]
    plugins.append({"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"})
    schema = {"code": "restart", "version": "1.0.0", "inputs": [], "outputs": []}
    registry = FixturePluginSchemaService(plugins, {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    resolved = CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert resolved.code == "restart"
    assert registry.refresh_values == [True]


def test_resolver_rejects_a_reference_not_present_in_current_authorized_catalog(manifest):
    """Changing authorization rechecks would turn a revoked capability into an allowed action."""
    registry = FixturePluginSchemaService([], {}, {("uniform_api", "source-a", "restart")})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    with pytest.raises(CapabilityResolutionError, match="CAPABILITY_FORBIDDEN"):
        CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert registry.schema_calls == []


def test_resolver_rejects_version_or_schema_hash_drift_and_requires_search(manifest):
    """Changing the current version or IO schema must block a formerly selected reference."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}
    drifted_schema = {"code": "restart", "version": "2.0.0", "inputs": [{"key": "host"}], "outputs": []}
    registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): drifted_schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    with pytest.raises(SchemaDriftError) as error:
        CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert error.value.code == "SCHEMA_DRIFT"
    assert error.value.next_action == "search_workflow_capabilities"


def test_resolver_rejects_a_schema_hash_from_a_previous_search(manifest):
    """Changing expected schema hash handling would silently accept a changed parameter contract."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}
    schema = {"code": "restart", "version": "1.0.0", "inputs": [{"key": "host"}], "outputs": []}
    registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    with pytest.raises(SchemaDriftError, match="SCHEMA_DRIFT"):
        CapabilityResolver(registry, manifest=manifest).resolve(capability_ref, expected_schema_hash="0" * 64)


def test_resolver_uses_explicit_unversioned_sentinel_for_legacy_plugins(manifest):
    """Changing legacy handling would make unversioned records indistinguishable from latest."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": ""}
    schema = {"code": "restart", "version": "", "inputs": [], "outputs": []}
    registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", UNVERSIONED)

    resolved = CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)

    assert resolved.resolved_version == UNVERSIONED
    assert registry.schema_calls == [("restart", None, "uniform_api", "source-a")]


def test_resolver_rejects_raw_plugin_code_and_retired_lifecycle(manifest):
    """Changing opaque-reference or lifecycle gates would bypass capability governance."""
    registry = FixturePluginSchemaService([], {}, {("uniform_api", "source-a", "restart")})
    resolver = CapabilityResolver(registry, manifest=manifest)

    with pytest.raises(CapabilityResolutionError):
        resolver.resolve("restart")

    retired_manifest = dict(manifest, capabilities=[dict(manifest["capabilities"][0], lifecycle="RETIRED")])
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}
    schema = {"code": "restart", "version": "1.0.0", "inputs": [], "outputs": []}
    retired_registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")
    with pytest.raises(CapabilityResolutionError, match="CAPABILITY_FORBIDDEN"):
        CapabilityResolver(retired_registry, manifest=retired_manifest).resolve(capability_ref)


def test_resolver_rejects_provider_conversion_metadata_that_is_extra_or_not_the_exact_record(manifest):
    """Provider output must not be able to choose a different execution wrapper or V4 source."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}
    schema = {
        "version": "1.0.0",
        "inputs": [],
        "outputs": [],
        "conversion_metadata": {
            "kind": "uniform_api",
            "wrapper_code": "uniform_api",
            "wrapper_version": "4.0.0",
            "source_key": "other-source",
            "plugin_id": "restart",
            "plugin_version": "1.0.0",
            "url": "https://fixture.invalid/restart",
            "method": "POST",
            "credential_key": None,
            "provider_override": True,
        },
    }
    registry = FixturePluginSchemaService([plugin], {("uniform_api", "source-a", "restart"): schema})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    with pytest.raises(SchemaDriftError, match="SCHEMA_DRIFT"):
        CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)


def test_resolver_preserves_provider_outage_as_retryable_infrastructure(manifest):
    """A timeout/error is not evidence that the selected schema has drifted."""
    plugin = {"plugin_type": "uniform_api", "source_key": "source-a", "code": "restart", "version": "1.0.0"}

    class OutageRegistry(FixturePluginSchemaService):
        def get_plugin_schema(self, *args, **kwargs):
            raise PluginSchemaInfrastructureError("timeout")

    registry = OutageRegistry([plugin], {})
    capability_ref = encode_capability_ref("uniform_api", "source-a", "restart", "1.0.0")

    with pytest.raises(ProviderInfrastructureError, match="RETRYABLE_INFRA"):
        CapabilityResolver(registry, manifest=manifest).resolve(capability_ref)
