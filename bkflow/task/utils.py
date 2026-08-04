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
import logging
from functools import wraps

from bamboo_engine import states as bamboo_engine_states
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.core import constants as pipeline_constants
from pipeline.engine.utils import calculate_elapsed_time
from redis.client import Redis

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.utils.dates import format_datetime
from bkflow.utils.message import send_message

logger = logging.getLogger("root")


def redis_inst_check(func):
    """如果 Redis 没有正确配置，则修饰的函数不执行"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            redis_inst = settings.redis_inst
            if not isinstance(redis_inst, Redis):
                logger.error("[redis_inst_check] redis_inst is not Redis instance, please check redis config")
                return
        except Exception as e:
            logger.error(f"[redis_inst_check] get redis_inst error, please check redis config: {e}")
            return
        return func(*args, **kwargs)

    return wrapper


def _format_status_time(status_tree):
    status_tree.setdefault("children", {})
    status_tree.pop("created_time", "")
    started_time = status_tree.pop("started_time", None)
    archived_time = status_tree.pop("archived_time", None)

    if "elapsed_time" not in status_tree:
        status_tree["elapsed_time"] = calculate_elapsed_time(started_time, archived_time)

    status_tree["start_time"] = format_datetime(started_time) if started_time else None
    status_tree["finish_time"] = format_datetime(archived_time) if archived_time else None


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
        elif bamboo_engine_states.SUSPENDED in child_status or "NODE_SUSPENDED" in child_status:
            status_tree["state"] = "NODE_SUSPENDED"


def add_node_name_to_status_tree(pipeline_tree, status_tree_children):
    for node_id, status in status_tree_children.items():
        status["name"] = pipeline_tree.get("activities", {}).get(node_id, {}).get("name", "")
        children = status.get("children", {})
        add_node_name_to_status_tree(pipeline_tree.get("activities", {}).get(node_id, {}).get("pipeline", {}), children)


def parse_node_timeout_configs(pipeline_tree: dict) -> list:
    configs = []
    for act_id, act in pipeline_tree[pipeline_constants.PE.activities].items():
        if act["type"] == pipeline_constants.PE.SubProcess:
            result = parse_node_timeout_configs(act[pipeline_constants.PE.pipeline])
            if not result["result"]:
                return result
            configs.extend(result["data"])
        elif act["type"] == pipeline_constants.PE.ServiceActivity:
            timeout_config = act.get("timeout_config", {})
            enable = timeout_config.get("enable")
            if not enable:
                continue
            timeout_seconds = timeout_config.get("seconds")
            action = timeout_config.get("action")
            if not timeout_seconds or not isinstance(timeout_seconds, int):
                message = _(f"节点执行失败: 节点[ID: {act_id}]配置了非法的超时时间: {timeout_seconds}, 请修改配置后重试")
                logger.error(message)
                # 对于不符合格式要求的情况，则不设置对应超时时间
                continue
            configs.append({"action": action, "node_id": act_id, "timeout": timeout_seconds})
    return {"result": True, "data": configs, "message": ""}


ATOM_FAILED = "atom_failed"
TASK_FINISHED = "task_finished"

DEFAULT_TITLE_TEMPLATE = "【BKFlow引擎服务通知】任务执行{status}"
DEFAULT_TASK_INSTANCE_MESSAGE_TEMPLATE = "您的任务【{task_name}】执行{status}，操作员是【{executor}】"


def send_task_instance_message(task_instance, msg_type):
    notify_info = task_instance.get_notify_info()
    if not notify_info["receivers"]:
        logger.info(
            "task instance[id={task_instance_id}] will not send {msg_type} message, because receivers is empty".format(
                task_instance_id=task_instance.id, msg_type=msg_type
            )
        )
        return True

    executor = task_instance.executor
    receivers = ",".join(notify_info["receivers"])
    types = notify_info["types"]
    msg_format = notify_info["format"]

    if msg_type == ATOM_FAILED:
        status = "失败"
        notify_type = types.get("fail", [])
    else:
        status = "完成"
        notify_type = types.get("success", [])
    title = (msg_format.get("title", "") or DEFAULT_TITLE_TEMPLATE).format(
        task_name=task_instance.name, status=status, executor=executor
    )
    content = (msg_format.get("content", "") or DEFAULT_TASK_INSTANCE_MESSAGE_TEMPLATE).format(
        task_name=task_instance.name, status=status, executor=executor
    )

    logger.info(
        "task instance[id={task_instance_id}] will send {msg_type} message({notify_type}) to: {receivers}".format(
            task_instance_id=task_instance.id, msg_type=msg_type, notify_type=notify_type, receivers=receivers
        )
    )
    send_message(executor, notify_type, receivers, title, content)

    return True


def extract_extra_info(constants, keys=None):
    extra_info = {}
    if not constants:
        return ""
    for key in list(constants.keys()) if not keys else keys:
        extra_info.update({key: {"name": constants[key]["name"], "value": constants[key]["value"]}})
    return json.dumps(extra_info, ensure_ascii=False)


def get_running_tasks_redis_key(template_id) -> str:
    return f"bkflow_running_tasks_template_{template_id}"


@redis_inst_check
def get_running_task_count(template_id) -> int:
    """获取指定模板当前运行中的任务数量。Redis 不可用时返回 0，不阻塞流程。"""
    if template_id is None:
        return 0
    try:
        return int(settings.redis_inst.scard(get_running_tasks_redis_key(template_id)) or 0)
    except Exception as e:
        logger.exception(f"[get_running_task_count] template_id={template_id} error: {e}")
        return 0


@redis_inst_check
def update_running_task(template_id, task_id, action: str) -> bool:
    """更新模板运行中任务集合。

    :param template_id: 模板 ID
    :param task_id: 任务 ID
    :param action: 操作类型，"add"：加入运行集合；"remove"：从运行集合移除
    :return: 操作是否成功
    """
    if template_id is None:
        return False
    if action not in ("add", "remove"):
        logger.error(f"[update_running_task] invalid action: {action}")
        return False
    try:
        key = get_running_tasks_redis_key(template_id)
        if action == "add":
            settings.redis_inst.sadd(key, str(task_id))
        else:
            settings.redis_inst.srem(key, str(task_id))
        return True
    except Exception as e:
        logger.exception(
            f"[update_running_task] action={action} template_id={template_id} task_id={task_id} error: {e}"
        )
        return False


def check_template_concurrency(space_id, template_id):
    """检查模板当前运行中任务数是否达到空间配置的最大并发上限。

    :param space_id: 空间 ID
    :param template_id: 模板 ID
    :return: (is_allowed, message)
        is_allowed: True 表示允许执行；False 表示已达上限。
        message: 当 is_allowed 为 False 时为提示信息。
    """
    if template_id is None:
        return True, ""
    try:
        interface_client = InterfaceModuleClient()
        space_infos_result = interface_client.get_space_infos(
            {"space_id": space_id, "config_names": "concurrency_control"}
        )
        space_configs = space_infos_result.get("data", {}).get("configs", {})
        max_running = int(space_configs.get("concurrency_control", 0))
    except Exception as e:
        logger.exception(f"[check_template_concurrency] get space concurrency_control error: {e}")
        return True, ""

    if not max_running:
        return True, ""

    running_count = get_running_task_count(template_id)
    if running_count >= max_running:
        msg = f"当前模板(template_id={template_id})正在运行的任务数已达上限({max_running})，" f"当前运行中数量为{running_count}，请稍后再试"
        return False, msg
    return True, ""
