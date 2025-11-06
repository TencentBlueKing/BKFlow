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
import functools
import logging
import traceback
from copy import deepcopy
from typing import Any, List, Optional

from bamboo_engine import api as bamboo_engine_api
from bamboo_engine import exceptions as bamboo_engine_exceptions
from bamboo_engine import exceptions as bamboo_exceptions
from bamboo_engine import states as bamboo_engine_states
from bamboo_engine.api import EngineAPIResult
from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue, ContextValueType
from bamboo_engine.template import Template
from django.utils import timezone
from pipeline.component_framework.library import ComponentLibrary
from pipeline.engine.utils import calculate_elapsed_time
from pipeline.eri.imp.serializer import SerializerMixin
from pipeline.eri.models import ExecutionData as DBExecutionData
from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.parser.context import get_pipeline_context
from pydantic import BaseModel, validator

from bkflow.constants import (
    PipelineContextObjType,
    RecordType,
    TaskOperationSource,
    TaskOperationType,
    TaskStates,
)
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.exceptions import ValidationError
from bkflow.pipeline_web.parser.format import format_web_data_to_pipeline
from bkflow.task.context import SystemObject
from bkflow.task.models import EngineSpaceConfig, TaskInstance
from bkflow.task.signals.signals import taskflow_started
from bkflow.task.utils import format_bamboo_engine_status
from bkflow.utils.canvas import get_variable_mapping
from bkflow.utils.dates import format_datetime

logger = logging.getLogger("root")


class OperationResult(BaseModel):
    result: bool
    data: Optional[Any] = None
    message: str = ""
    exc: str = None
    exc_trace: str = None

    @validator("exc", pre=True)
    def parse_exc(cls, value):
        if value is not None:
            return str(value)
        return value

    class Config:
        orm_mode = True


def uniform_task_operation_result(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            msg = f"task operation error: {e}"
            logger.exception(msg)
            trace = traceback.format_exc()
            return OperationResult(result=False, message=msg, exc=str(e), exc_trace=trace)

        if isinstance(result, OperationResult):
            operation_result = result
        elif isinstance(result, EngineAPIResult):
            operation_result = OperationResult.from_orm(result)
        elif isinstance(result, dict):
            operation_result = OperationResult(**result)
        else:
            operation_result = OperationResult(result=True, data=result)
        return operation_result

    return wrapper


class TaskOperation:
    CREATED_STATUS = {
        "start_time": None,
        "state": TaskStates.CREATED.value,
        "retry": 0,
        "skip": 0,
        "finish_time": None,
        "elapsed_time": 0,
        "children": {},
    }

    def __init__(self, task_instance: TaskInstance, queue: str = None, *args, **kwargs):
        self.task_instance = task_instance
        self.queue = queue

    @record_operation(RecordType.task.name, TaskOperationType.start.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def start(self, operator: str, *args, **kwargs) -> OperationResult:
        # CAS
        update_success = TaskInstance.objects.filter(id=self.task_instance.id, is_started=False).update(
            start_time=timezone.now(), is_started=True, executor=operator
        )
        self.task_instance.calculate_tree_info()

        if not update_success:
            raise ValidationError("task already started")

        try:
            self.task_instance.refresh_from_db()
            # convert web pipeline to pipeline
            pipeline = format_web_data_to_pipeline(self.task_instance.execution_data)

            root_pipeline_data = get_pipeline_context(
                self.task_instance, obj_type=PipelineContextObjType.instance.value, username=operator
            )
            system_obj = SystemObject(root_pipeline_data)
            root_pipeline_context = {"${_system}": system_obj}

            # 读取 引擎模块配置 注入空间和域变量
            engine_var = EngineSpaceConfig.get_space_var(space_id=self.task_instance.space_id)
            space_var = engine_var.get("space", None)
            scope_var = engine_var.get("scope", None)

            scope_type, scope_id = root_pipeline_data.get("task_scope_type"), root_pipeline_data.get("task_scope_value")

            if scope_type is not None and scope_id is not None and space_var is not None:
                # 域变量 存在则加入
                scope_var = scope_var.get(f"{scope_type}_{scope_id}", None)
                if scope_var is not None:
                    scope_obj = SystemObject(scope_var)
                    root_pipeline_context.update({"${_scope}": scope_obj})
            if space_var is not None:
                # 空间变量 存在则加入
                space_obj = SystemObject(space_var)
                root_pipeline_context.update({"${_space}": space_obj})

            # run pipeline
            result = bamboo_engine_api.run_pipeline(
                runtime=BambooDjangoRuntime(),
                pipeline=pipeline,
                root_pipeline_data=root_pipeline_data,
                root_pipeline_context=root_pipeline_context,
                subprocess_context=root_pipeline_context,
                queue=self.queue,
                cycle_tolerate=True,
            )
        except Exception as e:
            logger.exception(f"run pipeline failed: {e}")
            TaskInstance.objects.filter(id=self.task_instance.id, is_started=True).update(
                start_time=None,
                is_started=False,
                executor="",
            )
            raise

        if not result.result:
            TaskInstance.objects.filter(id=self.task_instance.id, is_started=True).update(
                start_time=None,
                is_started=False,
                executor="",
            )
            logger.error("run_pipeline fail: {}, exception: {}".format(result.message, result.exc_trace))
        else:
            taskflow_started.send(sender=self.__class__, task_id=self.task_instance.id)

        return result

    @record_operation(RecordType.task.name, TaskOperationType.pause.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def pause(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.pause_pipeline(
            runtime=BambooDjangoRuntime(), pipeline_id=self.task_instance.instance_id
        )

    @record_operation(RecordType.task.name, TaskOperationType.resume.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def resume(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.resume_pipeline(
            runtime=BambooDjangoRuntime(), pipeline_id=self.task_instance.instance_id
        )

    @record_operation(RecordType.task.name, TaskOperationType.revoke.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def revoke(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.revoke_pipeline(
            runtime=BambooDjangoRuntime(), pipeline_id=self.task_instance.instance_id
        )

    @uniform_task_operation_result
    def get_task_states(
        self, subprocess_id: str = None, with_ex_data: bool = False, *args, **kwargs
    ) -> OperationResult:
        if self.task_instance.is_expired:
            return OperationResult(result=True, data={"state": TaskStates.EXPIRED.value})
        if not self.task_instance.is_started:
            return OperationResult(result=True, data=self.CREATED_STATUS)

        runtime = BambooDjangoRuntime()
        state_result = bamboo_engine_api.get_pipeline_states(
            runtime=runtime, root_id=self.task_instance.instance_id, flat_children=False
        )
        if not state_result.result:
            logger.error(
                "get_pipeline_states fail: {}, exception: {}".format(state_result.message, state_result.exc_trace)
            )
            return state_result

        task_states = state_result.data
        if not task_states:
            return OperationResult(result=True, data={"state": TaskStates.CREATED.value})
        task_states = task_states[self.task_instance.instance_id]

        def get_subprocess_states(states) -> dict:
            for child in states["children"].values():
                if child["id"] == subprocess_id:
                    return child
                if child["children"]:
                    status = get_subprocess_states(child)
                    if status is not None:
                        return status

        if subprocess_id:
            task_states = get_subprocess_states(task_states)

        # subprocess not been executed
        task_states = task_states or TaskStates.CREATED.value

        def _format_status_time(status_tree):
            status_tree.setdefault("children", {})
            status_tree.pop("created_time", "")
            started_time = status_tree.pop("started_time", None)
            archived_time = status_tree.pop("archived_time", None)

            if "elapsed_time" not in status_tree:
                status_tree["elapsed_time"] = calculate_elapsed_time(started_time, archived_time)

            status_tree["start_time"] = format_datetime(started_time) if started_time else ""
            status_tree["finish_time"] = format_datetime(archived_time) if archived_time else ""

        def format_bamboo_engine_status(status_tree):
            """
            @summary: 转换通过 bamboo engine api 获取的任务状态格式
            @return:
            """
            _format_status_time(status_tree)
            child_status = set()
            for identifier_code, child_tree in list(status_tree["children"].items()):
                format_bamboo_engine_status(child_tree)
                child_status.add(child_tree["state"])

            if status_tree["state"] == bamboo_engine_states.RUNNING:
                if bamboo_engine_states.FAILED in child_status:
                    status_tree["state"] = bamboo_engine_states.FAILED
                elif bamboo_engine_states.SUSPENDED in child_status:
                    status_tree["state"] = "NODE_SUSPENDED"

        format_bamboo_engine_status(task_states)

        def collect_fail_nodes(task_status: dict) -> list:
            task_status["ex_data"] = {}
            children_list = [task_status["children"]]
            failed_nodes = []
            while len(children_list) > 0:
                children = children_list.pop(0)
                for _, node in children.items():
                    if node["state"] == bamboo_engine_states.FAILED:
                        if len(node["children"]) > 0:
                            children_list.append(node["children"])
                            continue
                        failed_nodes.append(node_id)
            return failed_nodes

        # 返回失败节点和对应调试信息
        if with_ex_data and task_states["state"] == bamboo_engine_states.FAILED:
            fail_nodes = collect_fail_nodes(task_states)
            task_states["ex_data"] = {}
            for node_id in fail_nodes:
                data_result = bamboo_engine_api.get_execution_data_outputs(runtime=runtime, node_id=node_id)

                if not data_result:
                    task_states["ex_data"][node_id] = "get ex_data fail: {}".format(data_result.exc)
                else:
                    task_states["ex_data"][node_id] = data_result.data.get("ex_data")

        return OperationResult(result=True, data=task_states)

    @uniform_task_operation_result
    def render_current_constants(self):
        runtime = BambooDjangoRuntime()
        context_values = runtime.get_context(self.task_instance.instance_id)
        try:
            root_pipeline_inputs = {
                key: di.value for key, di in runtime.get_data_inputs(self.task_instance.instance_id).items()
            }
        except bamboo_engine_exceptions.NotFoundError:
            return OperationResult(result=False, message="data not found, task is not running")
        context = Context(runtime, context_values, root_pipeline_inputs)

        try:
            hydrated_context = context.hydrate()
        except Exception as e:
            logger.exception("[render_current_constants] hydrate context failed: {}".format(e))
            return OperationResult(
                result=False, message="hydrate context failed.", exc=e, exc_trace=traceback.format_exc()
            )

        data = [{"key": key, "value": value} for key, value in hydrated_context.items()]
        return OperationResult(result=True, data=data)

    @uniform_task_operation_result
    def render_context_with_node_outputs(self, node_ids: List[str], to_render_constants):
        runtime = BambooDjangoRuntime()
        context_values = runtime.get_context(self.task_instance.instance_id)
        constants = self.task_instance.pipeline_tree.get("constants", {})

        context_dict = {cv.key: cv for cv in context_values}

        # 构建节点输出变量的映射关系
        node_outputs = {}
        node_id_constants_map = get_variable_mapping(constants, set(node_ids))

        # 获取节点输出数据
        nodes = DBExecutionData.objects.filter(node_id__in=node_ids).iterator()

        # 反序列化节点输出
        nodes_data = {}
        for node in nodes:
            try:
                nodes_data[node.node_id] = SerializerMixin()._deserialize(node.outputs, node.outputs_serializer)
            except Exception as e:
                logger.exception(
                    "[render_context] Failed to deserialize node outputs: node_id=%s, error=%s", node.node_id, str(e)
                )
                continue

        # 根据映射关系构建最终的输出数据
        for node_id, node_data in nodes_data.items():
            node_mapping = node_id_constants_map.get(node_id, {})
            for original_key, value in node_data.items():
                if mapped_key := node_mapping.get(original_key):
                    node_outputs[mapped_key] = value

        for key, value in node_outputs.items():
            if key not in context_dict:
                context_dict[key] = ContextValue(key=key, type=ContextValueType.PLAIN, value=value, code=None)
            elif value != context_dict[key].value:
                context_dict[key].value = value

        # 转换回列表
        context_values = list(context_dict.values())

        try:
            context = Context(runtime, context_values, to_render_constants)
            hydrated_context = context.hydrate(deformat=True)
            hydrated_param_data = Template(to_render_constants).render(hydrated_context)
        except Exception as e:
            logger.exception("[render_context_with_node_outputs] hydrate context failed: %s", e)
            return OperationResult(
                result=False, message="hydrate context failed.", exc=e, exc_trace=traceback.format_exc()
            )

        return OperationResult(
            result=True, data=[{"key": key, "value": value} for key, value in hydrated_param_data.items()]
        )


class TaskNodeOperation:
    def __init__(self, task_instance: TaskInstance, node_id: str, *args, **kwargs):
        self.task_instance = task_instance
        self.node_id = node_id
        self.runtime = BambooDjangoRuntime()

    @record_operation(RecordType.task_node.name, TaskOperationType.retry.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def retry(self, operator: str, *args, **kwargs) -> OperationResult:
        api_result = bamboo_engine_api.get_data(runtime=self.runtime, node_id=self.node_id)
        if not api_result.result:
            return api_result
        return bamboo_engine_api.retry_node(
            runtime=self.runtime, node_id=self.node_id, data=kwargs.get("inputs") or None
        )

    @record_operation(RecordType.task_node.name, TaskOperationType.skip.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def skip(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.skip_node(runtime=self.runtime, node_id=self.node_id)

    @record_operation(RecordType.task_node.name, TaskOperationType.callback.name, TaskOperationSource.api.name)
    @uniform_task_operation_result
    def callback(self, operator: str, *args, **kwargs) -> OperationResult:
        runtime = BambooDjangoRuntime()
        version = kwargs.get("version")
        if not version:
            version = runtime.get_state(self.node_id).version
        return bamboo_engine_api.callback(runtime=runtime, node_id=self.node_id, version=version, data=kwargs["data"])

    @record_operation(RecordType.task_node.name, TaskOperationType.skip_exg.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def skip_exg(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.skip_exclusive_gateway(
            runtime=self.runtime, node_id=self.node_id, flow_id=kwargs["flow_id"]
        )

    @record_operation(RecordType.task_node.name, TaskOperationType.skip_cpg.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def skip_cpg(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.skip_conditional_parallel_gateway(
            runtime=self.runtime,
            node_id=self.node_id,
            flow_ids=kwargs["flow_ids"],
            converge_gateway_id=kwargs["converge_gateway_id"],
        )

    @record_operation(RecordType.task_node.name, TaskOperationType.forced_fail.name, TaskOperationSource.app.name)
    @uniform_task_operation_result
    def forced_fail(self, operator: str, *args, **kwargs) -> OperationResult:
        return bamboo_engine_api.forced_fail_activity(
            runtime=self.runtime,
            node_id=self.node_id,
            ex_data=kwargs.get("ex_data", f"forced fail by {operator}"),
            send_post_set_state_signal=kwargs.get("send_post_set_state_signal", True),
        )

    @uniform_task_operation_result
    def get_node_detail(
        self, subprocess_stack: List[str] = None, loop: Optional[int] = None, *args, **kwargs
    ) -> OperationResult:
        if subprocess_stack is None:
            subprocess_stack = []

        runtime = BambooDjangoRuntime()
        result = bamboo_engine_api.get_children_states(runtime=runtime, node_id=self.node_id)
        if not result.result:
            return result

        detail = result.data
        # 节点已经执行
        if detail:
            detail = detail[self.node_id]
            # 默认只请求最后一次循环结果
            format_bamboo_engine_status(detail)
            if loop is None or int(loop) >= detail["loop"]:
                loop = detail["loop"]
                hist_result = bamboo_engine_api.get_node_histories(runtime=runtime, node_id=self.node_id, loop=loop)
                if not hist_result:
                    logger.exception("bamboo_engine_api.get_node_histories fail")
                    return hist_result
                for hist in hist_result.data:
                    hist["ex_data"] = hist.get("outputs", {}).get("ex_data", "")
                detail["histories"] = hist_result.data
                detail["history_id"] = -1
            # 如果用户传了 loop 参数，并且 loop 小于当前节点已循环次数，则从历史数据获取结果
            else:
                hist_result = bamboo_engine_api.get_node_histories(runtime=runtime, node_id=self.node_id, loop=loop)
                if not hist_result:
                    logger.exception("bamboo_engine_api.get_node_histories fail")
                    return hist_result
                self._assemble_history_detail(detail=detail, histories=hist_result.data)
                detail["history_id"] = hist_result.data[-1]["id"]
                detail["version"] = hist_result.data[-1]["version"]

            for hist in detail["histories"]:
                # 重试记录必然是因为失败才重试
                hist.setdefault("state", bamboo_engine_states.FAILED)
                hist["history_id"] = hist["id"]
                format_bamboo_engine_status(hist)
        # 节点未执行
        else:
            node = self._get_node_info(
                node_id=self.node_id, pipeline=self.task_instance.execution_data, subprocess_stack=subprocess_stack
            )
            detail.update(
                {
                    "name": node["name"],
                    "error_ignorable": node.get("error_ignorable", False),
                    "state": bamboo_engine_states.READY,
                }
            )

        return OperationResult(result=True, data=detail)

    @uniform_task_operation_result
    def get_outputs(self, *args, **kwargs) -> OperationResult:
        runtime = BambooDjangoRuntime()
        outputs_result = bamboo_engine_api.get_execution_data_outputs(runtime=runtime, node_id=self.node_id)
        if not outputs_result.result:
            logger.error(f"get_outputs failed: {outputs_result.message}, exc: {outputs_result.exc}")
        return outputs_result

    @uniform_task_operation_result
    def get_node_data(
        self,
        username: str,
        subprocess_stack: List[str],
        component_code: Optional[str] = None,
        loop: Optional[int] = None,
        *args,
        **kwargs,
    ) -> OperationResult:
        runtime = BambooDjangoRuntime()
        result = bamboo_engine_api.get_children_states(runtime=runtime, node_id=self.node_id)
        if not result.result:
            logger.exception("bamboo_engine_api.get_children_states fail")
            return result

        state = result.data
        # 已执行的节点直接获取执行数据
        inputs = {}
        outputs = {}
        node_info = self._get_node_info(
            node_id=self.node_id, pipeline=self.task_instance.execution_data, subprocess_stack=subprocess_stack
        )
        node_code = node_info.get("component", {}).get("code")
        if state:
            # 获取最新的执行数据
            if loop is None or int(loop) >= state[self.node_id]["loop"]:
                result = bamboo_engine_api.get_execution_data(runtime=runtime, node_id=self.node_id)
                if not result.result:
                    logger.exception("bamboo_engine_api.get_execution_data fail")
                    # 对上层屏蔽执行数据不存在的场景
                    if isinstance(result.exc, bamboo_exceptions.NotFoundError):
                        return OperationResult(
                            result=True, data={"inputs": {}, "outputs": [], "ex_data": ""}, message=""
                        )
                    return result

                data = result.data
                if node_info["type"] == "SubProcess":
                    # remove prefix '${' and subfix '}' in subprocess execution input
                    inputs = {k[2:-1]: v for k, v in data["inputs"].items()}
                elif node_info["type"] == "ServiceActivity" and node_code == "subprocess_plugin":
                    raw_inputs = data["inputs"]["subprocess"]["constants"]
                    inputs = {key[2:-1]: value.get("value") for key, value in raw_inputs.items()}
                else:
                    inputs = data["inputs"]
                outputs = data["outputs"]
                outputs = {"outputs": outputs, "ex_data": outputs.get("ex_data")}
            # 读取历史记录
            else:
                result = bamboo_engine_api.get_node_histories(runtime=runtime, node_id=self.node_id, loop=loop)
                if not result.result:
                    logger.exception("bamboo_engine_api.get_node_histories fail")
                    return result

                hist = result.data
                if hist:
                    inputs = hist[-1]["inputs"]
                    outputs = hist[-1]["outputs"]
                    outputs = {"outputs": outputs, "ex_data": outputs.get("ex_data")}
        # 未执行节点需要实时渲染
        else:
            if node_info["type"] not in {"ServiceActivity", "SubProcess"}:
                return OperationResult(result=True, data={"inputs": {}, "outputs": [], "ex_data": ""}, message="")
            try:
                root_pipeline_data = get_pipeline_context(
                    self.task_instance, obj_type="instance", data_type="data", username=username
                )
                # TODO： 补充系统变量
                # system_obj = SystemObject(root_pipeline_data)
                # root_pipeline_context = {"${_system}": {"type": "plain", "value": system_obj}}
                root_pipeline_context = {}
                # TODO： 补充空间变量
                # root_pipeline_context.update(
                #     {
                #         key: {"type": "plain", "value": value}
                #         for key, value in get_project_constants_context(kwargs["project_id"]).items()
                #     }
                # )
                existing_context_values = runtime.get_context(self.task_instance.instance_id)
                root_pipeline_context.update(
                    {
                        context_value.key: {"type": "plain", "value": context_value.value}
                        for context_value in existing_context_values
                        if context_value.type == ContextValueType.PLAIN
                    }
                )

                formatted_pipeline = format_web_data_to_pipeline(self.task_instance.execution_data)
                preview_result = bamboo_engine_api.preview_node_inputs(
                    runtime=runtime,
                    pipeline=formatted_pipeline,
                    node_id=self.node_id,
                    subprocess_stack=subprocess_stack,
                    root_pipeline_data=root_pipeline_data,
                    parent_params=root_pipeline_context,
                )

                if not preview_result.result:
                    message = f"节点数据请求失败: 请重试, 如多次失败可联系管理员处理. {preview_result.exc}"
                    logger.error(message)
                    return OperationResult(result=False, data={}, message=message)

                if node_info["type"] == "SubProcess":
                    # remove prefix '${' and subfix '}' in subprocess execution input
                    inputs = {k[2:-1]: v for k, v in preview_result.data.items()}
                elif node_info["type"] == "ServiceActivity" and node_code == "subprocess_plugin":
                    raw_inputs = preview_result.data["subprocess"]["constants"]
                    inputs = {k[2:-1]: v.get("value") for k, v in raw_inputs.items()}
                else:
                    inputs = preview_result.data

            except Exception as err:
                return OperationResult(result=False, data={}, message=err)

        # 根据传入的 component_code 对输出进行格式化
        success, err, outputs_table = self._format_outputs(
            outputs=outputs,
            component_code=component_code,
            subprocess_stack=subprocess_stack,
        )
        if not success:
            return OperationResult(result=False, data={}, message=err)

        data = {"inputs": inputs, "outputs": outputs_table, "ex_data": outputs.pop("ex_data", "")}
        return OperationResult(result=True, data=data, message="")

    @staticmethod
    def _assemble_history_detail(detail: dict, histories: list):
        # index 为 -1 表示当前 loop 的最新一次重试执行，历史 loop 最终状态一定是 FINISHED
        # deepcopy 是为了不在 format_pipeline_status 中修改原数据
        current_loop = deepcopy(histories[-1])
        current_loop["state"] = bamboo_engine_states.FINISHED
        format_bamboo_engine_status(current_loop)
        detail.update(
            {
                "start_time": current_loop["start_time"],
                "finish_time": current_loop["finish_time"],
                "elapsed_time": current_loop["elapsed_time"],
                "loop": current_loop["loop"],
                "skip": current_loop["skip"],
                "state": current_loop["state"],
            }
        )
        # index 非 -1 表示当前 loop 的重试记录
        detail["histories"] = histories[:-1]

    @staticmethod
    def _get_node_info(node_id: str, pipeline: dict, subprocess_stack: Optional[list] = None) -> dict:
        subprocess_stack = subprocess_stack or []

        def get_node_info(pipeline: dict, subprocess_stack: list) -> dict:
            # go deeper
            if subprocess_stack:
                return get_node_info(pipeline["activities"][subprocess_stack[0]]["pipeline"], subprocess_stack[1:])

            nodes = {
                pipeline["start_event"]["id"]: pipeline["start_event"],
                pipeline["end_event"]["id"]: pipeline["end_event"],
            }
            nodes.update(pipeline["activities"])
            nodes.update(pipeline["gateways"])
            return nodes[node_id]

        return get_node_info(pipeline, subprocess_stack)

    def _format_outputs(
        self,
        outputs: dict,
        component_code: str,
        subprocess_stack: Optional[list] = None,
    ) -> (bool, str, list):
        outputs_table = []
        if component_code:
            try:
                version = (
                    self._get_node_info(self.node_id, self.task_instance.execution_data, subprocess_stack)
                    .get("component", {})
                    .get("version", None)
                )
                component = ComponentLibrary.get_component_class(component_code=component_code, version=version)
                outputs_format = component.outputs_format()
            except Exception:
                logger.exception(
                    "_format_outputs(node_id: {}, outputs: {}, component_code: {}) fail".format(
                        self.node_id, outputs, component_code
                    )
                )
                return False, "_format_outputs fail", []
            else:
                # for some special empty case e.g. ''
                outputs_data = outputs.get("outputs") or {}
                # 在标准插件定义中的预设输出参数
                archived_keys = []
                for outputs_item in outputs_format:
                    value = outputs_data.get(outputs_item["key"], "")
                    outputs_table.append(
                        {"name": outputs_item["name"], "key": outputs_item["key"], "value": value, "preset": True}
                    )
                    archived_keys.append(outputs_item["key"])
                # 其他输出参数
                for out_key, out_value in list(outputs_data.items()):
                    if out_key not in archived_keys:
                        outputs_table.append(
                            {
                                "name": out_key[2:-1] if component_code == "subprocess_plugin" else out_key,
                                "key": out_key,
                                "value": out_value,
                                "preset": component_code == "subprocess_plugin",
                            }
                        )
        else:
            try:
                outputs_table = [
                    {"key": key, "value": val, "preset": False}
                    for key, val in list((outputs.get("outputs") or {}).items())
                ]
            except Exception:
                logger.exception(
                    "_format_outputs(node_id: {}, outputs: {}, component_code: {}) fail".format(
                        self.node_id, outputs, component_code
                    )
                )
                return False, "_format_outputs fail", []

        node_id_constants_map = {}
        try:
            # 尝试搜索并替换变量重命名的值
            constants = self.task_instance.execution_data.get("constants", {})

            for key, value in constants.items():
                # 只对输出进行重命名，如果变量来源非输出，则跳过
                if not value.get("source_type") == "component_outputs":
                    continue
                # 搜索这些新变量的来源
                source_info = value.get("source_info", {})
                # 查看来源中是否有自己
                if self.node_id in source_info.keys():
                    if len(source_info[self.node_id]) > 0:
                        # key = ${key}, key[2:-1] = key
                        node_id_constants_map[source_info[self.node_id][0]] = key[2:-1]
        except Exception as e:
            logger.exception("[_format_outputs]变量重命名格式化失败，error={}".format(e))
            return True, "", outputs_table

        for item in outputs_table:
            key = item.get("key")
            if key in node_id_constants_map.keys():
                # 替换key值
                item["key"] = node_id_constants_map[key]

        return True, "", outputs_table
