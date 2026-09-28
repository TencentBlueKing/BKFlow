"""稳定的幂等身份编码；历史迁移保存独立副本，修改编码必须显式迁移。"""

import hashlib
import json

SCOPE_FIELDS = ("platform_app", "actor", "space_id", "tool_name", "run_scope", "idempotency_key")


def normalize_scope(values):
    """按持久化字段类型归一，不折叠大小写、重音或尾空格。"""
    return {
        name: None if values[name] is None else (int(values[name]) if name == "space_id" else str(values[name]))
        for name in SCOPE_FIELDS
    }


def scope_hash(values):
    """用有序 JSON 数组避免分隔符歧义，并压缩六维唯一索引。"""
    normalized = normalize_scope(values)
    encoded = json.dumps([normalized[name] for name in SCOPE_FIELDS], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
