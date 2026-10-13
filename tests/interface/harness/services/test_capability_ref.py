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
import base64
import json

import pytest

from bkflow.harness.services.capability_ref import (
    MAX_CAPABILITY_REF_LENGTH,
    CapabilityReferenceError,
    decode_capability_ref,
    encode_capability_ref,
)


@pytest.mark.parametrize(
    "plugin_type,source_key,code,version",
    (
        ("component", None, "c" * 255, "v" * 64),
        ("remote_plugin", None, "r" * 100, "v" * 64),
        ("uniform_api", "s" * 64, "p" * 128, "v" * 64),
    ),
)
def test_capability_ref_round_trips_current_maximum_legal_identities(plugin_type, source_key, code, version):
    """The reference must preserve every identity component without truncation."""
    reference = encode_capability_ref(
        plugin_type=plugin_type,
        source_key=source_key,
        code=code,
        version=version,
    )

    decoded = decode_capability_ref(reference)

    assert reference.startswith("cap_v1_")
    assert decoded.plugin_type == plugin_type
    assert decoded.source_key == source_key
    assert decoded.code == code
    assert decoded.version == version
    assert encode_capability_ref(**decoded.as_dict()) == reference


def test_capability_ref_keeps_the_existing_439_character_uniform_identity_valid():
    """Tightening decode ceilings must not reject the current maximum ASCII V4 uniform identity."""
    reference = encode_capability_ref("uniform_api", "s" * 64, "p" * 128, "v" * 64)

    assert len(reference) == 439
    assert decode_capability_ref(reference).code == "p" * 128


def test_capability_ref_round_trips_four_byte_component_maximum():
    """Four-byte UTF-8 identities at the stored character maximum remain exactly reversible."""
    reference = encode_capability_ref("component", None, "😀" * 255, "版" * 64)

    assert len(reference) <= MAX_CAPABILITY_REF_LENGTH
    assert decode_capability_ref(reference).code == "😀" * 255


def test_capability_ref_keeps_all_four_byte_code_and_version_at_exact_ceiling():
    """The documented 1799-byte opaque-reference ceiling accepts the full four-byte maximum."""
    reference = encode_capability_ref("component", None, "😀" * 255, "😀" * 64)

    assert len(reference) == MAX_CAPABILITY_REF_LENGTH
    assert decode_capability_ref(reference).version == "😀" * 64


@pytest.mark.parametrize("plugin_type,source_key", (("component", None), ("uniform_api", "source-a")))
def test_capability_ref_translates_lone_surrogates_to_typed_errors(plugin_type, source_key):
    """Unencodable source text must not leak a raw UnicodeEncodeError through reference APIs."""
    with pytest.raises(CapabilityReferenceError):
        encode_capability_ref(plugin_type, source_key, "bad\ud800", "1")

    payload = {"plugin_type": plugin_type, "source_key": source_key, "code": "bad\ud800", "version": "1"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    with pytest.raises(CapabilityReferenceError):
        decode_capability_ref("cap_v1_{}".format(encoded))


def test_capability_ref_allows_a_legacy_uniform_none_source_key():
    """Legacy uniform identities are structurally distinct from V4 source-keyed catalog identities."""
    assert decode_capability_ref(encode_capability_ref("uniform_api", None, "legacy", "1")).source_key is None


@pytest.mark.parametrize("version", ("v" * 128, "v" * 129))
def test_capability_ref_enforces_remote_plugin_persisted_version_limit(version):
    """Remote versions must follow the exact 128-character persisted contract."""
    if len(version) == 128:
        assert decode_capability_ref(encode_capability_ref("remote_plugin", None, "remote", version)).version == version
    else:
        with pytest.raises(CapabilityReferenceError):
            encode_capability_ref("remote_plugin", None, "remote", version)


@pytest.mark.parametrize(
    "plugin_type,source_key,code,version",
    (
        ("component", None, "c" * 256, "v" * 64),
        ("component", "source", "c" * 255, "v" * 64),
        ("remote_plugin", "source", "r" * 100, "v" * 64),
        ("uniform_api", "源" * 65, "p" * 128, "v" * 64),
        ("uniform_api", "s" * 64, "p" * 129, "v" * 64),
        ("uniform_api", "s" * 64, "p" * 128, "版" * 65),
    ),
)
def test_capability_ref_rejects_source_specific_max_plus_one_identities(plugin_type, source_key, code, version):
    """Accepting values beyond authoritative model limits can make a reference impossible to resolve exactly."""
    with pytest.raises(CapabilityReferenceError):
        encode_capability_ref(plugin_type, source_key, code, version)


def test_capability_ref_rejects_oversized_encoded_payload_before_decoding():
    """Decoding an unbounded opaque payload first would permit avoidable parser work on hostile input."""
    with pytest.raises(CapabilityReferenceError):
        decode_capability_ref("cap_v1_" + "a" * MAX_CAPABILITY_REF_LENGTH)


@pytest.mark.parametrize(
    "reference",
    (
        "cap_v2_eyJjb2RlIjoiZGVtbyJ9",
        "cap_v1_not%2Furlsafe",
        "cap_v1_eyJjb2RlIjoiZGVtbyJ9=",
        "cap_v1_eyJjb2RlIjoiZGVtbyJ9",
    ),
)
def test_capability_ref_rejects_invalid_prefix_or_base64(reference):
    """A malformed opaque reference must never degrade into a raw plugin lookup."""
    with pytest.raises(CapabilityReferenceError):
        decode_capability_ref(reference)


@pytest.mark.parametrize(
    "payload",
    (
        {"plugin_type": "component", "source_key": None, "code": "demo"},
        {"plugin_type": "component", "source_key": None, "code": "demo", "version": "1", "extra": True},
        {"plugin_type": "unknown", "source_key": None, "code": "demo", "version": "1"},
        {"plugin_type": "component", "source_key": "", "code": "demo", "version": "1"},
        {"plugin_type": "component", "source_key": None, "code": "demo", "version": 1},
    ),
)
def test_capability_ref_rejects_noncanonical_or_invalid_identity_payload(payload):
    """The decoder accepts one closed canonical JSON representation only."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")

    with pytest.raises(CapabilityReferenceError):
        decode_capability_ref("cap_v1_{}".format(encoded))
