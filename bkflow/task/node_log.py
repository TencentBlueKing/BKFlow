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
from abc import ABCMeta, abstractmethod
from urllib.parse import urlencode

import requests
from django.conf import settings
from pipeline.eri.runtime import BambooDjangoRuntime

logger = logging.getLogger("root")


class BaseNodeLogDataSource(metaclass=ABCMeta):
    @abstractmethod
    def fetch_node_logs(self, node_id, version_id, *args, **kwargs):
        raise NotImplementedError()


class PaaS3NodeLogDataSource(BaseNodeLogDataSource):
    def __init__(self):
        module_name = settings.NODE_LOG_DATA_SOURCE_CONFIG.get("module_name", "pipeline")
        self.url = settings.NODE_LOG_DATA_SOURCE_CONFIG["url"].format(module_name=module_name, code=settings.APP_CODE)
        self.headers = {
            "X-Bkapi-Authorization": json.dumps(
                {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}
            ),
            "Content-Type": "application/json",
        }
        self.private_token = settings.PAASV3_APIGW_API_TOKEN

    def fetch_node_logs(self, node_id, version_id, *args, **kwargs):
        page, page_size = kwargs.get("page", 1), kwargs.get("page_size", 30)
        url_params = {
            "page": page,
            "page_size": page_size,
            "log_type": "STRUCTURED",
            "time_range": "7d",
        }
        if self.private_token:
            url_params.update({"private_token": self.private_token})
        url = self.url.rstrip("/") + f"/?{urlencode(url_params)}"
        payload = {"query": {"query_string": f"__ext_json.node_id:{node_id} AND __ext_json.version:{version_id}"}}
        response = requests.get(url, headers=self.headers, data=json.dumps(payload))
        logger.info(
            f"[PaaS3NodeLogDataSource fetch_node_logs] request {url} with payload {payload} and "
            f"response status_code {response.status_code} and content {response.text}."
        )

        if response.status_code != 200:
            return {"result": False, "data": None, "message": response.text}

        res_data = response.json()
        page_info, logs = (
            res_data["data"]["page"],
            "\n".join([f'{log["ts"]}: {log["message"]}' for log in res_data["data"]["logs"]]),
        )
        return {"result": True, "data": {"logs": logs, "page_info": page_info}, "message": ""}


class DatabaseNodeLogDataSource(BaseNodeLogDataSource):
    def fetch_node_logs(self, node_id, version_id, *args, **kwargs):
        runtime = BambooDjangoRuntime()
        logs = runtime.get_plain_log_for_node(node_id=node_id, version=version_id)
        return {"result": True, "data": {"logs": logs, "page_info": {}}, "message": ""}


class DummyLogDataSource(BaseNodeLogDataSource):
    def fetch_node_logs(self, node_id, version_id, *args, **kwargs):
        return {"result": True, "data": {"logs": "", "page_info": {}}, "message": ""}


class NodeLogDataSourceFactory:
    DATASOURCE_MAPPINGS = {
        "DATABASE": DatabaseNodeLogDataSource,
        "PaaS3": PaaS3NodeLogDataSource,
        "DUMMY": DummyLogDataSource,
    }
    DEFAULT_DATASOURCE = DatabaseNodeLogDataSource

    def __init__(self, datasource):
        data_source_cls = self.DATASOURCE_MAPPINGS.get(datasource, self.DEFAULT_DATASOURCE)
        self.data_source = data_source_cls()
