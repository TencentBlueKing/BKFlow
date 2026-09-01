"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import zipfile
from collections import Counter
from pathlib import Path

import yaml

from bkflow.harness.services.facade import P0_TOOL_OPERATION_MAP

ROOT = Path(__file__).resolve().parents[3]
RESOURCES = ROOT / "bkflow/apigw/management/commands/data/api-resources.yml"
DOCS_DIR = ROOT / "bkflow/apigw/docs/zh"
DOCS_ZIP = ROOT / "bkflow/apigw/docs/apigw-docs.zip"

EXPECTED_ROUTES = {
    "harness_search_workflow_capabilities": "/space/{space_id}/harness/search_workflow_capabilities/",
    "harness_get_plugin_schema": "/space/{space_id}/harness/get_plugin_schema/",
    "harness_validate_workflow": "/space/{space_id}/harness/validate_workflow/",
    "harness_create_workflow_draft": "/space/{space_id}/harness/create_workflow_draft/",
}


def _paths():
    spec = yaml.safe_load(RESOURCES.read_text())
    return spec["paths"]


def test_four_prefixed_operations_exist_once_with_required_auth():
    """四个 prefixed operation 唯一存在，且鉴权与 backend 符合契约。"""
    paths = _paths()
    found = {}
    operation_ids = []
    for path, methods in paths.items():
        post = methods.get("post") or {}
        operation_id = post.get("operationId")
        if operation_id in EXPECTED_ROUTES:
            found[operation_id] = (path, post)
            operation_ids.append(operation_id)

    assert set(found) == set(EXPECTED_ROUTES)
    assert set(P0_TOOL_OPERATION_MAP.values()) == set(EXPECTED_ROUTES)
    assert Counter(operation_ids) == Counter(EXPECTED_ROUTES.keys())

    for operation_id, (path, post) in found.items():
        assert path == EXPECTED_ROUTES[operation_id]
        gateway = post["x-bk-apigateway-resource"]
        assert gateway["backend"]["name"] == "default"
        assert gateway["backend"]["method"] == "post"
        assert gateway["authConfig"] == {
            "appVerifiedRequired": True,
            "userVerifiedRequired": True,
            "resourcePermissionRequired": True,
        }


def test_chinese_docs_and_zip_contain_four_harness_operations():
    """四个中文文档存在，并且打包进 apigw-docs.zip。"""
    names = ["{}.md".format(operation_id) for operation_id in EXPECTED_ROUTES]
    for name in names:
        path = DOCS_DIR / name
        assert path.exists(), name
        text = path.read_text()
        assert "token" not in text.lower()
        assert "bk_app_secret" not in text
        assert "credential" not in text.lower() or "credential_ref" in text

    with zipfile.ZipFile(DOCS_ZIP) as archive:
        members = set(archive.namelist())
    for name in names:
        assert "zh/{}".format(name) in members or name in members
