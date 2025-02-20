# -*- coding: utf-8 -*-
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
import re
from functools import partial

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

import env
from bkflow.constants import JobBizScopeType
from bkflow.utils.handlers import handle_api_error
from config.default import BKAPP_INNER_CALLBACK_ENTRY

logger = logging.getLogger("celery")

__group_name__ = _("作业平台(JOB)")

JOB_SUCCESS = {3}
JOB_VAR_TYPE_IP = 2

job_handle_api_error = partial(handle_api_error, __group_name__)
LOG_VAR_SEARCH_CONFIGS = [{"re": r"<SOPS_VAR>(.+?)</SOPS_VAR>", "kv_sep": ":"}]


def get_node_callback_url(space_id, task_id, node_id, node_version=""):
    f = Fernet(env.CALLBACK_KEY)
    callback_entry = BKAPP_INNER_CALLBACK_ENTRY + "callback/%s/"
    return (
        callback_entry
        % f.encrypt(bytes("{}:{}:{}:{}".format(space_id, task_id, node_id, node_version), encoding="utf8")).decode()
    )


def convert_dict_value(data):
    # 将默认的 inputs 的 value 尝试 json loads 成 python 的基本对象类型
    inputs_data = {}
    for key, value in data.items():
        try:
            inputs_data[key] = json.loads(value)
        except Exception as e:
            logger.exception("convert value failed, key={}, value={}, err={}".format(key, value, e))
            inputs_data[key] = value
    return inputs_data


def get_job_instance_url(biz_cc_id, job_instance_id):
    url_format = "{}/api_execute/{}"
    return url_format.format(settings.BK_JOB_HOST, job_instance_id)


def get_job_tagged_ip_dict(
    client, service_logger, job_instance_id, bk_biz_id, job_scope_type=JobBizScopeType.BIZ.value
):
    """根据job步骤执行标签获取 IP 分组"""
    kwargs = {
        "bk_scope_type": job_scope_type,
        "bk_scope_id": str(bk_biz_id),
        "bk_biz_id": bk_biz_id,
        "job_instance_id": job_instance_id,
        "return_ip_result": True,
    }
    result = client.jobv3.get_job_instance_status(kwargs)

    if not result["result"]:
        message = handle_api_error(
            __group_name__,
            "jobv3.get_job_instance_status",
            kwargs,
            result,
        )
        service_logger.warning(message)
        return False, message

    step_instance = result["data"]["step_instance_list"][-1]

    step_ip_result_list = step_instance["step_ip_result_list"]
    tagged_ip_dict = {}

    for step_ip_result in step_ip_result_list:
        tag_key = step_ip_result["tag"]
        if not tag_key:
            continue
        ip = get_ip_from_step_ip_result(step_ip_result)
        if tag_key in tagged_ip_dict:
            tagged_ip_dict[tag_key] += f",{ip}"
        else:
            tagged_ip_dict[tag_key] = ip

    return True, tagged_ip_dict


def get_ip_from_step_ip_result(step_ip_result):
    ip = step_ip_result.get("ip")
    if not ip:
        ip = step_ip_result.get("ipv6", "")
    # 防止极端情况下，ipv6 仍然不可用
    return ip or ""


def get_job_sops_var_dict(client, service_logger, job_instance_id, bk_biz_id, job_scope_type=JobBizScopeType.BIZ.value):
    """
    解析作业日志：默认取每个步骤/节点的第一个ip_logs
    :param client:
    :param service_logger: 组件日志对象
    :param job_instance_id: 作业实例id
    :param bk_biz_id 业务ID
    :return:
    - success { "result": True, "data": {"key1": "value1"}}
    - fail { "result": False, "message": message}
    """
    get_job_instance_log_result = get_job_instance_log(
        client, service_logger, job_instance_id, bk_biz_id, job_scope_type=job_scope_type
    )
    if not get_job_instance_log_result["result"]:
        return get_job_instance_log_result
    log_text = get_job_instance_log_result["data"]
    service_logger.info(log_text)
    return {"result": True, "data": get_sops_var_dict_from_log_text(log_text, service_logger)}


def get_job_instance_log(
    client, service_logger, job_instance_id, bk_biz_id, target_ip=None, job_scope_type=JobBizScopeType.BIZ.value
):
    """
    获取作业日志：获取某个ip每个步骤的日志
    :param client:
    :param service_logger: 组件日志对象
    :param job_instance_id: 作业实例id
    :param bk_biz_id 业务ID
    :param target_ip 希望提取日志的目标IP
    获取到的job_logs实例
    [
        {
            "status": 3,
            "step_results": [
                {
                    "tag": "",
                    "ip_logs": [
                        {
                            "total_time": 0.363,
                            "ip": "1.1.1.1",
                            "start_time": "2020-06-15 17:23:11 +0800",
                            "log_content": "<SOPS_VAR>key1:value1</SOPS_VAR>\ngsectl\n-rwxr-xr-x 1",
                            "exit_code": 0,
                            "bk_cloud_id": 0,
                            "retry_count": 0,
                            "end_time": "2020-06-15 17:23:11 +0800",
                            "error_code": 0
                        },
                    ],
                    "ip_status": 9
                }
            ],
            "is_finished": true,
            "step_instance_id": 12321,
            "name": "查看文件"
        },
    ]
    :return:
    - success { "result": True, "data": "log text of target_ip"}
    - fail { "result": False, "message": message}
    """
    get_job_instance_status_kwargs = {
        "bk_scope_type": job_scope_type,
        "bk_scope_id": str(bk_biz_id),
        "bk_biz_id": bk_biz_id,
        "job_instance_id": job_instance_id,
        "return_ip_result": True,
    }
    get_job_instance_status_return = client.jobv3.get_job_instance_status(**get_job_instance_status_kwargs)
    if not get_job_instance_status_return["result"]:
        message = handle_api_error(
            __group_name__,
            "jobv3.get_job_instance_status",
            get_job_instance_status_kwargs,
            get_job_instance_status_return,
        )
        service_logger.warning(message)
        return {"result": False, "message": message}
    # 根据每个步骤的IP（可能有多个），循环查询作业执行日志
    log_list = []
    for step_instance in get_job_instance_status_return["data"]["step_instance_list"]:
        if not step_instance.get("step_ip_result_list"):
            continue
        # 为了防止查询时间过长，每个步骤只取一个IP的日志进行记录
        step_ip_result = None
        if target_ip:
            for ip_result in step_instance["step_ip_result_list"]:
                if ip_result["ip"] == target_ip:
                    step_ip_result = ip_result
            if step_ip_result is None:
                message = _(
                    f"执行历史请求失败: IP:[{target_ip}], 不属于IP列表: "
                    f"[{','.join([instance['ip'] for instance in step_instance['step_ip_result_list']])}]"
                    f" | get_job_instance_log"
                )
                service_logger.error(message)
                return {"result": False, "message": message}
        else:
            step_ip_result = step_instance["step_ip_result_list"][0]
        get_job_instance_ip_log_kwargs = {
            "bk_scope_type": job_scope_type,
            "bk_scope_id": str(bk_biz_id),
            "bk_biz_id": bk_biz_id,
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance["step_instance_id"],
            "bk_cloud_id": step_ip_result["bk_cloud_id"],
            "ip": step_ip_result["ip"],
            "bk_host_id": step_ip_result["bk_host_id"],
        }
        # 内部版不需要使用 ipv6 参数 直接携带 ip 和 bk_host_id

        get_job_instance_ip_log_kwargs_return = client.jobv3.get_job_instance_ip_log(get_job_instance_ip_log_kwargs)
        if not get_job_instance_ip_log_kwargs_return["result"]:
            message = handle_api_error(
                __group_name__,
                "jobv3.get_job_instance_ip_log_kwargs",
                get_job_instance_ip_log_kwargs,
                get_job_instance_ip_log_kwargs_return,
            )
            service_logger.warning(message)
            return {"result": False, "message": message}
        log_content = get_job_instance_ip_log_kwargs_return["data"]["log_content"]
        if log_content:
            log_list.append(str(log_content))
    log_text = "\n".join(log_list)
    return {"result": True, "data": log_text}


def get_sops_var_dict_from_log_text(log_text, service_logger):
    """
    在日志文本中提取全局变量
    :param service_logger:
    :param log_text: 日志文本，如下：
    "<SOPS_VAR>key1:value1</SOPS_VAR>\ngsectl\n-rwxr-xr-x 1 root<SOPS_VAR>key2:value2</SOPS_VAR>\n"
    或者已转义的日志文本
    &lt;SOPS_VAR&gt;key2:value2&lt;/SOPS_VAR&gt;
    :return:
    {"key1": "value1", "key2": "value2"}
    """
    sops_var_dict = {}
    # 支持跨行匹配全局变量
    service_logger.info("search log var with config: {}".format(LOG_VAR_SEARCH_CONFIGS))
    for var_search_config in LOG_VAR_SEARCH_CONFIGS:
        reg = var_search_config["re"]
        excape_reg = reg.replace("<", "&lt;").replace(">", "&gt;")
        kv_sep = var_search_config["kv_sep"]

        sops_key_val_list = re.findall(reg, log_text, re.DOTALL)
        sops_key_val_list.extend(re.findall(excape_reg, log_text, re.DOTALL))
        service_logger.info(f"search log var with sops key val list: {sops_key_val_list}")
        if len(sops_key_val_list) == 0:
            continue
        for sops_key_val in sops_key_val_list:
            if kv_sep not in sops_key_val:
                continue
            sops_key, sops_val = sops_key_val.split(kv_sep, 1)
            # 限制变量名不为空
            if len(sops_key) == 0:
                continue
            sops_var_dict.update({sops_key: sops_val})
    service_logger.info(f"search log var result: {sops_var_dict}")
    return sops_var_dict


def get_job_tagged_ip_dict_complex(
    client, service_logger, job_instance_id, bk_biz_id, job_scope_type=JobBizScopeType.BIZ.value
):
    """根据job步骤执行标签获取 IP 分组(该类型的会返回一个新的IP分组结构)，新的ip分组协议如下
    {
        "name": "JOB执行IP分组",
        "key": "job_tagged_ip_dict",
        "value": {
            "SUCCESS": {
                "DESC": "执行成功",
                "TAGS": {
                    "success-1": "127.0.0.1,127.0.0.1",
                    "success-2": "127.0.0.1,127.0.0.1",
                    "ALL": "127.0.0.1"
                }
            },
            "SCRIPT_FAILED": {
                "DESC": "脚本返回值非0",
                "TAGS": {
                    "failed-1": "127.0.0.1",
                    "failed-2": "127.0.0.1",
                    "ALL": "127.0.0.1"
                }
            },
            "OTHER_FAILED": {
                "desc": "其他报错",
                "tags": {
                    "TASK_TIMEOUT": "127.0.0.1",
                    "LOG_ERROR": "127.0.0.1",
                    "ALL": "127.0.0.1"
                }
            }
        }
    }
    """

    JOB_STEP_IP_RESULT_STATUS_MAP = {
        0: "UNKNOWN_ERROR",
        1: "AGENT_ERROR",
        2: "HOST_NOT_EXIST",
        3: "LAST_SUCCESS",
        9: "SUCCESS",
        11: "FAILED",
        12: "SUBMIT_FAILED",
        13: "TASK_TIMEOUT",
        15: "LOG_ERROR",
        16: "GSE_SCRIPT_TIMEOUT",
        17: "GSE_FILE_TIMEOUT",
        101: "SCRIPT_FAILED",
        102: "SCRIPT_TIMEOUT",
        103: "SCRIPT_TERMINATE",
        104: "SCRIPT_NOT_ZERO_EXIT_CODE",
        202: "COPYFILE_FAILED",
        203: "COPYFILE_SOURCE_FILE_NOT_EXIST",
        301: "FILE_ERROR_UNCLASSIFIED",
        303: "GSE_TIMEOUT",
        310: "GSE_AGENT_ERROR",
        311: "GSE_USER_ERROR",
        312: "GSE_USER_PWD_ERROR",
        320: "GSE_FILE_ERROR",
        321: "GSE_FILE_SIZE_EXCEED",
        329: "GSE_FILE_TASK_ERROR",
        399: "GSE_TASK_ERROR",
        403: "GSE_TASK_TERMINATE_SUCCESS",
        404: "GSE_TASK_TERMINATE_FAILED",
        500: "UNKNOWN",
    }

    kwargs = {
        "bk_scope_type": job_scope_type,
        "bk_scope_id": str(bk_biz_id),
        "bk_biz_id": bk_biz_id,
        "job_instance_id": job_instance_id,
        "return_ip_result": True,
    }
    result = client.jobv3.get_job_instance_status(**kwargs)

    if not result["result"]:
        message = handle_api_error(
            __group_name__,
            "jobv3.get_job_instance_status",
            kwargs,
            result,
        )
        service_logger.warning(message)
        return False, message

    step_instance = result["data"]["step_instance_list"][-1]

    step_ip_result_list = step_instance.get("step_ip_result_list", [])

    success_tags_dict = {}
    success_ips = []

    failed_tags_dict = {}
    failed_ips = []

    others_tags_dict = {}
    others_ips = []

    for step_ip_result in step_ip_result_list:
        tag_key = step_ip_result["tag"]
        status = step_ip_result["status"]
        status_key = JOB_STEP_IP_RESULT_STATUS_MAP.get(status, status)
        ip = get_ip_from_step_ip_result(step_ip_result)

        # 执行成功的分类到执行成功里面，JOB_SUCCESS
        if status == 9:
            success_ips.append(ip)
            if tag_key:
                if tag_key in success_tags_dict:
                    success_tags_dict[tag_key] += f",{ip}"
                else:
                    success_tags_dict[tag_key] = ip
        # 当调用job_failed时，会有失败的tag信息
        elif status == 104:
            failed_ips.append(ip)
            if tag_key:
                if tag_key in failed_tags_dict:
                    failed_tags_dict[tag_key] += f",{ip}"
                else:
                    failed_tags_dict[tag_key] = ip
        else:
            # 其他情况就是失败了
            others_ips.append(ip)
            if tag_key:
                if status_key in others_tags_dict:
                    others_tags_dict[status_key] += f",{ip}"
                else:
                    others_tags_dict[status_key] = ip

    success_tags_dict["ALL"] = ",".join(success_ips)
    failed_tags_dict["ALL"] = ",".join(failed_ips)
    others_tags_dict["ALL"] = ",".join(others_ips)

    tagged_ip_dict = {
        "name": "JOB执行IP分组",
        "key": "job_tagged_ip_dict",
        "value": {
            "SUCCESS": {"DESC": "执行成功", "TAGS": success_tags_dict},
            "SCRIPT_NOT_ZERO_EXIT_CODE": {"DESC": "脚本返回值非零", "TAGS": failed_tags_dict},
            "OTHER_FAILED": {"desc": "其他异常", "TAGS": others_tags_dict},
        },
    }

    return True, tagged_ip_dict
