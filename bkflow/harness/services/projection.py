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
import re
from pathlib import Path

import yaml

from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import (
    IDENTITY_LIMITS,
    UNVERSIONED,
    CapabilityReferenceError,
    encode_capability_ref,
    validate_capability_identity,
)
from bkflow.harness.services.catalog import list_authorized_plugins

DEFAULT_TOP_K = 10
MAX_TOP_K = 20
ALLOWED_LIFECYCLES = frozenset(("VERIFIED", "PUBLISHED"))
LIFECYCLES = frozenset(("DRAFT", "VERIFIED", "PUBLISHED", "DEPRECATED", "RETIRED"))
RISK_LEVELS = frozenset(("L0", "L1", "L2", "L3"))
MANIFEST_VERSION = "p0-v1"
MANIFEST_DEFAULT_FIELDS = frozenset(("lifecycle", "risk_level", "side_effects"))
MANIFEST_CAPABILITY_FIELDS = frozenset(
    ("plugin_type", "source_key", "code", "aliases", "tags", "use_cases", "lifecycle", "risk_level", "side_effects")
)
SUMMARY_MAX_LENGTH = 240
MAX_MANIFEST_FILE_BYTES = 262144
MAX_MANIFEST_CAPABILITIES = 1000
MAX_MANIFEST_METADATA_ITEMS = 20
MAX_MANIFEST_TEXT_LENGTH = 240
MAX_QUERY_LENGTH = 256
MAX_QUERY_TERMS = 12
MAX_QUERY_TERM_LENGTH = 64
MAX_REGISTRY_TEXT_LENGTH = 240
MAX_REGISTRY_TEXT_BYTES = 960
MAX_REGISTRY_TOKENS = 20


class CapabilityProjectionError(ValueError):
    """Raised for invalid, unsafe, or unbounded capability projection input."""


def _utf8_text_length(value, field):
    """Return UTF-8 byte length while translating malformed text to the projection contract."""
    try:
        return len(value.encode("utf-8"))
    except UnicodeError as error:
        raise CapabilityProjectionError("{} is invalid".format(field)) from error


def reconcile_manifest_overrides(plugin_schema_service, overrides):
    """Fail closed unless every override has one authoritative global source identity.

    An identity that is globally known but absent from this service's current
    space/scope catalog remains valid metadata and is deliberately not emitted.
    """
    if not overrides:
        return
    identity_exists = getattr(plugin_schema_service, "manifest_identity_exists", None)
    if not callable(identity_exists):
        raise CapabilityProjectionError("capability manifest identity registry is unavailable")
    for plugin_type, source_key, code in sorted(overrides):
        if not identity_exists(plugin_type, source_key, code):
            raise CapabilityProjectionError("capability manifest identity is unknown")


def _validate_text_list(value, field):
    """Accept only a deterministic list of non-empty metadata strings."""
    if value is None:
        return []
    if (
        not isinstance(value, list)
        or len(value) > MAX_MANIFEST_METADATA_ITEMS
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > MAX_MANIFEST_TEXT_LENGTH
            or _utf8_text_length(item, "manifest {}".format(field)) > MAX_MANIFEST_TEXT_LENGTH * 4
            for item in value
        )
    ):
        raise CapabilityProjectionError("manifest {} is invalid".format(field))
    return sorted(set(value))


def _validate_lifecycle(value):
    """Validate one closed lifecycle value."""
    if value not in LIFECYCLES:
        raise CapabilityProjectionError("manifest lifecycle is invalid")
    return value


def _validate_risk_level(value):
    """Validate one closed risk level value."""
    if value not in RISK_LEVELS:
        raise CapabilityProjectionError("manifest risk level is invalid")
    return value


def validate_manifest(manifest):
    """Validate a non-sensitive metadata-only manifest and return a normalized copy."""
    if not isinstance(manifest, dict) or set(manifest) != {"manifest_version", "defaults", "capabilities"}:
        raise CapabilityProjectionError("capability manifest fields are invalid")
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise CapabilityProjectionError("capability manifest version is invalid")
    defaults = manifest["defaults"]
    if not isinstance(defaults, dict) or set(defaults) != MANIFEST_DEFAULT_FIELDS:
        raise CapabilityProjectionError("capability manifest defaults are invalid")
    normalized_defaults = {
        "lifecycle": _validate_lifecycle(defaults["lifecycle"]),
        "risk_level": _validate_risk_level(defaults["risk_level"]),
        "side_effects": defaults["side_effects"],
    }
    if (
        not isinstance(normalized_defaults["side_effects"], str)
        or not normalized_defaults["side_effects"]
        or len(normalized_defaults["side_effects"]) > MAX_MANIFEST_TEXT_LENGTH
        or _utf8_text_length(normalized_defaults["side_effects"], "manifest side effects")
        > MAX_MANIFEST_TEXT_LENGTH * 4
    ):
        raise CapabilityProjectionError("manifest side effects are invalid")
    capabilities = manifest["capabilities"]
    if not isinstance(capabilities, list) or len(capabilities) > MAX_MANIFEST_CAPABILITIES:
        raise CapabilityProjectionError("capability manifest capabilities are invalid")
    normalized_capabilities = []
    seen = set()
    for capability in capabilities:
        if not isinstance(capability, dict) or not set(capability).issubset(MANIFEST_CAPABILITY_FIELDS):
            raise CapabilityProjectionError("capability manifest entry is invalid")
        if not {"plugin_type", "source_key", "code"}.issubset(capability):
            raise CapabilityProjectionError("capability manifest identity is invalid")
        plugin_type = capability["plugin_type"]
        source_key = capability["source_key"]
        code = capability["code"]
        try:
            validate_capability_identity(plugin_type, source_key, code)
        except CapabilityReferenceError as error:
            raise CapabilityProjectionError("capability manifest identity is invalid") from error
        if plugin_type not in IDENTITY_LIMITS:
            raise CapabilityProjectionError("capability manifest identity is invalid")
        if plugin_type in {"component", "remote_plugin"} and source_key is not None:
            raise CapabilityProjectionError("capability manifest identity is invalid")
        if plugin_type == "uniform_api" and source_key is None:
            raise CapabilityProjectionError("capability manifest identity is invalid")
        identity = (plugin_type, source_key, code)
        if identity in seen:
            raise CapabilityProjectionError("capability manifest identity is duplicated")
        seen.add(identity)
        item = {
            "plugin_type": plugin_type,
            "source_key": source_key,
            "code": code,
            "aliases": _validate_text_list(capability.get("aliases"), "aliases"),
            "tags": _validate_text_list(capability.get("tags"), "tags"),
            "use_cases": _validate_text_list(capability.get("use_cases"), "use_cases"),
            "lifecycle": _validate_lifecycle(capability.get("lifecycle", normalized_defaults["lifecycle"])),
            "risk_level": _validate_risk_level(capability.get("risk_level", normalized_defaults["risk_level"])),
            "side_effects": capability.get("side_effects", normalized_defaults["side_effects"]),
        }
        if (
            not isinstance(item["side_effects"], str)
            or not item["side_effects"]
            or len(item["side_effects"]) > MAX_MANIFEST_TEXT_LENGTH
            or _utf8_text_length(item["side_effects"], "manifest side effects") > MAX_MANIFEST_TEXT_LENGTH * 4
        ):
            raise CapabilityProjectionError("manifest side effects are invalid")
        normalized_capabilities.append(item)
    return {"defaults": normalized_defaults, "capabilities": normalized_capabilities}


def load_manifest(path=None):
    """Load the repository-owned, metadata-only capability manifest safely."""
    manifest_path = (
        Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "capability_manifest_overrides.yaml"
    )
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_FILE_BYTES:
            raise CapabilityProjectionError("capability manifest is too large")
        with manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = yaml.safe_load(manifest_file)
    except (OSError, yaml.YAMLError) as error:
        raise CapabilityProjectionError("capability manifest is unavailable") from error
    return validate_manifest(manifest)


def _normalize_query(query):
    """Normalize a user search query to deterministic non-empty search terms."""
    if not isinstance(query, str) or len(query) > MAX_QUERY_LENGTH:
        raise CapabilityProjectionError("query is invalid")
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", query)]
    if len(terms) > MAX_QUERY_TERMS or any(len(term) > MAX_QUERY_TERM_LENGTH for term in terms):
        raise CapabilityProjectionError("query is invalid")
    return list(dict.fromkeys(terms))


def _searchable_tokens(value):
    """Tokenize registry and manifest Latin fields exactly as a user query is tokenized."""
    value = _bounded_registry_text(value)
    if value is None:
        return []
    return [
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", value)
        if len(term) <= MAX_QUERY_TERM_LENGTH
    ][:MAX_REGISTRY_TOKENS]


def _bounded_registry_text(value):
    """Bound untrusted registry text before normalization, regex, or lowercase work."""
    if not isinstance(value, str):
        return None
    if len(value) > MAX_REGISTRY_TEXT_LENGTH:
        value = value[:MAX_REGISTRY_TEXT_LENGTH]
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as error:
        raise CapabilityProjectionError("registry text is invalid") from error
    if len(encoded) > MAX_REGISTRY_TEXT_BYTES:
        value = encoded[:MAX_REGISTRY_TEXT_BYTES].decode("utf-8", "ignore")
    return value


def _diagnostic_ref(plugin):
    """Return a bounded opaque reference without reflecting hostile identities."""
    raw = repr((plugin.get("plugin_type"), plugin.get("source_key"), plugin.get("code"))).encode("utf-8", "replace")
    return "sha256:{}".format(hashlib.sha256(raw).hexdigest()[:16])


def _schema_payload(plugin_schema):
    """Keep the schema fingerprint limited to generator-visible IO schema facts."""
    return {"inputs": plugin_schema.get("inputs", []), "outputs": plugin_schema.get("outputs", [])}


class CapabilityProjection:
    """Project a trusted plugin registry into a bounded, governed search directory."""

    def __init__(self, plugin_schema_service, manifest=None):
        self.plugin_schema_service = plugin_schema_service
        normalized_manifest = validate_manifest(manifest) if manifest is not None else load_manifest()
        self.defaults = normalized_manifest["defaults"]
        self.overrides = {
            (item["plugin_type"], item["source_key"], item["code"]): item
            for item in normalized_manifest["capabilities"]
        }
        reconcile_manifest_overrides(self.plugin_schema_service, self.overrides)

    def _metadata(self, plugin):
        """Resolve only a manifest override matching the registry identity exactly."""
        identity = (plugin.get("plugin_type"), plugin.get("source_key"), plugin.get("code"))
        override = self.overrides.get(identity, {})
        return {
            "aliases": override.get("aliases", []),
            "tags": override.get("tags", []),
            "use_cases": override.get("use_cases", []),
            "lifecycle": override.get("lifecycle", self.defaults["lifecycle"]),
            "risk_level": override.get("risk_level", self.defaults["risk_level"]),
            "side_effects": override.get("side_effects", self.defaults["side_effects"]),
        }

    @staticmethod
    def _match_terms(query_terms, plugin, metadata):
        """Score exact Latin fields and Chinese substring matches without locale-dependent ranking."""
        fields = [plugin.get("name", ""), plugin.get("code", "")]
        fields += metadata["aliases"] + metadata["tags"] + metadata["use_cases"]
        normalized_fields = [field.lower() for field in (_bounded_registry_text(field) for field in fields) if field]
        field_tokens = {term for field in normalized_fields for term in _searchable_tokens(field)}
        matched_terms = []
        score = 0
        for term in query_terms:
            whole_exact = any(term == field for field in normalized_fields)
            token_exact = term in field_tokens
            is_chinese_term = any("\u4e00" <= char <= "\u9fff" for char in term)
            chinese_match = any(is_chinese_term and term in field for field in normalized_fields)
            if whole_exact or token_exact or chinese_match:
                matched_terms.append(term)
                score += 100 if whole_exact else 80 if token_exact else 50
        return score, matched_terms

    def search(self, query, top_k=DEFAULT_TOP_K, plugin_source=None):
        """Return cards from the already ACL/scope-filtered registry, never a fallback catalog."""
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1 or top_k > MAX_TOP_K:
            raise CapabilityProjectionError("top_k must be between 1 and {}".format(MAX_TOP_K))
        query_terms = _normalize_query(query)
        if not query_terms:
            return {"capabilities": [], "errors": [], "next_actions": []}
        plugins = list_authorized_plugins(self.plugin_schema_service, plugin_source=plugin_source)
        candidates = []
        for plugin in plugins:
            metadata = self._metadata(plugin)
            if metadata["lifecycle"] not in ALLOWED_LIFECYCLES:
                continue
            score, matched_terms = self._match_terms(query_terms, plugin, metadata)
            if not score:
                continue
            candidates.append((score, plugin, metadata, matched_terms))

        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1].get("plugin_type", ""),
                item[1].get("source_key") or "",
                item[1].get("code", ""),
            )
        )
        selected = candidates[:top_k]
        cards = []
        errors = []
        for score, plugin, metadata, matched_terms in selected:
            requested_version = plugin.get("resolved_version") or plugin.get("version") or None
            try:
                plugin_schema = self.plugin_schema_service.get_plugin_schema(
                    code=plugin["code"],
                    version=requested_version,
                    plugin_type=plugin["plugin_type"],
                    source_key=plugin.get("source_key"),
                    exact_source=True,
                )
            except Exception:
                errors.append(
                    {
                        "code": "CAPABILITY_SCHEMA_UNAVAILABLE",
                        "retryable": True,
                        "candidate": {
                            "diagnostic_ref": _diagnostic_ref(plugin),
                        },
                    }
                )
                continue
            resolved_version = (
                plugin_schema.get("resolved_version")
                or plugin_schema.get("version")
                or requested_version
                or UNVERSIONED
            )
            try:
                capability_ref = encode_capability_ref(
                    plugin_type=plugin["plugin_type"],
                    source_key=plugin.get("source_key"),
                    code=plugin["code"],
                    version=resolved_version,
                )
            except Exception:
                errors.append(
                    {
                        "code": "CAPABILITY_IDENTITY_INVALID",
                        "retryable": False,
                        "candidate": {
                            "diagnostic_ref": _diagnostic_ref(plugin),
                        },
                    }
                )
                continue
            cards.append(
                {
                    "capability_ref": capability_ref,
                    "display_name": (_bounded_registry_text(plugin.get("name")) or plugin["code"])[:SUMMARY_MAX_LENGTH],
                    "summary": (_bounded_registry_text(plugin.get("description")) or "")[:SUMMARY_MAX_LENGTH],
                    "plugin_type": plugin["plugin_type"],
                    "resolved_version": resolved_version,
                    "schema_hash": schema_hash(_schema_payload(plugin_schema)),
                    "lifecycle": metadata["lifecycle"],
                    "risk_level": metadata["risk_level"],
                    "side_effects": metadata["side_effects"],
                    "required_credentials": [],
                    "matched_terms": matched_terms,
                    "score": score,
                }
            )
        cards.sort(key=lambda card: (-card["score"], card["capability_ref"]))
        result = {"capabilities": cards, "errors": errors, "next_actions": []}
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            result["errors"].insert(0, {"code": "AMBIGUOUS_CAPABILITY", "retryable": True})
            result["next_actions"] = [{"action": "clarify_capability"}]
        return result


def search_workflow_capabilities(plugin_schema_service, query, top_k=DEFAULT_TOP_K, manifest=None, plugin_source=None):
    """Expose the governed capability-search operation without registering a new MCP Tool."""
    projection = CapabilityProjection(plugin_schema_service, manifest=manifest)
    return projection.search(query, top_k=top_k, plugin_source=plugin_source)
