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
import hashlib
import json
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

import env

DEFAULT_CALLBACK_TOKEN_TTL = timedelta(hours=2)
OPEN_PLUGIN_CALLBACK_TOKEN_META_KEY = "HTTP_X_CALLBACK_TOKEN"


def get_open_plugin_callback_token_ttl():
    """回调 token 有效期，默认对齐节点最长执行时间。"""
    seconds = getattr(settings, "OPEN_PLUGIN_CALLBACK_TOKEN_TTL", None)
    if seconds:
        return timedelta(seconds=int(seconds))
    max_timeout = getattr(settings, "MAX_NODE_EXECUTE_TIMEOUT", None)
    if max_timeout:
        return timedelta(seconds=int(max_timeout))
    return DEFAULT_CALLBACK_TOKEN_TTL


def _get_callback_fernet():
    callback_key = getattr(settings, "CALLBACK_KEY", None) or env.CALLBACK_KEY
    if callback_key:
        return Fernet(callback_key)

    # 测试与本地开发环境下若未显式配置 callback key，退化为基于 SECRET_KEY 的稳定派生值，
    # 保证签发与验签仍然能自洽，不影响生产显式配置场景。
    derived = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def build_open_plugin_client_request_id(task_id, node_id, retry_no=1):
    return f"task-{task_id}-node-{node_id}-attempt-{retry_no}"


def callback_token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_open_plugin_callback_token(task_id, node_id, client_request_id, node_version="", expire_at=None):
    expire_at = expire_at or (timezone.now() + get_open_plugin_callback_token_ttl())
    payload = {
        "task_id": task_id,
        "node_id": node_id,
        "node_version": node_version or "",
        "client_request_id": client_request_id,
        "expire_at": expire_at.isoformat(),
    }
    token = _get_callback_fernet().encrypt(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("utf-8")
    return token, expire_at


def parse_open_plugin_callback_token(token):
    payload = _get_callback_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    return json.loads(payload)
