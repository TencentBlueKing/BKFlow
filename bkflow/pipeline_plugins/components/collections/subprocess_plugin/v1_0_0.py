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
from pydantic import BaseModel

from bkflow.constants import TaskTriggerMethod, WebhookEventType
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.components.collections.base import LoopBaseService


class Subprocess(BaseModel):
    subprocess_name: str
    template_id: str
    version: str
    always_use_latest: bool = False
    constants: dict


class SubprocessPluginService(LoopBaseService):
    plugin_name = "subprocess_plugin"
    __need_schedule__ = True
    runtime = BambooDjangoRuntime()

    def _get_subprocess_template(self, data):
        """获取子流程模板数据"""
        subprocess_data = data.get_one_of_inputs("subprocess") or {}
        subprocess = Subprocess(**subprocess_data)
        template_id = subprocess.template_id
        always_use_latest = subprocess.always_use_latest
        if always_use_latest:
            version = None
        else:
            version = subprocess.version
        interface_client = InterfaceModuleClient()
        template = interface_client.get_template_data(template_id=template_id, data={"version": version})

        # 检查API调用是否成功
        if not template.get("result"):
            data.set_outputs("ex_data", f"get subprocess data failed: {template['message']}")
            return None, None

        return template, subprocess

    def _process_subprocess_constants(self, subprocess, pipeline_tree):
        """处理子流程常量配置"""
        subproc_inputs = subprocess.constants
        # replace show constants with inputs
        subproc_constants = {}
        for key, info in subproc_inputs.items():
            # ignore expired parent constants data
            if subprocess.always_use_latest and key not in pipeline_tree["constants"]:
                continue
            if "form" in info:
                info.pop("form")

            # keep source_info consist with subprocess latest version
            if subprocess.always_use_latest:
                info["source_info"] = pipeline_tree["constants"][key]["source_info"]

            subproc_constants[key] = info

        pipeline_tree["constants"].update(subproc_constants)

    def plugin_execute(self, data, parent_data):
        from bkflow.task.models import TaskInstance
        from bkflow.task.operations import TaskOperation

        parent_task_id = parent_data.get_one_of_inputs("task_id")
        try:
            parent_task = TaskInstance.objects.get(id=parent_task_id)
        except TaskInstance.DoesNotExist:
            data.set_outputs("ex_data", f"parent task {parent_task_id} not found")
            return False

        template, subprocess = self._get_subprocess_template(data)
        if not template:
            return False

        pipeline_tree = template["data"]["pipeline_tree"]
        self._process_subprocess_constants(subprocess, pipeline_tree)
        try:
            self._render_parent_parameters(pipeline_tree, parent_task)
        except ValidationError as e:
            data.set_outputs("ex_data", str(e))
            return False

        # 创建子任务实例
        task_instance = self._create_subprocess_task_instance(
            subprocess.subprocess_name,
            pipeline_tree,
            parent_task,
            TaskTriggerMethod.subprocess.name,
            template_id=subprocess.template_id,
            notify_config=template["data"]["notify_config"],
        )
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
                    "template_id": task_instance.template_id,
                    "parameters": parameters,
                    "trigger_source": TaskTriggerMethod.subprocess.name,
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
        operation_method(operator=parent_task.creator)

        return True


class SubprocessPluginComponent(Component):
    code = "subprocess_plugin"
    name = "SubprocessPlugin"
    bound_service = SubprocessPluginService
    version = "1.0.0"
