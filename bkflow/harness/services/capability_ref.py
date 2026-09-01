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
import base64
import json
from typing import Any, Dict, Optional

from bkflow.harness.exceptions import CapabilityRefError
from bkflow.harness.services.canonical import canonical_json_bytes

CAPABILITY_REF_PREFIX = "cap_v1_"
CAPABILITY_REF_FIELDS = ("plugin_type", "source_key", "code", "version")


def encode_capability_ref(
    *,
    plugin_type: str,
    source_key: Optional[str],
    code: str,
    version: str,
) -> str:
    """将精确能力身份编码为不透明 capability_ref。"""
    payload = {
        "plugin_type": plugin_type,
        "source_key": source_key,
        "code": code,
        "version": version,
    }
    encoded = base64.urlsafe_b64encode(canonical_json_bytes(payload)).decode("ascii").rstrip("=")
    return f"{CAPABILITY_REF_PREFIX}{encoded}"


def decode_capability_ref(capability_ref: str) -> Dict[str, Any]:
    """解码 capability_ref，拒绝裸 plugin code 和非法载荷。"""
    if not isinstance(capability_ref, str) or not capability_ref.startswith(CAPABILITY_REF_PREFIX):
        raise CapabilityRefError("invalid capability_ref prefix")
    blob = capability_ref[len(CAPABILITY_REF_PREFIX) :]
    if not blob:
        raise CapabilityRefError("empty capability_ref payload")
    padding = "=" * (-len(blob) % 4)
    try:
        raw = base64.urlsafe_b64decode(blob + padding)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CapabilityRefError("malformed capability_ref") from exc
    if not isinstance(payload, dict) or set(payload.keys()) != set(CAPABILITY_REF_FIELDS):
        raise CapabilityRefError("capability_ref fields are invalid")
    return {field: payload[field] for field in CAPABILITY_REF_FIELDS}
