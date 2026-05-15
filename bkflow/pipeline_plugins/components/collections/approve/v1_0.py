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


import traceback

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import StringItemSchema

__group_name__ = _("蓝鲸服务(BK)")

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.pipeline_plugins.utils import get_node_callback_url
from bkflow.utils.handlers import handle_api_error
from packages.bkapi.bk_itsm4.shortcuts import get_client_by_username


class ApproveService(BKFlowBaseService):
    plugin_name = "approve"
    __need_schedule__ = True

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("审核人"),
                key="bk_verifier",
                type="string",
                schema=StringItemSchema(description=_("审核人,多个用英文逗号`,`分隔")),
            ),
            self.InputItem(
                name=_("审核标题"),
                key="bk_approve_title",
                type="string",
                schema=StringItemSchema(description=_("审核标题")),
            ),
            self.InputItem(
                name=_("审核内容"),
                key="bk_approve_content",
                type="string",
                schema=StringItemSchema(description=_("通知的标题")),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(name=_("单据sn"), key="sn", type="string", schema=StringItemSchema(description=_("单据sn"))),
            self.OutputItem(
                name=_("审核结果"),
                key="approve_result",
                type="string",
                schema=StringItemSchema(description=_("审核结果")),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        from bkflow.task.celery.tasks import send_task_message
        from bkflow.task.utils import PENDING_PROCESSING

        executor = parent_data.get_one_of_inputs("executor")
        tenant_id = parent_data.get_one_of_inputs("tenant_id")
        client = get_client_by_username(username=executor, stage=settings.BK_APIGW_STAGE_NAME)

        verifier = data.get_one_of_inputs("bk_verifier")
        title = data.get_one_of_inputs("bk_approve_title")
        approve_content = data.get_one_of_inputs("bk_approve_content")

        verifier = verifier.replace(" ", "")

        kwargs = {
            "workflow_key": f"{tenant_id}_bk_flow_engine_workflows_key_100001_v1",
            "form_data": {
                "ticket__title": title,
                "textarea_content": approve_content,
                "multiUser_approver": verifier.split(","),
            },
            "system_id": settings.APP_CODE,
            "callback_url": get_node_callback_url(self.root_pipeline_id, self.id, getattr(self, "version", "")),
            "options": {},
        }
        result = client.api.create_ticket(
            kwargs, headers={"X-Bk-Tenant-Id": tenant_id, "SYSTEM-TOKEN": settings.SECRET_KEY}
        )

        if not result["result"]:
            message = handle_api_error(__group_name__, "itsm.create_ticket", kwargs, result)
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        data.outputs.sn = result["data"]["sn"]
        data.outputs.id = result["data"]["id"]
        task_id: int = parent_data.get_one_of_inputs("task_id")
        send_task_message.delay(
            task_id=task_id,
            msg_type=PENDING_PROCESSING,
        )

        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        try:
            rejected_block = data.get_one_of_inputs("rejected_block", True)
            approve_result = callback_data["ticket"]["approve_result"]
            data.outputs.approve_result = "通过" if approve_result else "拒绝"
            # 审核拒绝不阻塞
            if not approve_result and not rejected_block:
                return True
            return approve_result
        except Exception as e:
            err_msg = "get Special Approve Component result failed: {}, err: {}"
            self.logger.error(err_msg.format(callback_data, traceback.format_exc()))
            data.outputs.ex_data = err_msg.format(callback_data, e)
            return False


class ApproveComponent(Component):
    name = _("审批")
    code = "bk_approve"
    bound_service = ApproveService
    version = "v1.0"
    form = "%scomponents/approve/v1_0.js" % settings.STATIC_URL
