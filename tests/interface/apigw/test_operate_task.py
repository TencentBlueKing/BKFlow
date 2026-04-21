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
import json
from unittest import mock

from bamboo_engine.builder import EmptyEndEvent, EmptyStartEvent, ServiceActivity, build_tree
from django.test import TestCase, override_settings

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.space.models import Space


def build_open_plugin_pipeline_tree(plugin_id="open_plugin_001", plugin_version="1.2.0"):
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="example_component")
    end = EmptyEndEvent()
    start.extend(act_1).extend(end)
    pipeline_tree = build_tree(start, data={"test": "test"})
    activity = next(iter(pipeline_tree["activities"].values()))
    activity["component"]["code"] = "uniform_api"
    activity["component"]["version"] = "v4.0.0"
    activity["component"]["data"] = {
        "uniform_api_plugin_url": {"hook": False, "need_render": True, "value": "https://bk-sops.example/run"},
        "uniform_api_plugin_method": {"hook": False, "need_render": True, "value": "POST"},
        "uniform_api_plugin_id": {"hook": False, "need_render": True, "value": plugin_id},
        "uniform_api_plugin_version": {"hook": False, "need_render": True, "value": plugin_version},
    }
    activity["component"]["api_meta"] = {
        "id": plugin_id,
        "name": "JOB 执行作业",
        "plugin_source": "builtin",
        "plugin_code": "job_execute_task",
        "source_key": "sops",
        "plugin_version": plugin_version,
    }
    return pipeline_tree


class TestOperateTask(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.operate_task.TaskComponentClient")
    def test_start_task_rejects_disabled_open_plugin(self, mock_client_class):
        pipeline_tree = build_open_plugin_pipeline_tree()
        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 1, "space_id": self.space.id, "pipeline_tree": pipeline_tree},
        }
        mock_client_class.return_value = mock_client

        OpenPluginCatalogIndex.objects.create(
            space_id=self.space.id,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.2.0",
            versions=["1.2.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=self.space.id,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=False,
        )

        data = {"operator": "test_user"}
        url = "/apigw/space/{}/task/1/operate_task/start/".format(self.space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 400)
        self.assertIn("未开放", resp_data["message"])
        mock_client.operate_task.assert_not_called()
