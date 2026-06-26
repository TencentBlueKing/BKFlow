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
import pytest
from pipeline.core.constants import PE

from bkflow.task.models import TaskInstance, TaskMockData
from bkflow.utils.context import TaskContext
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db
class TestDebugCreateInstance:
    def test_debug_method_materializes_mock_with_fail_nodes(self):
        pipeline_tree = build_default_pipeline_tree()
        node_id = list(pipeline_tree[PE.activities].keys())[0]
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=pipeline_tree,
            space_id=10,
            create_method="DEBUG",
            creator="admin",
            mock_data={
                "nodes": [node_id],
                "outputs": {node_id: {"k": "v"}},
                "fail_nodes": [node_id],
                "errors": {node_id: "boom"},
            },
        )
        mock = TaskMockData.objects.get(taskflow_id=instance.id)
        # 节点 id 经 replace_all_id 重映射，但单节点可断言键集合非空
        assert mock.data["nodes"]
        assert "fail_nodes" in mock.data and mock.data["fail_nodes"]
        assert "errors" in mock.data and list(mock.data["errors"].values()) == ["boom"]

    def test_debug_task_is_mock_true(self):
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=build_default_pipeline_tree(),
            space_id=10,
            create_method="DEBUG",
            creator="admin",
        )
        assert TaskContext(instance).is_mock is True
