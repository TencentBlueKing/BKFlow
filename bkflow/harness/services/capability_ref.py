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
import binascii
import json
from dataclasses import dataclass
from typing import Optional

from bkflow.harness.services.canonical import canonical_json_bytes

CAPABILITY_REF_PREFIX = "cap_v1_"
UNVERSIONED = "unversioned"
SUPPORTED_PLUGIN_TYPES = frozenset(("component", "remote_plugin", "uniform_api"))
REFERENCE_FIELDS = frozenset(("plugin_type", "source_key", "code", "version"))
IDENTITY_LIMITS = {
    "component": {"source_key": 0, "code": 255, "version": 64},
    "remote_plugin": {"source_key": 0, "code": 100, "version": 128},
    "uniform_api": {"source_key": 64, "code": 128, "version": 64},
}
IDENTITY_UTF8_BYTE_LIMITS = {
    plugin_type: {field: maximum * 4 for field, maximum in limits.items()}
    for plugin_type, limits in IDENTITY_LIMITS.items()
}
# Four-byte UTF-8 maxima: component code/version is the longest accepted payload (1799 chars encoded).
MAX_CAPABILITY_REF_LENGTH = 1799


class CapabilityReferenceError(ValueError):
    """Raised when an opaque capability reference is malformed or non-canonical."""


def _utf8_length(value, field):
    """Return a strict UTF-8 length without leaking surrogate encoding errors."""
    try:
        return len(value.encode("utf-8"))
    except UnicodeError as error:
        raise CapabilityReferenceError("capability {} is invalid".format(field)) from error


@dataclass(frozen=True)
class CapabilityReference:
    """Closed identity embedded in a deterministic opaque capability reference."""

    plugin_type: str
    source_key: Optional[str]
    code: str
    version: str

    def as_dict(self):
        """Return the canonical identity payload in its fixed field set."""
        return {
            "plugin_type": self.plugin_type,
            "source_key": self.source_key,
            "code": self.code,
            "version": self.version,
        }


def validate_capability_identity(plugin_type, source_key, code, version=None):
    """Validate a closed source identity before it reaches catalog or model code.

    ``version`` is optional for catalog rows, whose authoritative source does
    not always expose a version.  Reference encoding supplies it and therefore
    receives the additional exact-version validation below.
    """
    if plugin_type not in SUPPORTED_PLUGIN_TYPES:
        raise CapabilityReferenceError("unsupported capability plugin type")
    limits = IDENTITY_LIMITS[plugin_type]
    byte_limits = IDENTITY_UTF8_BYTE_LIMITS[plugin_type]
    if (
        not isinstance(code, str)
        or not code
        or len(code) > limits["code"]
        or _utf8_length(code, "code") > byte_limits["code"]
    ):
        raise CapabilityReferenceError("capability code is invalid")
    if limits["source_key"] == 0 and source_key is not None:
        raise CapabilityReferenceError("capability source key is invalid")
    if source_key is not None and (
        not isinstance(source_key, str)
        or not source_key
        or len(source_key) > limits["source_key"]
        or _utf8_length(source_key, "source key") > byte_limits["source_key"]
    ):
        raise CapabilityReferenceError("capability source key is invalid")
    if version is None:
        return plugin_type, source_key, code
    if (
        not isinstance(version, str)
        or not version
        or len(version) > limits["version"]
        or _utf8_length(version, "version") > byte_limits["version"]
    ):
        raise CapabilityReferenceError("capability version is invalid")
    return CapabilityReference(plugin_type=plugin_type, source_key=source_key, code=code, version=version)


def _validate_identity(plugin_type, source_key, code, version):
    """Validate one exact identity against its authoritative source-model limits."""
    return validate_capability_identity(plugin_type, source_key, code, version)


def encode_capability_ref(plugin_type, source_key, code, version):
    """Encode a version-pinned capability identity as one URL-safe opaque reference."""
    identity = _validate_identity(plugin_type, source_key, code, version)
    encoded = base64.urlsafe_b64encode(canonical_json_bytes(identity.as_dict())).decode("ascii").rstrip("=")
    capability_ref = "{}{}".format(CAPABILITY_REF_PREFIX, encoded)
    if len(capability_ref) > MAX_CAPABILITY_REF_LENGTH:
        raise CapabilityReferenceError("capability reference is too large")
    return capability_ref


def decode_capability_ref(capability_ref):
    """Decode only the canonical, closed v1 capability reference representation."""
    if (
        not isinstance(capability_ref, str)
        or len(capability_ref) > MAX_CAPABILITY_REF_LENGTH
        or not capability_ref.startswith(CAPABILITY_REF_PREFIX)
    ):
        raise CapabilityReferenceError("unsupported capability reference")
    payload = capability_ref[len(CAPABILITY_REF_PREFIX) :]
    is_urlsafe = all(char.isascii() and (char.isalnum() or char in "-_") for char in payload)
    if not payload or "=" in payload or not is_urlsafe:
        raise CapabilityReferenceError("capability reference is not URL-safe base64")
    try:
        raw = base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise CapabilityReferenceError("capability reference base64 is malformed")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError):
        raise CapabilityReferenceError("capability reference payload is malformed")
    if not isinstance(value, dict) or set(value) != REFERENCE_FIELDS:
        raise CapabilityReferenceError("capability reference payload fields are invalid")
    identity = _validate_identity(**value)
    if raw != canonical_json_bytes(identity.as_dict()) or capability_ref != encode_capability_ref(**identity.as_dict()):
        raise CapabilityReferenceError("capability reference payload is not canonical")
    return identity
