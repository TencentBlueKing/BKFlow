"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True, order=True)
class Grant:
    """一项不可变的资源授权。"""

    resource_type: str
    resource_id: str
    permission_type: str

    def as_dict(self) -> dict:
        """返回可序列化的授权三元组。"""
        return asdict(self)


def canonical_grants(grants: Iterable[Grant]) -> Tuple[Grant, ...]:
    """按完整三元组排序并去重授权。"""
    return tuple(sorted(set(grants)))


def _payload_hash(payload: list) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def grant_hash(grant: Grant) -> str:
    """计算单项授权的版本化摘要。"""
    return _payload_hash(["v1", grant.resource_type, grant.resource_id, grant.permission_type])


def grant_set_hash(grants: Iterable[Grant]) -> str:
    """计算规范授权集合的版本化摘要。"""
    canonical = canonical_grants(grants)
    payload = ["v1", [[grant.resource_type, grant.resource_id, grant.permission_type] for grant in canonical]]
    return _payload_hash(payload)
