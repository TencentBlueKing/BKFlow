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

from bkflow.admin.models import ModuleInfo
from bkflow.contrib.api.client import BaseComponentClient


class TaskComponentClient(BaseComponentClient):
    MODULE_TYPE = "TASK"

    def __init__(self, space_id=0, from_superuser=False):
        # space_id 等于0时表示默认配置
        super().__init__()
        self.from_superuser = from_superuser
        self.space_id = space_id
        self.module_info = self.get_module_info()

    def get_module_info(self):
        try:
            return ModuleInfo.objects.get(type=self.MODULE_TYPE, space_id=self.space_id)
        except ModuleInfo.DoesNotExist:
            return ModuleInfo.objects.get(type=self.MODULE_TYPE, space_id=0)

    def _pre_process_headers(self, headers):
        if not headers:
            headers = {
                "Content-Type": "application/json",
                settings.APP_INTERNAL_TOKEN_HEADER_KEY: self.module_info.token,
            }
        else:
            headers[settings.APP_INTERNAL_TOKEN_HEADER_KEY] = self.module_info.token

        if self.space_id is not None:
            headers[settings.APP_INTERNAL_SPACE_ID_HEADER_KEY] = str(self.space_id)
        headers[settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY] = "1" if self.from_superuser else "0"

        return headers

    def _get_task_url(self, api_name):
        return "{}/{}".format(self.module_info.url, api_name)

    def task_list(self, data):
        return self._request(method="get", url=self._get_task_url("task/"), data=data)

    def update_labels(self, task_id, data):
        return self._request(method="post", url=self._get_task_url("task/{}/update_labels/".format(task_id)), data=data)

    def get_task_label_ref_count(self, space_id, label_ids):
        return self._request(
            method="get",
            url=self._get_task_url(
                "task/get_task_label_ref_count/?space_id={}&label_ids={}".format(space_id, label_ids)
            ),
            data=None,
        )

    def delete_task_label_relation(self, data):
        return self._request(
            method="post",
            url=self._get_task_url("task/delete_task_label_relation/"),
            data=data,
        )

    def create_task(self, data):
        return self._request(method="post", url=self._get_task_url("task/"), data=data)

    def get_task_detail(self, task_id, data=None):
        return self._request(method="get", url=self._get_task_url("task/{}/".format(task_id)), data=data)

    def delete_task(self, task_id):
        return self._request(method="delete", url=self._get_task_url("task/{}/".format(task_id)), data=None)

    def get_task_states(self, task_id, data=None):
        return self._request(method="get", url=self._get_task_url("task/{}/get_states/".format(task_id)), data=data)

    def get_task_mock_data(self, task_id, data=None):
        return self._request(
            method="get", url=self._get_task_url("task/{}/get_task_mock_data/".format(task_id)), data=data
        )

    def operate_task(self, task_id, operate, data=None):
        return self._request(
            method="post", url=self._get_task_url("task/{}/operate/{}/".format(task_id, operate)), data=data
        )

    def get_task_node_detail(self, task_id, node_id, username="", data=None):
        return self._request(
            method="get",
            url=self._get_task_url("task/{}/get_task_node_detail/{}/?username={}".format(task_id, node_id, username)),
            data=data,
        )

    def node_operate(self, task_id, node_id, operation, data):
        return self._request(
            method="post",
            url=self._get_task_url("task/{}/node_operate/{}/{}/".format(task_id, node_id, operation)),
            data=data,
        )

    def get_task_node_log(self, task_id, node_id, version, data=None):
        return self._request(
            method="get",
            url=self._get_task_url("task/{}/get_task_node_log/{}/{}/".format(task_id, node_id, version)),
            data=data,
        )

    def render_current_constants(self, task_id):
        return self._request(
            method="get", url=self._get_task_url("task/{}/render_current_constants/".format(task_id)), data=None
        )

    def render_context_with_node_outputs(self, task_id, data=None):
        return self._request(
            method="post",
            url=self._get_task_url("task/{}/render_context_with_node_outputs/".format(task_id)),
            data=data,
        )

    def get_task_operation_record(self, task_id, data=None):
        return self._request(
            method="get", url=self._get_task_url("task/{}/get_task_operation_record/".format(task_id)), data=data
        )

    def get_node_snapshot_config(self, task_id, data=None):
        return self._request(
            method="get", url=self._get_task_url("task/{}/get_node_snapshot_config/".format(task_id)), data=data
        )

    def get_tasks_states(self, data=None):
        return self._request(method="post", url=self._get_task_url("task/get_tasks_states/"), data=data)

    def trigger_engine_admin_action(self, instance_id, action, data=None):
        return self._request(
            method="post",
            url=self._get_task_url(f"task_engine_admin/api/v1/bamboo_engine/{action}/{instance_id}/"),
            data=data,
        )

    def batch_delete_tasks(self, data):
        return self._request(method="post", url=self._get_task_url("task/batch_delete_tasks/"), data=data)

    def create_periodic_task(self, data):
        return self._request(method="post", url=self._get_task_url("task/periodic_task/"), data=data)

    def update_periodic_task(self, data):
        return self._request(method="post", url=self._get_task_url("task/periodic_task/update/"), data=data)

    def batch_delete_periodic_task(self, data):
        return self._request(method="post", url=self._get_task_url("task/periodic_task/batch_delete/"), data=data)

    def get_engine_config(self, data):
        return self._request(method="get", url=self._get_task_url("task/get_engine_config/"), data=data)

    def upsert_engine_config(self, data):
        return self._request(method="post", url=self._get_task_url("task/upsert_engine_config/"), data=data)

    def delete_engine_config(self, data):
        return self._request(method="delete", url=self._get_task_url("task/delete_engine_config/"), data=data)
