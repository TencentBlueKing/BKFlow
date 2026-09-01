"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml

from bkflow.harness.constants import UNVERSIONED
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import AmbiguousCapability, HarnessUserInputError
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref

SEARCH_CARD_FIELDS = (
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
)
DEFAULT_TOP_K = 10
MAX_TOP_K = 20
EXACT_NAME_SCORE = 90
EXACT_ALIAS_SCORE = 85
EXACT_CODE_SCORE = 100
TOKEN_SCORE = 10
FORBIDDEN_MANIFEST_KEYS = {"space_id", "token", "secret", "credential", "access_token"}
DEFAULT_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "capability_manifest_overrides.yaml",
)

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9_]+", re.IGNORECASE)


@dataclass
class CapabilitySearchResult:
    """能力检索结果。"""

    ok: bool
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    next_actions: List[Dict[str, Any]] = field(default_factory=list)


def tokenize(text: str) -> Set[str]:
    """规范化查询和文档字段的 token。"""
    tokens = set()
    for part in _TOKEN_RE.findall((text or "").lower()):
        tokens.add(part)
        if re.search(r"[\u4e00-\u9fff]", part) and len(part) > 1:
            tokens.update(part)
    return tokens


def load_capability_manifest(path: Optional[str] = None) -> Dict[str, Any]:
    """加载并校验安全元数据覆盖清单。"""
    manifest_path = path or DEFAULT_MANIFEST_PATH
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}
    if manifest.get("manifest_version") != "p0-v1":
        raise ValueError("capability manifest_version must be p0-v1")
    defaults = manifest.get("defaults") or {}
    for key in FORBIDDEN_MANIFEST_KEYS:
        if key in defaults or key in manifest:
            raise ValueError("capability manifest contains forbidden key")
    for entry in manifest.get("capabilities") or []:
        if not isinstance(entry, dict) or FORBIDDEN_MANIFEST_KEYS.intersection(entry):
            raise ValueError("capability manifest entry is invalid")
    return manifest


def _visible_in_space(item: Dict[str, Any], space_id: int) -> bool:
    space_ids = item.get("space_ids")
    return not space_ids or space_id in space_ids


def _score(query: str, item: Dict[str, Any]) -> Tuple[int, List[str]]:
    query_norm = (query or "").strip().lower()
    name = str(item.get("name") or "")
    code = str(item.get("code") or "")
    aliases = [str(alias) for alias in (item.get("aliases") or [])]
    if query_norm == code.lower():
        return EXACT_CODE_SCORE, [code]
    if query_norm == name.lower():
        return EXACT_NAME_SCORE, [name]
    for alias in aliases:
        if query_norm == alias.lower():
            return EXACT_ALIAS_SCORE, [alias]

    documents = " ".join([name, code, *aliases, *(item.get("tags") or []), *(item.get("use_cases") or [])])
    query_tokens = tokenize(query)
    document_tokens = tokenize(documents)
    matched = sorted(query_tokens & document_tokens)
    return TOKEN_SCORE * len(matched), matched


def _identity(item: Dict[str, Any]):
    return (
        item.get("plugin_type") or "",
        item.get("source_key") or "",
        item.get("code") or "",
        item.get("version") or UNVERSIONED,
    )


def _to_card(item: Dict[str, Any], score: int, matched: List[str], manifest: Dict[str, Any]) -> Dict[str, Any]:
    defaults = manifest.get("defaults") or {}
    version = item.get("version") or UNVERSIONED
    schema = item.get("schema") or {}
    return {
        "capability_ref": encode_capability_ref(
            plugin_type=item["plugin_type"],
            source_key=item.get("source_key"),
            code=item["code"],
            version=version,
        ),
        "display_name": item.get("name") or item["code"],
        "summary": (item.get("use_cases") or [item.get("description") or ""])[0]
        if (item.get("use_cases") or item.get("description"))
        else "",
        "plugin_type": item["plugin_type"],
        "resolved_version": version,
        "schema_hash": schema_hash(schema),
        "lifecycle": item.get("lifecycle") or defaults.get("lifecycle") or "VERIFIED",
        "risk_level": item.get("risk_level") or defaults.get("risk_level") or "L1",
        "side_effects": item.get("side_effects") or defaults.get("side_effects") or "unknown",
        "required_credentials": item.get("required_credentials") or [],
        "matched_terms": matched,
        "score": score,
    }


def search_workflow_capabilities(
    *,
    context: TrustedHarnessContext,
    query: str,
    registry_snapshot: Iterable[Dict[str, Any]],
    top_k: int = DEFAULT_TOP_K,
    manifest: Optional[Dict[str, Any]] = None,
) -> CapabilitySearchResult:
    """在授权空间内检索业务能力摘要。"""
    if top_k > MAX_TOP_K:
        raise HarnessUserInputError("USER_INPUT", "top_k must be <= 20")
    manifest = manifest or load_capability_manifest()
    scored = []
    for item in registry_snapshot:
        if not _visible_in_space(item, context.space_id):
            continue
        score, matched = _score(query, item)
        if score <= 0:
            continue
        scored.append((score, item, matched))

    scored.sort(key=lambda row: (-row[0], *_identity(row[1])))
    if len(scored) >= 2 and scored[0][0] == scored[1][0] and scored[0][0] >= EXACT_ALIAS_SCORE:
        cards = [_to_card(item, score, matched, manifest) for score, item, matched in scored if score == scored[0][0]]
        raise AmbiguousCapability("multiple capabilities matched the query", candidates=cards)

    limited = scored[:top_k]
    candidates = [_to_card(item, score, matched, manifest) for score, item, matched in limited]
    next_actions = [{"action": "get_plugin_schema"}] if candidates else [{"action": "revise_query"}]
    return CapabilitySearchResult(ok=True, candidates=candidates, next_actions=next_actions)
