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
import logging

from pipeline.core.data.expression import ConstantTemplate

from bkflow.space.configs import CallbackHooksConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils.api_client import ApiGwClient

logger = logging.getLogger("root")


def _system_constants_to_mako_str(value):
    """
    将内置系统变量(_system.xxx)转换为可用于mako渲染统计的变量(_system点xxx)
    """
    if isinstance(value, dict):
        for k, v in value.items():
            value[k] = _system_constants_to_mako_str(v)

    if isinstance(value, list):
        for i, v in enumerate(value):
            value[i] = _system_constants_to_mako_str(v)

    if isinstance(value, str):
        return value.replace("_system.", "_system点") if "_system." in value else value

    return value


def _mako_str_to_system_constants(value):
    """
    将用于mako渲染统计的变量(_system点xxx)还原为内置系统变量(_system.xxx)
    """
    if isinstance(value, str):
        return value.replace("_system点", "_system.") if "_system点" in value else value

    return value


def analysis_pipeline_constants_ref(pipeline_tree):
    result = {key: {"activities": [], "conditions": [], "constants": []} for key in pipeline_tree.get("constants", {})}

    def ref_counter(key):
        return result.setdefault("${%s}" % key, {"activities": [], "conditions": [], "constants": []})

    for act_id, act in pipeline_tree.get("activities", {}).items():
        if act["type"] == "SubProcess":
            subproc_consts = act.get("constants", {})
            for key, info in subproc_consts.items():
                value = _system_constants_to_mako_str(info["value"])
                refs = ConstantTemplate(value).get_reference()
                for r in refs:
                    r = _mako_str_to_system_constants(r)
                    ref_counter(r)["activities"].append(act_id)

        elif act["type"] == "ServiceActivity":
            act_data = act.get("component", {}).get("data", {})
            for data_item in act_data.values():
                value = _system_constants_to_mako_str(data_item["value"])
                refs = ConstantTemplate(value).get_reference()
                for r in refs:
                    r = _mako_str_to_system_constants(r)
                    ref_counter(r)["activities"].append(act_id)

    for gateway in pipeline_tree.get("gateways", {}).values():
        if gateway["type"] not in ["ExclusiveGateway", "ConditionalParallelGateway"]:
            continue

        for condition_id, condition in gateway.get("conditions", {}).items():
            value = _system_constants_to_mako_str(condition["evaluate"])
            refs = ConstantTemplate(value).get_reference()
            for r in refs:
                r = _mako_str_to_system_constants(r)
                ref_counter(r)["conditions"].append(condition_id)

    for key, const in pipeline_tree.get("constants", {}).items():
        value = _system_constants_to_mako_str(const.get("value"))
        refs = ConstantTemplate(value).get_reference()
        for r in refs:
            r = _mako_str_to_system_constants(r)
            ref_counter(r)["constants"].append(key)

    return result


def send_callback(space_id, callback_type, data):
    try:
        callback_hooks = SpaceConfig.get_config(space_id, CallbackHooksConfig.name)
        if callback_hooks:
            callback_types = callback_hooks.get("callback_types", [])
            if callback_type not in callback_types:
                logger.info(
                    "[callback] this space id not enabled this type callback. type={}, data={}, callback={}".format(
                        callback_type, data, callback_types
                    )
                )
                return
            callback_url = callback_hooks.get("url", "")
            if callback_url:
                logger.info("[send_callback] start callback, callback_type={}, data={}".format(callback_type, data))
                resp = ApiGwClient(from_apigw_check=True).request(
                    url=callback_url, method="POST", data=data, headers=None
                )
                if not resp.result:
                    logger.error(
                        "[send_callback] callback error, resp result is not True, message={}".format(resp.message)
                    )
    except Exception as e:
        # 回调不保证成功，但是不会影响到正常更新的逻辑
        logger.exception(
            "[send_callback] send_callback error, callback_type={}, data={}, err={}".format(callback_type, data, e)
        )
        return
