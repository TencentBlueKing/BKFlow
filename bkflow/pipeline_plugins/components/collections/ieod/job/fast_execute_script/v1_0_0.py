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
    get_job_instance_url,
    get_job_sops_var_dict,
    get_job_tagged_ip_dict_complex,
    job_handle_api_error,
)

__group_name__ = _("作业平台(JOB)")


class JobFastExecuteScriptService(BKFlowBaseService, GetJobHistoryResultMixin):
    need_get_sops_var = True
    need_is_tagged_ip = True

    __need_schedule__ = True
    reload_outputs = True
    biz_scope_type = JobBizScopeType.BIZ.value

    def is_need_log_outputs_even_fail(self, data):
        """
        默认开启失败时提取变量
        """
        return True

    def get_tagged_ip_dict(self, data, parent_data, job_instance_id):
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
                        "输出日志中提取的全局变量，日志中形如 <SOPS_VAR>key:val</SOPS_VAR> 的变量会被提取到 log_outputs['key'] 中，值为 val"
                    ),
                    property_schemas={
                        "name": StringItemSchema(description=_("全局变量名称")),
                        "value": StringItemSchema(description=_("全局变量值")),
                    },
                ),
            ),
            self.OutputItem(
                name=_("JOB执行IP分组"),
                key="job_tagged_ip_dict",
                type="string",
                schema=StringItemSchema(
                    description=_(
                        '按照执行结果将 IP 进行分组：1. 使用 job_tagged_ip_dict["value"]["SUCCESS"]["TAGS"]["ALL"]  获取「执行成功」的 IP， '
                        "ALL 代表所有 IP，可指定分组名获取特定分组的 IP ；"
                        '2. 使用 job_tagged_ip_dict["value"]["SCRIPT_NOT_ZERO_EXIT_CODE"]["TAGS"]["ALL"]'
                        " 获取「脚本返回值非零」的 IP"
                    )
                ),
            ),
        ]

    def get_target_server(self, client, biz_cc_id, ip_info):
        host_property_filter = {
            "condition": "AND",
            "rules": [
                {
                    "field": "bk_host_innerip",
                    "operator": "in",
                    "value": ip_info,
                }
            ],
        }
        path_params = {"bk_biz_id": biz_cc_id}
        list_biz_hosts_kwargs = {
            "page": {"start": 0, "limit": 10},
            "host_property_filter": host_property_filter,
        }

        ip_results = client.bkcmdb.list_biz_hosts(path_params=path_params, **list_biz_hosts_kwargs)

        if not ip_results["result"] or not ip_results["data"]["count"]:
            self.logger.error("获取ip信息失败 %s", ip_results["message"])
            return None
        target_server = {
            "ip_list": [
                {"bk_cloud_id": ip_data["bk_cloud_id"], "ip": ip_data["bk_host_innerip"]}
                for ip_data in ip_results["data"]["info"]
            ]
        }

        return target_server

    def plugin_execute(self, data, parent_data):
        job_success_id = data.get_one_of_inputs("job_success_id")
        if job_success_id:
            history_result = self.get_job_history_result(data, parent_data)
            self.logger.info(history_result)
            if history_result:
                self.__need_schedule__ = False
            return history_result

        executor = parent_data.get_one_of_inputs("executor")
        client = get_client_by_user(executor)
        if parent_data.get_one_of_inputs("language"):
            setattr(client, "language", parent_data.get_one_of_inputs("language"))
            translation.activate(parent_data.get_one_of_inputs("language"))
        biz_cc_id = data.get_one_of_inputs("biz_cc_id", parent_data.get_one_of_inputs("biz_cc_id"))
        script_source = data.get_one_of_inputs("job_script_source")
        ip_info = data.get_one_of_inputs("job_ip_list")
        job_rolling_config = data.get_one_of_inputs("job_rolling_config", {})
        job_rolling_execute = job_rolling_config.get("job_rolling_execute", None)
        # 获取 IP

        target_server = self.get_target_server(client, biz_cc_id, ip_info.split())
        if not target_server:
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
                func = client.jobv3.get_script_list
            else:
                func = client.jobv3.get_public_script_list

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
        job_result = client.jobv3.fast_execute_script(**job_kwargs)
        self.logger.info("job_result: {result}, job_kwargs: {kwargs}".format(result=job_result, kwargs=job_kwargs))
        if job_result["result"]:
            job_instance_id = job_result["data"]["job_instance_id"]
            data.outputs.job_inst_id = job_instance_id
            data.outputs.job_inst_name = job_result["data"]["job_instance_name"]
            data.outputs.job_inst_url = get_job_instance_url(biz_cc_id, job_instance_id)
            data.outputs.client = client
            return True
        else:
            message = job_handle_api_error("jobv3.fast_execute_script", job_kwargs, job_result)
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

    def plugin_schedule(self, data, parent_data, callback_data=None):
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
        need_log_outputs_even_fail = self.is_need_log_outputs_even_fail(data)
        # 失败情况下也需要要进行ip tag分组
        if job_success or need_log_outputs_even_fail or self.need_is_tagged_ip:

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

            if self.reload_outputs:

                client = data.outputs.client

                # 判断是否对IP进行Tag分组, 兼容之前的配置，默认从inputs拿
                is_tagged_ip = data.get_one_of_inputs("is_tagged_ip", False)
                tagged_ip_dict = {}
                if is_tagged_ip or self.need_is_tagged_ip:
                    result, tagged_ip_dict = self.get_tagged_ip_dict(data, parent_data, job_instance_id)
                    if not result:
                        self.logger.error(tagged_ip_dict)
                        data.outputs.ex_data = tagged_ip_dict
                        self.finish_schedule()
                        return False

                if "is_tagged_ip" in data.get_inputs() or self.need_is_tagged_ip:
                    data.set_outputs("job_tagged_ip_dict", tagged_ip_dict)

                bk_biz_id = data.get_one_of_inputs("biz_cc_id", parent_data.get_one_of_inputs("biz_cc_id"))
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

            # 无需提取全局变量的Service直接返回
            if not self.need_get_sops_var and not need_log_outputs_even_fail:
                self.finish_schedule()
                return True if job_success else False
            get_job_sops_var_dict_return = get_job_sops_var_dict(
                data.outputs.client,
                self.logger,
                job_instance_id,
                data.get_one_of_inputs("biz_cc_id", parent_data.get_one_of_inputs("biz_cc_id")),
                self.biz_scope_type,
            )
            if not get_job_sops_var_dict_return["result"]:
                self.logger.error(
                    _("{group}.{job_service_name}: 提取日志失败，{message}").format(
                        group=__group_name__,
                        job_service_name=self.__class__.__name__,
                        message=get_job_sops_var_dict_return["message"],
                    )
                )
                data.set_outputs("log_outputs", {})
                self.finish_schedule()
                return False

            log_outputs = get_job_sops_var_dict_return["data"]
            self.logger.info(
                _("{group}.{job_service_name}：输出日志提取变量为：{log_outputs}").format(
                    group=__group_name__, job_service_name=self.__class__.__name__, log_outputs=log_outputs
                )
            )
            data.set_outputs("log_outputs", log_outputs)
            self.finish_schedule()
            return True if job_success else False
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
    form = "%scomponents/job/v1_0_0.js" % settings.STATIC_URL
    desc = _("快速执行脚本")
