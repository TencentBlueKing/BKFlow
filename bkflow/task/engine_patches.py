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

import logging
from functools import wraps

from bamboo_engine import states
from bamboo_engine.eri import ExecutionData
from bamboo_engine.handler import ExecuteResult
from bamboo_engine.handlers.service_activity import ServiceActivityHandler

logger = logging.getLogger(__name__)

PATCHED_ATTR = "_bkflow_memory_error_handler_patched"

MEMORY_ERROR_EX_DATA = "".join(
    [
        "节点执行数据保存失败，可能是节点输入/输出数据过大导致 worker 内存不足。",
        "请检查上游节点输出和当前节点渲染后的输入，避免在流程变量中传递大对象。",
    ]
)


def build_memory_error_ex_data(exc: MemoryError) -> str:
    """构造节点详情中展示的内存异常提示。"""

    return "{} 异常类型: {}。".format(MEMORY_ERROR_EX_DATA, exc.__class__.__name__)


def fail_service_activity_on_memory_error(
    handler,
    process_info,
    loop: int,
    inner_loop: int,
    version: str,
    recover_point,
    exc: MemoryError,
) -> ExecuteResult:
    """将 ServiceActivity 的内存异常转换为节点失败结果。"""

    logger.error(
        "root_pipeline[%s] node(%s) service activity failed by memory error",
        process_info.root_pipeline_id,
        handler.node.id,
        exc_info=(exc.__class__, exc, exc.__traceback__),
    )

    ex_data = build_memory_error_ex_data(exc)
    handler.runtime.node_execute_fail(process_info.root_pipeline_id, handler.node.id)
    handler.runtime.set_state(
        node_id=handler.node.id,
        version=version,
        to_state=states.FAILED,
        set_archive_time=True,
        ignore_boring_set=recover_point is not None,
    )
    handler.runtime.set_execution_data(
        node_id=handler.node.id,
        data=ExecutionData(
            inputs={},
            outputs={
                "ex_data": ex_data,
                "_result": False,
                "_loop": loop,
                "_inner_loop": inner_loop,
            },
        ),
    )

    return ExecuteResult(
        should_sleep=True,
        schedule_ready=False,
        schedule_type=None,
        schedule_after=-1,
        dispatch_processes=[],
        next_node_id=None,
    )


def patch_service_activity_handler():
    """为 bamboo-engine ServiceActivity 执行阶段补充 MemoryError 兜底处理。"""

    if getattr(ServiceActivityHandler.execute, PATCHED_ATTR, False):
        return

    original_execute = ServiceActivityHandler.execute

    @wraps(original_execute)
    def execute_with_memory_error_handler(
        self,
        process_info,
        loop,
        inner_loop,
        version,
        recover_point=None,
    ):
        try:
            return original_execute(self, process_info, loop, inner_loop, version, recover_point)
        except MemoryError as exc:
            return fail_service_activity_on_memory_error(
                handler=self,
                process_info=process_info,
                loop=loop,
                inner_loop=inner_loop,
                version=version,
                recover_point=recover_point,
                exc=exc,
            )

    setattr(execute_with_memory_error_handler, PATCHED_ATTR, True)
    ServiceActivityHandler.execute = execute_with_memory_error_handler
