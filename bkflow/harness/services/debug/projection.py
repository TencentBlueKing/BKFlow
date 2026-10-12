"""Bounded node pages and immutable, session-owned terminal context evidence."""

import base64
import json
import re

from bkflow.harness.constants import DebugContextEvidenceType
from bkflow.harness.models import EvidenceEvent, ValidationReport
from bkflow.harness.safety import is_safe_harness_text
from bkflow.harness.services.canonical import canonical_json_bytes, sha256_json
from bkflow.harness.services.debug.policy import DebugStartRejected
from bkflow.harness.services.evidence import (
    EVIDENCE_REDACTION_VERSION,
    MAX_EVIDENCE_INLINE_BYTES,
    project_evidence_payload,
    record_evidence,
)
from bkflow.template.models import DebugNodeState

MAX_CONTEXT_NODES = 100
MAX_NODE_BYTES = 4096
MAX_PAGE_BYTES = 8192
META_EVENT = DebugContextEvidenceType.SNAPSHOT
NODES_EVENT = DebugContextEvidenceType.NODES
NODE_FIELDS = (
    "node_id",
    "name",
    "source_node_id",
    "node_type",
    "execution_mode",
    "configured_execution_mode",
    "last_execution_mode",
    "outputs",
    "supports_step",
    "supports_mock",
    "mock_result",
    "mock_outputs",
    "mock_error",
    "status",
    "waiting_reason",
    "can_step",
    "missing_vars",
    "duration_ms",
    "error_detail",
    "log_ref",
    "selected_flow_ids",
    "condition_results",
)
CONTEXT_FIELDS = (
    "template_id",
    "status",
    "active_task_id",
    "active_run_type",
    "active_node_id",
    "last_task_id",
    "last_run_type",
    "last_run_status",
    "last_error_detail",
    "last_inputs",
    "global_vars",
)
STATUSES = frozenset(choice[0] for choice in DebugNodeState.STATUS_CHOICES)


def enrich_context_view(session, view):
    """补充当前修订的节点映射及会话内运行证据，不修改节点默认配置。"""
    if not isinstance(view, dict) or not isinstance(view.get("nodes"), list):
        return view
    # 原始输出交给下游有界投影，不在预算检查前递归复制插件数据。
    view = {**view, "nodes": [dict(node) for node in view["nodes"]]}
    report = ValidationReport.objects.filter(revision=session.revision, checkpoint="VALIDATE").order_by("-id").first()
    source_map = report.result.get("source_map", {}) if report and report.result.get("valid") is True else {}
    # Evidence 属于本会话；达到扫描预算仍无证据时返回未知，绝不按配置猜测。
    runs = list(
        EvidenceEvent.objects.filter(debug_session=session, event_type="DEBUG_RUN_STARTED")
        .order_by("-occurred_at", "-id")
        .values_list("redacted_payload", flat=True)[:1000]
    )
    for node in view["nodes"]:
        node["source_node_id"] = source_map.get(node["node_id"])
        node["last_execution_mode"] = None
        if node.get("status") == "not_run":
            continue
        for run in runs:
            if run.get("node_id") == node["node_id"] or run.get("mode") == "global":
                mode = run.get("execution_mode")
                if node.get("node_type") in {
                    "ExclusiveGateway",
                    "ParallelGateway",
                    "ConvergeGateway",
                    "ConditionalParallelGateway",
                }:
                    mode = "real"
                node["last_execution_mode"] = mode if mode in {"real", "mock"} else None
                break
    return view


def _verify_context(view, nodes, metadata):
    """仅检查调试回读一致性，不代替业务验收、分页覆盖或发布审批。"""
    missing = sum(node.get("status") == "finished" and bool(node.get("missing_vars")) for node in nodes)
    failed = sum(node.get("status") in {"failed", "revoked"} for node in nodes)
    omitted = sum(bool(node.get("details_omitted")) for node in nodes)
    pending = sum(node.get("status") not in {"finished", "not_run"} for node in nodes)
    unobserved = sum(
        node.get("status") == "finished"
        and (
            not isinstance(node.get("outputs"), dict)
            or node.get("last_execution_mode") not in {"real", "mock"}
            or not isinstance(node.get("missing_vars"), list)
        )
        for node in nodes
    )
    if missing or failed or view.get("last_run_status") in {"failed", "revoked"}:
        status = "failed"
    elif (
        not nodes
        or pending
        or omitted
        or unobserved
        or metadata.get("omitted")
        or view.get("last_run_status") != "finished"
    ):
        status = "incomplete"
    else:
        status = "passed"
    return {
        "scope": "debug_context_consistency",
        "status": status,
        "finished_nodes_with_missing_vars": missing,
        "failed_or_revoked_nodes": failed,
        "omitted_nodes": omitted,
        "finished_nodes_without_observed_evidence": unobserved,
    }


def _has_reserved_metadata(value):
    """Inspect only already-bounded/redacted JSON, never scan raw provider data."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not is_safe_harness_text(key, max_chars=256, max_bytes=256, allow_empty=False):
                return True
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in {"approvalrequestid", "requiredcredentials"}:
                return True
            if "traceback" in normalized or "providerdetail" in normalized:
                return True
            if normalized == "type" and isinstance(item, str):
                if re.sub(r"[^a-z0-9]", "", item.lower()) == "approvalrequest":
                    return True
            if _has_reserved_metadata(item):
                return True
    elif isinstance(value, list):
        return any(_has_reserved_metadata(item) for item in value)
    return False


def project_debug_payload(value, *, inline_bytes=MAX_EVIDENCE_INLINE_BYTES):
    """Provider output cannot impersonate Harness approval or internal metadata."""
    projected = project_evidence_payload(value, inline_bytes=inline_bytes)
    if _has_reserved_metadata(projected):
        return {"omitted": True, "reason": "reserved_metadata", "redaction_version": EVIDENCE_REDACTION_VERSION}
    return projected


def _project_node(node, budget):
    # Reserve the response nesting depth as well as the byte budget. The same
    # result must survive both Evidence storage and APIGW's final safety filter.
    value = project_debug_payload([{"context_page": {"items": [node]}}], inline_bytes=budget)
    return value[0]["context_page"]["items"][0] if isinstance(value, list) else value


def build_context_snapshot(view):
    """Separate one oversized value from useful node state; never truncate silently."""
    if not isinstance(view, dict) or not isinstance(view.get("nodes"), list):
        return None
    nodes = view["nodes"]
    if len(nodes) > MAX_CONTEXT_NODES:
        return None
    counts = {}
    projected = []
    for node in nodes:
        if not isinstance(node, dict):
            return None
        status = node.get("status")
        status = status if isinstance(status, str) and status in STATUSES else "unknown"
        counts[status] = counts.get(status, 0) + 1
        item = _project_node({key: node[key] for key in NODE_FIELDS if key in node}, MAX_NODE_BYTES)
        if item.get("omitted") is True:
            brief = _project_node(
                {key: node[key] for key in ("node_id", "node_type", "status", "execution_mode") if key in node},
                1024,
            )
            item = {**brief, "details_omitted": True, "reason": item["reason"]}
        projected.append(item)
    metadata = project_debug_payload(
        [{"context_page": {"metadata": {key: view[key] for key in CONTEXT_FIELDS if key in view}}}], inline_bytes=2048
    )
    snapshot = {
        "summary": {"total_nodes": len(nodes), "status_counts": counts},
        "metadata": metadata[0]["context_page"]["metadata"] if isinstance(metadata, list) else metadata,
        "nodes": projected,
    }
    snapshot["verification"] = _verify_context(view, projected, snapshot["metadata"])
    return {**snapshot, "snapshot_id": sha256_json(snapshot)}


def _encode_cursor(session_id, snapshot_id, offset):
    return base64.urlsafe_b64encode(canonical_json_bytes([str(session_id), snapshot_id, offset])).decode().rstrip("=")


def context_page(session_id, snapshot, request):
    """A cursor is a position, not authority; callers must check session ownership first."""
    if snapshot is None:
        if request.node_cursor or request.node_id:
            raise DebugStartRejected("DEBUG_CONTEXT_CHANGED", "node_cursor")
        return None
    offset = 0
    if request.node_cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(request.node_cursor + "=" * (-len(request.node_cursor) % 4)))
            if not isinstance(decoded, list) or len(decoded) != 3:
                raise ValueError
            owner, digest, offset = decoded
            if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset < len(snapshot["nodes"]):
                raise ValueError
        except (TypeError, ValueError, UnicodeError):
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_cursor") from None
        if owner != str(session_id) or digest != snapshot["snapshot_id"]:
            raise DebugStartRejected("DEBUG_CONTEXT_CHANGED", "node_cursor")
    nodes = snapshot["nodes"]
    if request.node_id:
        nodes = [node for node in nodes if node.get("node_id") == request.node_id]
        if not nodes:
            raise DebugStartRejected("SCHEMA_VALIDATION_ERROR", "node_id")
    page = {
        "snapshot_id": snapshot["snapshot_id"],
        "summary": snapshot["summary"],
        "metadata": snapshot["metadata"],
        "items": [],
        "next_cursor": None,
        "verification": snapshot.get("verification", {"scope": "debug_context_consistency", "status": "incomplete"}),
        "coverage": {"offset": offset, "returned": 0, "total": len(nodes), "has_more": False},
    }
    for index in range(offset, min(len(nodes), offset + request.node_limit)):
        cursor = _encode_cursor(session_id, snapshot["snapshot_id"], index + 1) if index + 1 < len(nodes) else None
        candidate = {**page, "items": page["items"] + [nodes[index]], "next_cursor": cursor}
        candidate["coverage"] = {
            "offset": offset,
            "returned": len(candidate["items"]),
            "total": len(nodes),
            "has_more": cursor is not None,
        }
        # Reserve space for cursor/metadata and serialized punctuation in every page.
        if len(canonical_json_bytes(candidate)) > MAX_PAGE_BYTES - 256:
            break
        page = candidate
    return page


def persist_context_snapshot(session, view):
    """Write only bounded redacted chunks under the caller's locked terminal transition."""
    snapshot = build_context_snapshot(view)
    if snapshot is None:
        return
    common = {
        "run": session.run,
        "revision": session.revision,
        "debug_session": session,
        "action": "get_debug_session",
        "actor": session.actor,
        "correlation_id": session.trusted_context_snapshot["correlation_id"],
    }
    record_evidence(
        **common,
        event_type=META_EVENT,
        payload={key: value for key, value in snapshot.items() if key != "nodes"},
    )
    # Pack small nodes together while keeping each record below the existing
    # Evidence budget. No external writer or schema migration is required.
    chunk = {"snapshot_id": snapshot["snapshot_id"], "offset": 0, "items": []}
    for index, node in enumerate(snapshot["nodes"]):
        candidate = {**chunk, "items": chunk["items"] + [node]}
        if len(canonical_json_bytes(candidate)) > 7000:
            record_evidence(**common, event_type=NODES_EVENT, payload=chunk)
            chunk = {"snapshot_id": snapshot["snapshot_id"], "offset": index, "items": [node]}
        else:
            chunk = candidate
    if chunk["items"]:
        record_evidence(**common, event_type=NODES_EVENT, payload=chunk)


def load_context_snapshot(session):
    """Never read a template's newer DebugContext when browsing an old session."""
    events = EvidenceEvent.objects.filter(debug_session=session)
    meta = events.filter(event_type=META_EVENT).order_by("-occurred_at", "-id").first()
    if meta is None:
        return None
    snapshot = dict(meta.redacted_payload)
    rows = list(events.filter(event_type=NODES_EVENT).order_by("occurred_at", "id")[: MAX_CONTEXT_NODES + 1])
    if len(rows) > MAX_CONTEXT_NODES:
        return None
    records = [event.redacted_payload for event in rows]
    if any(item.get("snapshot_id") != snapshot["snapshot_id"] for item in records):
        return None
    records.sort(key=lambda item: item["offset"])
    snapshot["nodes"] = []
    for record in records:
        if record["offset"] != len(snapshot["nodes"]):
            return None
        snapshot["nodes"].extend(record["items"])
    if len(snapshot["nodes"]) != snapshot["summary"]["total_nodes"]:
        return None
    digest = sha256_json({key: value for key, value in snapshot.items() if key != "snapshot_id"})
    return snapshot if digest == snapshot["snapshot_id"] else None
