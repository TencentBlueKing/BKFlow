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
import copy
import datetime

from bamboo_engine.context import Context
from bamboo_engine.template import Template
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow import Service
from pipeline.eri.runtime import BambooDjangoRuntime
from pydantic import BaseModel

from bkflow.constants import TaskOperationSource, TaskOperationType, TaskTriggerMethod
from bkflow.exceptions import ValidationError
from bkflow.task.models import TaskOperationRecord


class Subprocess(BaseModel):
    subprocess_name: str
    pipeline: dict
    template_id: str
    notify_config: dict = {}


class SubprocessPluginService(Service):
    __need_schedule__ = True
    runtime = BambooDjangoRuntime()

    def execute(self, data, parent_data):
        from bkflow.task.models import TaskFlowRelation, TaskInstance
        from bkflow.task.operations import TaskOperation
        from bkflow.task.utils import extract_extra_info

        parent_task_id = parent_data.get_one_of_inputs("task_id")
        try:
            parent_task = TaskInstance.objects.get(id=parent_task_id)
        except TaskInstance.DoesNotExist:
            data.set_outputs("ex_data", f"parent task {parent_task_id} not found")
            return False

        subprocess_data = data.get_one_of_inputs("subprocess") or {}
        subprocess = Subprocess(**subprocess_data)
        pipeline_tree = subprocess.pipeline

        # 渲染父任务中的参数
        constants = pipeline_tree.get("constants", {})
        subprocess_inputs = {
            key: constant["value"]
            for key, constant in constants.items()
            if constant.get("show_type") == "show" and constant.get("need_render", True)
        }
        raw_subprocess_inputs = copy.deepcopy(subprocess_inputs)
        inputs_refs = Template(subprocess_inputs).get_reference()
        self.logger.info(f"subprocess original refs: {inputs_refs}")
        additional_refs = self.runtime.get_context_key_references(pipeline_id=self.top_pipeline_id, keys=inputs_refs)
        inputs_refs = inputs_refs.union(additional_refs)
        self.logger.info(f"subprocess final refs: {inputs_refs}")
        context_values = self.runtime.get_context_values(pipeline_id=self.top_pipeline_id, keys=inputs_refs)
        context_mappings = {c.key: c for c in context_values}
        root_pipeline_inputs = {
            key: inputs.value for key, inputs in self.runtime.get_data_inputs(self.top_pipeline_id).items()
        }
        context = Context(self.runtime, context_values, root_pipeline_inputs)
        hydrated_context = context.hydrate(deformat=True)
        self.logger.info(f"subprocess parent hydrated context: {hydrated_context}")

        parsed_subprocess_inputs = Template(subprocess_inputs).render(hydrated_context)
        parent_constants = parent_task.pipeline_tree["constants"]
        for key, constant in pipeline_tree.get("constants", {}).items():
            # 如果父流程直接勾选，则直接使用父流程对应变量的值
            raw_constant_value = raw_subprocess_inputs.get(key)
            if (
                raw_constant_value
                and isinstance(raw_constant_value, str)
                and parent_constants.get(raw_constant_value)
                and self.id in parent_constants[raw_constant_value]["source_info"]
                and key in parent_constants[raw_constant_value]["source_info"][self.id]
            ):
                constant["value"] = context_mappings[raw_subprocess_inputs[key]].value
            elif constant.get("need_render", True) and key in parsed_subprocess_inputs:
                constant["value"] = parsed_subprocess_inputs[key]
        self.logger.info(f'subprocess parsed constants: {pipeline_tree.get("constants", {})}')

        with transaction.atomic():
            time_zone = timezone.pytz.timezone(settings.TIME_ZONE) or "Asia/Shanghai"
            time_stamp = datetime.datetime.now(tz=time_zone).strftime("%Y%m%d%H%M%S")
            create_task_data = {
                "name": f"{subprocess.subprocess_name}_子流程_{time_stamp}",
                "template_id": subprocess.template_id,
                "creator": parent_task.creator,
                "scope_type": parent_task.scope_type,
                "scope_value": parent_task.scope_value,
                "space_id": parent_task.space_id,
                "pipeline_tree": pipeline_tree,
                "trigger_method": TaskTriggerMethod.subprocess.name,
                "mock_data": {},
            }
            DEFAULT_NOTIFY_CONFIG = {
                "notify_type": {"fail": [], "success": []},
                "notify_receivers": {"more_receiver": "", "receiver_group": []},
            }
            create_task_data.setdefault("extra_info", {}).update(
                {"notify_config": subprocess.notify_config or DEFAULT_NOTIFY_CONFIG}
            )

            task_instance = TaskInstance.objects.create_instance(**create_task_data)
            try:
                root_task_id = TaskFlowRelation.objects.get(task_id=parent_task_id).root_task_id
            except TaskFlowRelation.DoesNotExist:
                root_task_id = parent_task_id

            relate_info = {"node_id": self.id, "node_version": self.version}
            TaskFlowRelation.objects.create(
                task_id=task_instance.id,
                parent_task_id=parent_task_id,
                root_task_id=root_task_id,
                extra_info=relate_info,
            )

            # 记录操作流水
            pipeline_constants = task_instance.pipeline_tree.get("constants")
            extra_info = extract_extra_info(pipeline_constants)
            TaskOperationRecord.objects.create(
                instance_id=task_instance.id,
                operate_type=TaskOperationType.create.name,
                operate_source=TaskOperationSource.api.name,
                operator=parent_task.creator,
                extra_info=extra_info,
            )
        data.set_outputs("task_id", task_instance.id)
        task_operation = TaskOperation(task_instance=task_instance, queue=settings.BKFLOW_MODULE.code)
        operation_method = getattr(task_operation, "start", None)
        if operation_method is None:
            raise ValidationError("task operation not found")
        operation_method(operator=parent_task.creator)

        return True

    def schedule(self, data, parent_data, callback_data=None):
        from bkflow.task.models import TaskInstance

        task_success = callback_data.get("task_success", False)
        task_id = data.get_one_of_outputs("task_id")
        self.finish_schedule()
        if not task_success:
            data.set_outputs("ex_data", "子流程执行失败，请检查失败节点")
            return False
        try:
            subprocess_task = TaskInstance.objects.get(id=task_id)
        except TaskInstance.DoesNotExist:
            message = _(f"子任务[{task_id}]不存在")
            self.logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        subprocess_pipeline_id = subprocess_task.instance_id
        self.logger.info(f"subprocess pipeline id: {subprocess_pipeline_id}")
        subprocess_execution_data_outputs = self.runtime.get_execution_data_outputs(node_id=subprocess_pipeline_id)
        self.logger.info(f"subprocess execution data outputs: {subprocess_execution_data_outputs}")
        node_outputs = self.runtime.get_data_outputs(self.id)
        self.logger.info(f"node outputs: {node_outputs}")
        for key in filter(lambda x: x in subprocess_execution_data_outputs, node_outputs.keys()):
            data.set_outputs(key, subprocess_execution_data_outputs[key])
        return True


class SubprocessPluginComponent(Component):
    code = "subprocess_plugin"
    name = "SubprocessPlugin"
    bound_service = SubprocessPluginService
    version = "1.0.0"
