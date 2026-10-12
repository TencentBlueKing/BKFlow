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
import json

import pytest

from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import decode_capability_ref
from bkflow.harness.services.catalog import CatalogPaginationError
from bkflow.harness.services.projection import (
    CapabilityProjection,
    CapabilityProjectionError,
    validate_manifest,
)


class FixturePluginSchemaService:
    """A permission-filtered registry fixture with observable exact schema access."""

    def __init__(self, plugins, schemas, global_identities=None):
        self.plugins = plugins
        self.schemas = schemas
        self.schema_calls = []
        self.schema_kwargs = []
        self.global_identities = global_identities or {
            (item["plugin_type"], item.get("source_key"), item["code"]) for item in plugins
        }

    def list_plugins(self, plugin_source=None, limit=100, offset=0, **kwargs):
        filtered = [item for item in self.plugins if not plugin_source or item.get("plugin_source") == plugin_source]
        return filtered[offset : offset + limit], len(filtered)

    def get_plugin_schema(self, code, version=None, plugin_type=None, source_key=None, **kwargs):
        self.schema_calls.append((code, version, plugin_type, source_key))
        self.schema_kwargs.append(kwargs)
        return self.schemas[(plugin_type, source_key, code)]

    def manifest_identity_exists(self, plugin_type, source_key, code):
        return (plugin_type, source_key, code) in self.global_identities


@pytest.fixture
def registry():
    """Provide a governed registry snapshot."""
    plugins = [
        {
            "code": "restart_service",
            "name": "重启服务",
            "plugin_type": "component",
            "version": "1.0.0",
            "description": "重启目标主机上的服务",
            "access_token": "must-not-leak",
        },
        {
            "code": "restart_database",
            "name": "重启数据库",
            "plugin_type": "component",
            "version": "1.0.0",
            "description": "重启数据库服务",
            "secret": "must-not-leak",
        },
        {
            "code": "retired_plugin",
            "name": "旧服务",
            "plugin_type": "remote_plugin",
            "version": "2.0.0",
            "description": "不可用于新流程",
        },
    ]
    schemas = {
        ("component", None, "restart_service"): {"code": "restart_service", "inputs": [{"key": "host"}], "outputs": []},
        ("component", None, "restart_database"): {
            "code": "restart_database",
            "inputs": [{"key": "host"}],
            "outputs": [],
        },
        ("remote_plugin", None, "retired_plugin"): {"code": "retired_plugin", "inputs": [], "outputs": []},
    }
    return FixturePluginSchemaService(plugins, schemas)


@pytest.fixture
def manifest():
    """Provide lifecycle and searchable metadata without runtime authority."""
    return {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [
            {
                "plugin_type": "component",
                "source_key": None,
                "code": "restart_service",
                "aliases": ["restart"],
                "tags": ["运维"],
                "use_cases": ["服务重启"],
                "lifecycle": "VERIFIED",
                "risk_level": "L1",
                "side_effects": "restart",
            },
            {
                "plugin_type": "component",
                "source_key": None,
                "code": "restart_database",
                "aliases": ["restart-db"],
                "tags": ["运维"],
                "use_cases": ["数据库重启"],
                "lifecycle": "PUBLISHED",
                "risk_level": "L2",
                "side_effects": "restart",
            },
            {"plugin_type": "remote_plugin", "source_key": None, "code": "retired_plugin", "lifecycle": "RETIRED"},
        ],
    }


def test_projection_returns_only_allowlisted_lightweight_cards(registry, manifest):
    """Changing a registry response to expose a secret must not expose it to the agent."""
    result = CapabilityProjection(registry, manifest=manifest).search("restart")

    card = result["capabilities"][0]
    assert set(card) == {
        "capability_ref",
        "display_name",
        "summary",
        "plugin_type",
        "resolved_version",
        "schema_hash",
        "lifecycle",
        "risk_level",
        "side_effects",
        "required_credentials",
        "matched_terms",
        "score",
    }
    assert card["display_name"] == "重启服务"
    assert card["matched_terms"] == ["restart"]
    assert "inputs" not in json.dumps(result, ensure_ascii=False)
    assert "must-not-leak" not in json.dumps(result, ensure_ascii=False)
    assert registry.schema_calls == [
        ("restart_service", "1.0.0", "component", None),
        ("restart_database", "1.0.0", "component", None),
    ]


def test_projection_matches_chinese_terms_and_keeps_lifecycle_governance(registry, manifest):
    """Changing lifecycle filtering would leak retired capabilities into new generation."""
    result = CapabilityProjection(registry, manifest=manifest).search("重启")

    assert [card["display_name"] for card in result["capabilities"]] == ["重启数据库", "重启服务"]
    assert all(card["lifecycle"] in {"VERIFIED", "PUBLISHED"} for card in result["capabilities"])


def test_projection_returns_clarification_for_equal_best_candidates(registry, manifest):
    """Changing equal-best handling would let an agent select an arbitrary capability."""
    result = CapabilityProjection(registry, manifest=manifest).search("运维")

    assert result["errors"] == [{"code": "AMBIGUOUS_CAPABILITY", "retryable": True}]
    assert result["next_actions"] == [{"action": "clarify_capability"}]
    assert [card["display_name"] for card in result["capabilities"]] == ["重启数据库", "重启服务"]


def test_projection_keeps_empty_authorized_catalog_empty_without_fallback(manifest):
    """Changing an empty catalog to use an unrestricted registry would leak cross-space plugins."""
    global_identities = {(item["plugin_type"], item["source_key"], item["code"]) for item in manifest["capabilities"]}
    empty_registry = FixturePluginSchemaService([], {}, global_identities=global_identities)

    result = CapabilityProjection(empty_registry, manifest=manifest).search("restart")

    assert result == {"capabilities": [], "errors": [], "next_actions": []}
    assert empty_registry.schema_calls == []


def test_projection_uses_stable_identity_for_equal_score_ties(registry, manifest):
    """Changing the tie-breaker would make equal registry snapshots nondeterministic."""
    projection = CapabilityProjection(registry, manifest=manifest)

    first = projection.search("运维")
    second = projection.search("运维")

    first_json = json.dumps(first, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    second_json = json.dumps(second, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    assert first_json == second_json


def test_projection_rejects_top_k_above_p0_limit(registry, manifest):
    """Changing the top-k limit would let unbounded catalog data enter model context."""
    with pytest.raises(CapabilityProjectionError, match="top_k"):
        CapabilityProjection(registry, manifest=manifest).search("restart", top_k=21)


def test_projection_fetches_schema_only_for_ranked_top_k_candidates():
    """Fetching schemas before ranking would let a large authorized catalog exhaust provider capacity."""
    plugins = [
        {
            "plugin_type": "component",
            "source_key": None,
            "code": "maintenance-{:02d}".format(index),
            "name": "Maintenance {:02d}".format(index),
            "version": "1.0.0",
            "description": "maintenance operation",
        }
        for index in range(25)
    ]
    schemas = {("component", None, plugin["code"]): {"inputs": [{"key": "host"}], "outputs": []} for plugin in plugins}
    registry = FixturePluginSchemaService(plugins, schemas)

    result = CapabilityProjection(registry).search("maintenance", top_k=2)

    assert [card["display_name"] for card in result["capabilities"]] == ["Maintenance 00", "Maintenance 01"]
    assert registry.schema_calls == [
        ("maintenance-00", "1.0.0", "component", None),
        ("maintenance-01", "1.0.0", "component", None),
    ]


def test_projection_returns_retryable_candidate_error_when_ranked_schema_is_unavailable():
    """Swallowing a schema-provider failure as no result hides an actionable governed capability failure."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "restart_service",
        "name": "Restart Service",
        "version": "1.0.0",
        "description": "restart operation",
    }
    registry = FixturePluginSchemaService([plugin], {})

    result = CapabilityProjection(registry).search("restart")

    assert result["capabilities"] == []
    assert result["errors"] == [
        {
            "code": "CAPABILITY_SCHEMA_UNAVAILABLE",
            "retryable": True,
            "candidate": {"diagnostic_ref": "sha256:84b70c4b58569be9"},
        }
    ]


def test_projection_keeps_partial_schema_failure_visible_without_fetching_lower_ranked_candidates():
    """Falling through to lower-ranked schemas after failure would exceed the declared top-k provider budget."""
    plugins = [
        {
            "plugin_type": "component",
            "source_key": None,
            "code": "restart-{}".format(index),
            "name": "Restart {}".format(index),
            "version": "1.0.0",
        }
        for index in range(3)
    ]
    registry = FixturePluginSchemaService(
        plugins,
        {("component", None, "restart-1"): {"inputs": [], "outputs": []}},
    )

    result = CapabilityProjection(registry).search("restart", top_k=2)

    assert [card["display_name"] for card in result["capabilities"]] == ["Restart 1"]
    assert result["errors"][0]["code"] == "AMBIGUOUS_CAPABILITY"
    assert result["errors"][1]["candidate"]["diagnostic_ref"].startswith("sha256:")
    assert registry.schema_calls == [
        ("restart-0", "1.0.0", "component", None),
        ("restart-1", "1.0.0", "component", None),
    ]


@pytest.mark.parametrize("query", ("restart service", "restart_service", "restart-service"))
def test_projection_normalizes_latin_query_and_catalog_fields_identically(query):
    """Only normalizing the query would make the same Latin capability undiscoverable by separators."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "restart_service",
        "name": "Restart Service",
        "version": "1.0.0",
        "description": "restart operation",
    }
    registry = FixturePluginSchemaService(
        [plugin], {("component", None, "restart_service"): {"inputs": [], "outputs": []}}
    )

    result = CapabilityProjection(registry).search(query)

    assert [card["display_name"] for card in result["capabilities"]] == ["Restart Service"]


def test_projection_deduplicates_repeated_search_terms_before_ranking():
    """Repeating a term must not let a caller manipulate deterministic capability ranking."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "restart_service",
        "name": "Restart Service",
        "version": "1.0.0",
    }
    registry = FixturePluginSchemaService(
        [plugin], {("component", None, "restart_service"): {"inputs": [], "outputs": []}}
    )

    result = CapabilityProjection(registry).search("restart restart")

    assert result["capabilities"][0]["matched_terms"] == ["restart"]
    assert result["capabilities"][0]["score"] == 80


def test_projection_rejects_a_misspelled_retired_override_before_catalog_projection():
    """Ignoring an unknown RETIRED override can accidentally publish the dangerous intended capability by default."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "dangerous_delete",
        "name": "Dangerous Delete",
        "version": "1.0.0",
    }
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [
            {"plugin_type": "component", "source_key": None, "code": "dangerous_deleet", "lifecycle": "RETIRED"}
        ],
    }
    registry = FixturePluginSchemaService(
        [plugin], {("component", None, "dangerous_delete"): {"inputs": [], "outputs": []}}
    )

    with pytest.raises(CapabilityProjectionError, match="identity"):
        CapabilityProjection(registry, manifest=manifest).search("dangerous")


def test_projection_hides_globally_known_override_absent_from_current_authorized_space():
    """A globally valid override outside this space must not be treated as a typo or emitted without current ACL."""
    visible = {
        "plugin_type": "component",
        "source_key": None,
        "code": "safe_restart",
        "name": "Safe Restart",
        "version": "1.0.0",
    }
    absent_identity = ("uniform_api", "other-space-source", "global_only")
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [
            {
                "plugin_type": "uniform_api",
                "source_key": "other-space-source",
                "code": "global_only",
                "lifecycle": "RETIRED",
            }
        ],
    }
    registry = FixturePluginSchemaService(
        [visible],
        {("component", None, "safe_restart"): {"inputs": [], "outputs": []}},
        global_identities={absent_identity},
    )

    result = CapabilityProjection(registry, manifest=manifest).search("restart")

    assert [card["display_name"] for card in result["capabilities"]] == ["Safe Restart"]


@pytest.mark.parametrize(
    "case",
    ("side_effects", "capabilities", "aliases"),
)
def test_manifest_rejects_model_context_bounds(case):
    """Unbounded manifest text or lists would let repository data overflow model-facing capability cards."""
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [{"plugin_type": "component", "source_key": None, "code": "safe"}],
    }
    if case == "side_effects":
        manifest["defaults"]["side_effects"] = "副" * 241
    elif case == "capabilities":
        manifest["capabilities"] = [
            {"plugin_type": "component", "source_key": None, "code": "cap-{}".format(index)} for index in range(1001)
        ]
    else:
        manifest["capabilities"][0]["aliases"] = ["tag"] * 21

    with pytest.raises(CapabilityProjectionError):
        validate_manifest(manifest)


def test_projection_rejects_multibyte_query_above_bound():
    """Counting only ASCII query length would leave a large model-facing multibyte request unbounded."""
    with pytest.raises(CapabilityProjectionError):
        CapabilityProjection(FixturePluginSchemaService([], {})).search("查" * 257)


def test_projection_bounds_hostile_registry_text_and_never_returns_raw_identity():
    """A hostile source value must not reach regex/lowercase work or a model-facing error."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "x" * 100000,
        "name": "restart",
        "version": "1.0.0",
    }
    registry = FixturePluginSchemaService([plugin], {})

    with pytest.raises(CatalogPaginationError, match="identity"):
        CapabilityProjection(registry).search("restart")


def test_projection_reports_invalid_selected_identity_with_bounded_opaque_diagnostic():
    """Identity validation failures must be typed without echoing attacker-controlled fields."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "valid_code",
        "name": "restart",
        "version": "v" * 65,
    }
    registry = FixturePluginSchemaService([plugin], {("component", None, "valid_code"): {"inputs": [], "outputs": []}})

    result = CapabilityProjection(registry).search("restart")

    assert result["errors"][0]["code"] == "CAPABILITY_IDENTITY_INVALID"
    assert result["errors"][0]["retryable"] is False
    assert result["errors"][0]["candidate"]["diagnostic_ref"].startswith("sha256:")
    assert "valid_code" not in str(result["errors"])


@pytest.mark.parametrize("count", (2, 3))
def test_projection_reports_ambiguity_before_top_k_slice_for_equal_best_candidates(count):
    """A top_k=1 response must still request clarification for every equal-best candidate set."""
    plugins = [
        {"plugin_type": "component", "source_key": None, "code": "restart-{}".format(index), "name": "restart"}
        for index in range(count)
    ]
    schemas = {("component", None, item["code"]): {"inputs": [], "outputs": []} for item in plugins}

    result = CapabilityProjection(FixturePluginSchemaService(plugins, schemas)).search("restart", top_k=1)

    assert len(result["capabilities"]) == 1
    assert result["errors"][0] == {"code": "AMBIGUOUS_CAPABILITY", "retryable": True}
    assert result["next_actions"] == [{"action": "clarify_capability"}]


def test_projection_accepts_legal_long_manifest_and_registry_tokens_without_unbounded_matching():
    """Legal source text is bounded before tokenization but remains usable for ordinary matching."""
    plugin = {
        "plugin_type": "component",
        "source_key": None,
        "code": "restart_service",
        "name": "restart",
        "description": "d" * 240,
    }
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [
            {"plugin_type": "component", "source_key": None, "code": "restart_service", "aliases": ["a" * 240]}
        ],
    }
    registry = FixturePluginSchemaService(
        [plugin], {("component", None, "restart_service"): {"inputs": [], "outputs": []}}
    )

    result = CapabilityProjection(registry, manifest=manifest).search("restart")

    assert [card["display_name"] for card in result["capabilities"]] == ["restart"]


def test_projection_rejects_unknown_manifest_identity_during_constructor_before_empty_search():
    """Manifest reconciliation is a startup boundary, not a side effect of a nonempty query."""
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [{"plugin_type": "component", "source_key": None, "code": "unknown"}],
    }

    with pytest.raises(CapabilityProjectionError, match="identity"):
        CapabilityProjection(FixturePluginSchemaService([], {}), manifest=manifest)


@pytest.mark.parametrize("field", ("aliases", "side_effects"))
def test_manifest_translates_lone_surrogates_to_projection_error(field):
    """Repository metadata with an unencodable string must fail closed at manifest validation."""
    manifest = {
        "manifest_version": "p0-v1",
        "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
        "capabilities": [{"plugin_type": "component", "source_key": None, "code": "safe"}],
    }
    if field == "aliases":
        manifest["capabilities"][0]["aliases"] = ["bad\ud800"]
    else:
        manifest["defaults"]["side_effects"] = "bad\ud800"

    with pytest.raises(CapabilityProjectionError):
        validate_manifest(manifest)


@pytest.mark.parametrize("field", ("name", "description"))
def test_projection_rejects_surrogate_registry_text_without_raw_unicode_error(field):
    """Remote registry text must be bounded/validated before any normalization work."""
    plugin = {"plugin_type": "component", "source_key": None, "code": "safe", "name": "restart", "description": ""}
    plugin[field] = "bad\ud800"
    registry = FixturePluginSchemaService([plugin], {("component", None, "safe"): {"inputs": [], "outputs": []}})

    with pytest.raises(CapabilityProjectionError):
        CapabilityProjection(registry).search("restart")


@pytest.mark.parametrize("field", ("name", "description"))
def test_projection_bounds_100k_registry_text_before_model_context(field):
    """Hostile registry text is truncated before ranking and card construction."""
    plugin = {"plugin_type": "component", "source_key": None, "code": "safe", "name": "restart", "description": ""}
    plugin[field] = "restart " + "x" * 100000
    registry = FixturePluginSchemaService([plugin], {("component", None, "safe"): {"inputs": [], "outputs": []}})

    result = CapabilityProjection(registry).search("restart")

    assert len(result["capabilities"][0]["display_name"]) <= 240
    assert len(result["capabilities"][0]["summary"]) <= 240


def test_projection_uses_exact_source_schema_for_legacy_and_same_code_v4_candidates():
    """A legacy None-source card must not load the public wildcard-selected V4 schema."""
    plugins = [
        {"plugin_type": "uniform_api", "source_key": None, "code": "shared", "name": "restart", "version": "1"},
        {
            "plugin_type": "uniform_api",
            "source_key": "legacy_uniform_api",
            "code": "shared",
            "name": "restart",
            "version": "1",
        },
    ]
    legacy_schema = {"inputs": [{"key": "legacy"}], "outputs": []}
    v4_schema = {"inputs": [{"key": "v4"}], "outputs": []}
    registry = FixturePluginSchemaService(
        plugins,
        {
            ("uniform_api", None, "shared"): legacy_schema,
            ("uniform_api", "legacy_uniform_api", "shared"): v4_schema,
        },
    )

    result = CapabilityProjection(registry).search("restart", top_k=2)
    cards = {decode_capability_ref(card["capability_ref"]).source_key: card for card in result["capabilities"]}

    assert cards[None]["schema_hash"] == schema_hash(legacy_schema)
    assert cards["legacy_uniform_api"]["schema_hash"] == schema_hash(v4_schema)
    assert registry.schema_kwargs == [{"exact_source": True}, {"exact_source": True}]
