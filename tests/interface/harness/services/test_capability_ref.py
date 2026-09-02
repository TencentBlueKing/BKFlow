"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import pytest

from bkflow.harness.exceptions import CapabilityRefError
from bkflow.harness.services.capability_ref import (
    decode_capability_ref,
    encode_capability_ref,
)


def test_capability_ref_round_trip_is_deterministic():
    """相同身份编码结果稳定，且可以无损解码。"""
    payload = {
        "plugin_type": "component",
        "source_key": None,
        "code": "demo_restart_service",
        "version": "1.0.0",
    }
    first = encode_capability_ref(**payload)
    second = encode_capability_ref(**payload)
    assert first == second
    assert first.startswith("cap_v1_")
    assert decode_capability_ref(first) == payload


@pytest.mark.parametrize(
    "value",
    [
        "cap_v2_abc",
        "cap_v1_@@@",
        "cap_v1_",
        "plain_plugin_code",
    ],
)
def test_decode_rejects_invalid_prefix_or_base64(value):
    """拒绝错误前缀或损坏的 Base64。"""
    with pytest.raises(CapabilityRefError):
        decode_capability_ref(value)


def test_decode_rejects_missing_and_unsupported_fields():
    """拒绝缺字段或额外字段。"""
    import base64

    from bkflow.harness.services.canonical import canonical_json_bytes

    raw = canonical_json_bytes({"plugin_type": "component", "code": "x"})
    ref = "cap_v1_" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    with pytest.raises(CapabilityRefError):
        decode_capability_ref(ref)

    extra = encode_capability_ref(plugin_type="component", source_key=None, code="x", version="1.0.0")
    decoded = decode_capability_ref(extra)
    assert set(decoded) == {"plugin_type", "source_key", "code", "version"}
