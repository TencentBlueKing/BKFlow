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

from bamboo_engine import api as bamboo_engine_api
from bamboo_engine import states
from django.conf import settings
from django.core.exceptions import ValidationError
from pipeline.eri.models import Schedule as DBSchedule
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.task.models import TaskFlowRelation
from bkflow.utils.redis_lock import redis_lock

logger = logging.getLogger("root")


class TaskCallBacker:
    def __init__(self, task_id, *args, **kwargs):
        self.task_id = task_id
        self.task_relate = TaskFlowRelation.objects.filter(task_id=self.task_id).first()
        self.extra_info = {"task_id": self.task_id, **self.task_relate.extra_info, **kwargs}

    def check_record_existence(self):
        return True if self.task_relate else False

    def subprocess_callback(self):
        try:
            node_id, version = self.extra_info["node_id"], self.extra_info["node_version"]
            with redis_lock(settings.redis_inst, key=f"sc_{node_id}_{version}") as (acquired_result, err):
                if not acquired_result:
                    # 如果对应节点已经在回调，则直接忽略本次回调
                    logger.error(f"[TaskCallBacker _subprocess_callback] get lock error: {err}")
                    return None
                runtime = BambooDjangoRuntime()
                node_state = runtime.get_state(node_id)
                if node_state.name not in [states.RUNNING, states.FAILED]:
                    raise ValidationError(f"node state is not running or failed, but {node_state.name}")
                if node_state.version != version:
                    raise ValidationError(f"node version is not {version}, but {node_state.version}")
                if node_state.name == states.FAILED:
                    if self.extra_info["task_success"] is False:
                        logger.info(
                            f"[TaskCallBacker _subprocess_callback] info: child task not success: {self.task_id}"
                        )
                        return True
                    schedule = runtime.get_schedule_with_node_and_version(node_id, version)
                    DBSchedule.objects.filter(id=schedule.id).update(expired=False)
                    # FAILED 状态需要转换为 READY 之后才能转换为 RUNNING
                    runtime.set_state(node_id=node_id, version=version, to_state=states.READY)
                    runtime.set_state(node_id=node_id, version=version, to_state=states.RUNNING)

                bamboo_engine_api.callback(runtime=runtime, node_id=node_id, version=version, data=self.extra_info)

        except Exception as e:
            message = f"[TaskCallBacker _subprocess_callback] error: {e}, with data {self.task_relate.extra_info}"
            logger.exception(message)
        else:
            logger.info(f"[TaskCallBacker _subprocess_callback] data: {self.task_relate.extra_info}, callback success.")
        return True
