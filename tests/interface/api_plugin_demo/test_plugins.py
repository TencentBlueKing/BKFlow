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
from types import SimpleNamespace

from bkflow.api_plugin_demo import plugins


class TestApiPluginDemoPath:
    """测试 API 插件 demo 路径生成"""

    def test_builds_urls_with_current_apigw_stage(self, monkeypatch):
        """API 插件 demo URL 使用当前网关环境"""
        monkeypatch.setattr(
            plugins,
            "settings",
            SimpleNamespace(
                BK_API_URL_TMPL="http://{api_name}.example.com",
                BK_APIGW_NAME="bkflow",
                BK_APIGW_STAGE_NAME="prod",
            ),
        )

        api_list = plugins.get_api_list(limit=10, offset=0, scope_type="", scope_value="", category="")
        api_detail = plugins.get_api_detail("get_user_info")

        assert api_list["apis"][0]["meta_url"] == (
            "http://bkflow.example.com/prod/api_plugin_demo/detail_meta/?api_id=get_user_info"
        )
        assert api_detail["url"] == "http://bkflow.example.com/prod/api_plugin_demo/execute/get_user_info/"
