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

import base64
import re
import traceback

from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.conf import settings
from pipeline.core.flow.io import (
    BooleanItemSchema,
    IntItemSchema,
    ObjectItemSchema,
    StringItemSchema,
)

from bkflow.constants import JobBizScopeType
from bkflow.exceptions import APIRequestError
from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.pipeline_plugins.utils import get_node_callback_url
from bkflow.utils.requests import batch_request
from client.shortcuts import get_client_by_user

from ..job import GetJobHistoryResultMixin
from ..utils import (
    JOB_SUCCESS,
    JOB_VAR_TYPE_IP,
    get_job_bkflow_var_dict,
    get_job_instance_url,
    get_job_tagged_ip_dict_complex,
    job_handle_api_error,
)

__group_name__ = _("作业平台(JOB)")


class JobFastExecuteScriptService(BKFlowBaseService, GetJobHistoryResultMixin):

    __need_schedule__ = True
    biz_scope_type = JobBizScopeType.BIZ.value
    ip_pattern = re.compile(
        r"(?:(?P<region>\d+):)?(?P<ip>(?:25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})){3})$"  # noqa: E501
    )

    def get_tagged_ip_dict(self, data, parent_data, job_instance_id):
        """
        暂时未启用 ip 分组功能
        """
        result, tagged_ip_dict = get_job_tagged_ip_dict_complex(
            data.outputs.client,
            self.logger,
            job_instance_id,
            data.get_one_of_inputs("biz_cc_id", parent_data.get_one_of_inputs("biz_cc_id")),
            job_scope_type=self.biz_scope_type,
        )
        return result, tagged_ip_dict

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("业务 ID"),
                key="biz_cc_id",
                type="string",
                schema=StringItemSchema(description=_("当前操作所属的 CMDB 业务 ID")),
            ),
            self.InputItem(
                name=_("脚本来源"),
                key="job_script_source",
                type="string",
                schema=StringItemSchema(
                    description=_("待执行的脚本来源，手动(manual)，业务脚本(general)，公共脚本(public)"),
                    enum=["manual", "general", "public"],
                ),
            ),
            self.InputItem(
                name=_("脚本类型"),
                key="job_script_type",
                type="string",
                schema=StringItemSchema(
                    description=_("待执行的脚本类型：shell(1) bat(2) perl(3) python(4) powershell(5)" "，仅在脚本来源为手动时生效"),
                    enum=["1", "2", "3", "4", "5"],
                ),
            ),
            self.InputItem(
                name=_("脚本内容"),
                key="job_content",
                type="string",
                schema=StringItemSchema(description=_("待执行的脚本内容，仅在脚本来源为手动时生效")),
            ),
            self.InputItem(
                name=_("公共脚本"),
                key="job_script_list_public",
                type="string",
                schema=StringItemSchema(description=_("待执行的公共脚本 ID，仅在脚本来源为公共脚本时生效")),
            ),
            self.InputItem(
                name=_("业务脚本"),
                key="job_script_list_general",
                type="string",
                schema=StringItemSchema(description=_("待执行的业务脚本 ID，仅在脚本来源为业务脚本时生效")),
            ),
            self.InputItem(
                name=_("脚本执行参数"),
                key="job_script_param",
                type="string",
                schema=StringItemSchema(description=_("脚本执行参数")),
            ),
            self.InputItem(
                name=_("目标 IP"),
                key="job_ip_list",
                type="string",
                schema=StringItemSchema(description=_("执行脚本的目标机器 IP，多个用英文逗号 `,` 分隔")),
            ),
            self.InputItem(
                name=_("目标账户"),
                key="job_account",
                type="string",
                schema=StringItemSchema(description=_("执行脚本的目标机器账户")),
            ),
            self.InputItem(
                name=_("滚动执行"),
                key="job_rolling_execute",
                type="boolean",
                schema=BooleanItemSchema(description=_("是否开启滚动执行")),
            ),
            self.InputItem(
                name=_("滚动策略"),
                key="job_rolling_expression",
                type="string",
                schema=StringItemSchema(description=_("滚动策略，仅在滚动执行开启时生效")),
            ),
            self.InputItem(
                name=_("滚动机制"),
                key="job_rolling_mode",
                type="string",
                schema=StringItemSchema(description=_("滚动机制，仅在滚动执行开启时生效")),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("JOB任务ID"),
                key="job_inst_id",
                type="int",
                schema=IntItemSchema(description=_("提交的任务在 JOB 平台的实例 ID")),
            ),
            self.OutputItem(
                name=_("JOB任务链接"),
                key="job_inst_url",
                type="string",
                schema=StringItemSchema(description=_("提交的任务在 JOB 平台的 URL")),
            ),
            self.OutputItem(
                name=_("JOB全局变量"),
                key="log_outputs",
                type="object",
                schema=ObjectItemSchema(
                    description=_(
                        "输出日志中提取的全局变量，日志中形如 <BKFLOW_VAR>key:val</BKFLOW_VAR> 的变量会被提取到 log_outputs['key'] 中，值为 val"
                    ),
                    property_schemas={
                        "name": StringItemSchema(description=_("全局变量名称")),
                        "value": StringItemSchema(description=_("全局变量值")),
                    },
                ),
            ),
        ]

    def parse_ip_info(self, ip_info_list):
        parsed_ips = []
        # 更严格的正则表达式来匹配 IPv4 地址

        for ip_info in ip_info_list:
            match = self.ip_pattern.match(ip_info)
            if match:
                region = match.group("region") if match.group("region") else "0"
                ip = match.group("ip")
                parsed_ips.append([region, ip])
            else:
                # 处理不符合格式的情况
                raise ValueError(f"不正确的管控区域和ip格式: {ip_info}")

        return parsed_ips

    def get_target_server(self, client, biz_cc_id, ip_info: list):
        """
        根据业务和传入的主机信息进行检查校验 支持云管控区域 以逗号分隔一组对象 以冒号分隔 管控区域:主机ip
        """
        try:
            ips = self.parse_ip_info(ip_info)
        except ValueError as e:
            self.logger.error(str(e))
            return None, str(e)
        err_msg = "目标主机未找到"
        host_property_filter = {
            "condition": "OR",
            "rules": [
                {
                    "condition": "AND",
                    "rules": [
                        {
                            "field": "bk_host_innerip",
                            "operator": "equal",
                            "value": ip,
                        },
                        {"field": "bk_cloud_id", "operator": "equal", "value": int(cloud_id)},
                    ],
                }
                for cloud_id, ip in ips
            ],
        }
        path_params = {"bk_biz_id": biz_cc_id}
        list_biz_hosts_kwargs = {
            "page": {"start": 0, "limit": 10},
            "host_property_filter": host_property_filter,
        }

        ip_results = client.bkcmdb.list_biz_hosts(path_params=path_params, **list_biz_hosts_kwargs)

        if not ip_results["result"] or not ip_results["data"]["count"]:
            err_msg = f"获取ip信息失败: {ip_results['message']}"
            self.logger.error(err_msg)
            return None, err_msg
        target_server = {
            "ip_list": [
                {"bk_cloud_id": ip_data["bk_cloud_id"], "ip": ip_data["bk_host_innerip"]}
                for ip_data in ip_results["data"]["info"]
            ]
        }

        return target_server, err_msg

    def plugin_execute(self, data, parent_data):
        """
        Job 插件执行逻辑 暂未启用历史成功记录功能
        """
        executor = parent_data.get_one_of_inputs("executor")
        job_client = get_client_by_user(executor, stage=settings.BK_JOB_APIGW_STAGE)
        cc_client = get_client_by_user(executor, stage=settings.BK_CMDB_APIGW_STAGE)
        if parent_data.get_one_of_inputs("language"):
            setattr(job_client, "language", parent_data.get_one_of_inputs("language"))
            translation.activate(parent_data.get_one_of_inputs("language"))
        biz_cc_id = data.get_one_of_inputs("biz_cc_id")
        script_source = data.get_one_of_inputs("job_script_source")
        ip_info = data.get_one_of_inputs("job_ip_list")
        job_rolling_config = data.get_one_of_inputs("job_rolling_config", {})
        job_rolling_execute = job_rolling_config.get("job_rolling_execute", None)
        # 获取 IP

        target_server, err_msg = self.get_target_server(cc_client, biz_cc_id, ip_info.split(","))
        if not target_server:
            data.outputs.ex_data = f"获取目标主机失败: {err_msg}"
            return False

        space_id = parent_data.get_one_of_inputs("task_space_id")
        task_id = parent_data.get_one_of_inputs("task_id")
        callback_url = get_node_callback_url(space_id, task_id, self.id, getattr(self, "version", ""))
        job_kwargs = {
            "bk_scope_type": JobBizScopeType.BIZ.value,
            "bk_scope_id": str(biz_cc_id),
            "bk_biz_id": biz_cc_id,
            "timeout": data.get_one_of_inputs("job_script_timeout"),
            "account_alias": data.get_one_of_inputs("job_account").strip(),
            "target_server": target_server,
            "callback_url": callback_url,
        }

        # 如果开启了滚动执行，填充rolling_config配置
        if job_rolling_execute:
            # 滚动策略
            job_rolling_expression = job_rolling_config.get("job_rolling_expression")
            # 滚动机制
            job_rolling_mode = job_rolling_config.get("job_rolling_mode")
            rolling_config = {"expression": job_rolling_expression, "mode": job_rolling_mode}
            job_kwargs.update({"rolling_config": rolling_config})

        script_param = str(data.get_one_of_inputs("job_script_param"))

        if script_param:
            job_kwargs.update({"script_param": base64.b64encode(script_param.encode("utf-8")).decode("utf-8")})

        if script_source in ["general", "public"]:
            script_name = data.get_one_of_inputs("job_script_list_{}".format(script_source))
            kwargs = {"name": script_name}
            if script_source == "general":
                kwargs.update(
                    {"bk_scope_type": JobBizScopeType.BIZ.value, "bk_scope_id": str(biz_cc_id), "bk_biz_id": biz_cc_id}
                )
                func = job_client.jobv3.get_script_list
            else:
                func = job_client.jobv3.get_public_script_list

            try:
                script_list = batch_request(
                    func=func,
                    params=kwargs,
                    get_data=lambda x: x["data"]["data"],
                    get_count=lambda x: x["data"]["total"],
                    page_param={"cur_page_param": "start", "page_size_param": "length"},
                    is_page_merge=True,
                )
            except APIRequestError as e:
                message = str(e)
                self.logger.error(str(e))
                data.outputs.ex_data = message
                return False

            # job 脚本名称使用的是模糊匹配，这里需要做一次精确匹配
            selected_script = None
            for script in script_list:
                if script["name"] == script_name:
                    selected_script = script
                    break

            if not selected_script:
                api_name = "jobv3.get_script_list" if script_source == "general" else "jobv3.get_public_script_list"
                message = job_handle_api_error(api_name, job_kwargs, {})
                script_type = "业务脚本" if script_source == "general" else "公共脚本"
                message += (
                    f"快速执行脚本启动失败: [作业平台]未找到名称:{script_name}的{script_type}, "
                    f"现有脚本: {[script['name'] for script in script_list]}, 请检查配置"
                )
                message = _(message)
                self.logger.error(message)
                data.outputs.ex_data = message
                return False
            self.logger.info(selected_script)
            script_id = selected_script["id"]
            job_kwargs.update({"script_id": script_id})
        else:
            job_kwargs.update(
                {
                    "script_language": data.get_one_of_inputs("job_script_type"),
                    "script_content": base64.b64encode(data.get_one_of_inputs("job_content").encode("utf-8")).decode(
                        "utf-8"
                    ),
                }
            )
        job_result = job_client.jobv3.fast_execute_script(**job_kwargs)
        self.logger.info("job_result: {result}, job_kwargs: {kwargs}".format(result=job_result, kwargs=job_kwargs))
        if job_result["result"]:
            job_instance_id = job_result["data"]["job_instance_id"]
            data.outputs.job_inst_id = job_instance_id
            data.outputs.job_inst_name = job_result["data"]["job_instance_name"]
            data.outputs.job_inst_url = get_job_instance_url(job_instance_id)
            data.outputs.client = job_client
            return True
        else:
            message = job_handle_api_error("jobv3.fast_execute_script", job_kwargs, job_result)
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

    def plugin_schedule(self, data, parent_data, callback_data=None):
        """
        插件调度逻辑 回调时执行 检查执行状态 进行 ip 分组并提取对应日志和变量
        """
        try:
            job_instance_id = callback_data.get("job_instance_id", None)
            status = callback_data.get("status", None)
        except Exception as e:
            err_msg = "invalid callback_data: {}, err: {}"
            self.logger.error(err_msg.format(callback_data, traceback.format_exc()))
            data.outputs.ex_data = err_msg.format(callback_data, e)
            return False

        if not job_instance_id or not status:
            data.outputs.ex_data = "invalid callback_data, job_instance_id: %s, status: %s" % (job_instance_id, status)
            self.finish_schedule()
            return False

        job_success = status in JOB_SUCCESS
        # 失败情况下也需要要进行ip tag分组
        if job_success:

            if not job_success:
                data.set_outputs(
                    "ex_data",
                    {
                        "exception_msg": _(
                            "任务执行失败，<a href='{job_inst_url}' target='_blank'>前往作业平台(JOB)查看详情</a>"
                        ).format(job_inst_url=data.outputs.job_inst_url),
                        "task_inst_id": job_instance_id,
                        "show_ip_log": True,
                    },
                )
            client = data.outputs.client

            bk_biz_id = data.get_one_of_inputs("biz_cc_id")
            # 全局变量重载
            get_var_kwargs = {
                "bk_scope_type": self.biz_scope_type,
                "bk_scope_id": str(bk_biz_id),
                "bk_biz_id": bk_biz_id,
                "job_instance_id": job_instance_id,
            }
            global_var_result = client.jobv3.get_job_instance_global_var_value(**get_var_kwargs)
            self.logger.info("get_job_instance_global_var_value return: {}".format(global_var_result))

            if not global_var_result["result"]:
                message = job_handle_api_error(
                    "jobv3.get_job_instance_global_var_value",
                    get_var_kwargs,
                    global_var_result,
                )
                self.logger.error(message)
                data.outputs.ex_data = message
                self.finish_schedule()
                return False

            global_var_list = global_var_result["data"].get("step_instance_var_list", [])
            if global_var_list:
                for global_var in global_var_list[-1]["global_var_list"] or []:
                    if global_var["type"] != JOB_VAR_TYPE_IP:
                        data.set_outputs(global_var["name"], global_var["value"])

            get_job_bkflow_var_dict_return = get_job_bkflow_var_dict(
                client,
                self.logger,
                job_instance_id,
                data.get_one_of_inputs("biz_cc_id"),
                self.biz_scope_type,
            )
            if not get_job_bkflow_var_dict_return["result"]:
                message = _("{group}.{job_service_name}: 提取日志失败，{message}").format(
                    group=__group_name__,
                    job_service_name=self.__class__.__name__,
                    message=get_job_bkflow_var_dict_return["message"],
                )
                self.logger.error(message)
                data.set_outputs("log_outputs", {})
                data.outputs.ex_data = message
                self.finish_schedule()
                return False

            log_outputs = get_job_bkflow_var_dict_return["data"]
            message = _("{group}.{job_service_name}：输出日志提取变量为：{log_outputs}").format(
                group=__group_name__, job_service_name=self.__class__.__name__, log_outputs=log_outputs
            )
            self.logger.info(message)
            data.set_outputs("log_outputs", log_outputs)
            self.finish_schedule()
            return True
        else:
            data.set_outputs(
                "ex_data",
                {
                    "exception_msg": _("任务执行失败，<a href='{job_inst_url}' target='_blank'>前往作业平台(JOB)查看详情</a>").format(
                        job_inst_url=data.outputs.job_inst_url
                    ),
                    "task_inst_id": job_instance_id,
                    "show_ip_log": True,
                },
            )
            self.finish_schedule()
            return False


class JobFastExecuteScriptComponent(Component):
    name = _("快速执行脚本")
    code = "job_fast_execute_script"
    bound_service = JobFastExecuteScriptService
    version = "v1.0.0"
    form = "%scomponents/ieod/job/fast_execute_scripts/v1_0_0.js" % settings.STATIC_URL
    desc = _("快速执行脚本")
