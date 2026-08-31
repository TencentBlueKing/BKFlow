"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.conf import settings
from pipeline.component_framework.component import Component
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.constants import TaskTriggerMethod, WebhookEventType
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.components.collections.base import LoopBaseService


class SubcanvasPluginService(LoopBaseService):
    """
    子画布插件服务
    """

    plugin_name = "subcanvas_plugin"
    __need_schedule__ = True
    runtime = BambooDjangoRuntime()

    def plugin_execute(self, data, parent_data):
        from bkflow.task.models import TaskInstance
        from bkflow.task.operations import OperationResult, TaskOperation

        parent_task_id = parent_data.get_one_of_inputs("task_id")
        subprocess_name = data.get_one_of_inputs("subprocess_name")

        # 获取父任务实例
        try:
            parent_task = TaskInstance.objects.get(id=parent_task_id)
        except TaskInstance.DoesNotExist:
            data.set_outputs("ex_data", f"parent task {parent_task_id} not found")
            return False

        # 获取当前子画布节点的 pipeline 字段作为子任务的 pipeline_tree
        parent_pipeline_tree = parent_task.pipeline_tree
        current_node = parent_pipeline_tree["activities"].get(self.id)
        if not current_node:
            data.set_outputs("ex_data", f"current node {self.id} not found in parent task pipeline_tree")
            return False

        pipeline_tree = current_node.get("pipeline")
        if not pipeline_tree:
            data.set_outputs("ex_data", f"pipeline not found in current node {self.id}")
            return False

        try:
            sub_constant = self._render_parent_parameters(pipeline_tree, parent_task)
        except ValidationError as e:
            data.set_outputs("ex_data", str(e))
            return False

        notify_config = parent_task.extra_info.get("notify_config")
        # 创建子任务实例
        try:
            task_instance = self._create_subprocess_task_instance(
                subprocess_name,
                pipeline_tree,
                parent_task,
                TaskTriggerMethod.sub_canvas.name,
                notify_config=notify_config,
            )
        except ValidationError as e:
            data.set_outputs("ex_data", f"子任务创建失败: {e}")
            return False
        self.runtime.copy_context_values_to_new_pipeline(
            self.top_pipeline_id, task_instance.pipeline_tree["id"], {"${outputs}"}
        )
        sub_data = {c.key: c for c in sub_constant}
        self.runtime.upsert_plain_context_values(task_instance.pipeline_tree["id"], sub_data)

        constants = task_instance.pipeline_tree["constants"]
        parameters = {key: value["value"] for key, value in constants.items()}

        interface_client = InterfaceModuleClient()
        interface_client.broadcast_task_events(
            data={
                "space_id": task_instance.space_id,
                "event": WebhookEventType.TASK_CREATE.value,
                "extra_info": {
                    "task_id": task_instance.id,
                    "task_name": task_instance.name,
                    "parameters": parameters,
                    "trigger_source": TaskTriggerMethod.sub_canvas.name,
                    "is_subprocess_task": True,
                },
            }
        )

        # 设置输出并启动任务
        data.set_outputs("task_id", task_instance.id)
        task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
        operation_method = getattr(task_operation, "start", None)
        if operation_method is None:
            raise ValidationError("task operation not found")
        operation_result = operation_method(operator=parent_task.creator)
        if not isinstance(operation_result, OperationResult) or not operation_result.result:
            data.set_outputs("ex_data", getattr(operation_result, "message", "子任务启动失败"))
            return False

        return True


class SubcanvasPluginComponent(Component):
    code = "subcanvas_plugin"
    name = "SubcanvasPlugin"
    bound_service = SubcanvasPluginService
    version = "1.0.0"
