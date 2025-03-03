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
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from bkflow.constants import JobBizScopeType
from bkflow.utils.handlers import handle_api_error
from client.shortcuts import get_client_by_user

from .utils import JOB_SUCCESS, get_job_bkflow_var_dict

__group_name__ = _("作业平台(JOB)")


class GetJobHistoryResultMixin:
    """
    公共类 Job 成功历史记录 暂未启用
    """

    def get_job_history_result(self, data, parent_data):
        # get job_instance[job_success_id] execute status
        job_success_id = data.get_one_of_inputs("job_success_id")
        client = get_client_by_user(parent_data.inputs.executor, stage=settings.BK_JOB_APIGW_STAGE)
        bk_scope_type = getattr(self, "biz_scope_type", JobBizScopeType.BIZ.value)
        job_kwargs = {
            "bk_scope_type": bk_scope_type,
            "bk_scope_id": str(data.inputs.biz_cc_id),
            "bk_biz_id": data.inputs.biz_cc_id,
            "job_instance_id": job_success_id,
        }
        job_result = client.jobv3.get_job_instance_status(**job_kwargs)

        if not job_result["result"]:
            message = handle_api_error(
                __group_name__,
                "jobv3.get_job_instance_status",
                job_kwargs,
                job_result,
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            self.logger.info(data.outputs)
            return False

        # judge success status
        if job_result["data"]["job_instance"]["status"] not in JOB_SUCCESS:
            message = _(f"执行历史请求失败: 任务实例[ID: {job_success_id}], 异常信息: {job_result['result']} | get_job_history_result")
            self.logger.error(message)
            data.outputs.ex_data = message
            self.logger.info(data.outputs)
            return False

        # get job_var
        if not self.need_get_bkflow_var:
            self.logger.info(data.outputs)
            return True

        get_job_bkflow_var_dict_return = get_job_bkflow_var_dict(
            client,
            self.logger,
            job_success_id,
            data.get_one_of_inputs("biz_cc_id", parent_data.inputs.biz_cc_id),
        )
        if not get_job_bkflow_var_dict_return["result"]:
            self.logger.error(
                _("{group}.{job_service_name}: 提取日志失败，{message}").format(
                    group=__group_name__,
                    job_service_name=self.__class__.__name__,
                    message=get_job_bkflow_var_dict_return["message"],
                )
            )
            data.set_outputs("log_outputs", {})
            self.logger.info(data.outputs)
            return False
        log_outputs = get_job_bkflow_var_dict_return["data"]
        self.logger.info(
            _("{group}.{job_service_name}：输出日志提取变量为：{log_outputs}").format(
                group=__group_name__, job_service_name=self.__class__.__name__, log_outputs=log_outputs
            )
        )
        data.set_outputs("log_outputs", log_outputs)
        self.logger.info(data.outputs)
        return True
