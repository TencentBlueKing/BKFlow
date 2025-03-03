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

from .exceptions import APIException

logger = logging.getLogger(__name__)


def render_string(tmpl, context):
    return tmpl.format(**context)


class RequestAPI:
    """Single request api"""

    HTTP_STATUS_OK = 200

    def __init__(self, client, method, host=None, path=None, description=""):
        self.host = host
        self.path = path
        self.client = client
        self.method = method

    def __call__(self, *args, path_params=None, **kwargs):
        try:
            return self._call(*args, path_params=path_params, **kwargs)
        except APIException as e:
            # Combine log message
            log_message = [
                e.error_message,
            ]
            log_message.append("url=%s" % e.url)
            if e.resp:
                log_message.append("content=%s" % e.resp.text)

            logger.exception("\n".join(log_message))

            # Try return error message from remote service
            if e.resp is not None:
                try:
                    return e.resp.json()
                except Exception:
                    pass
            return {"result": False, "message": e.error_message, "data": None}

    def _call(self, *args, path_params=None, **kwargs):
        if not path_params:
            path_params = {"stage": self.client.stage, "bk_apigw_ver": self.client.bk_apigw_ver}
        else:
            path_params.update({"stage": self.client.stage, "bk_apigw_ver": self.client.bk_apigw_ver})

        params, data = {}, {}
        for arg in args:
            if isinstance(arg, dict):
                params.update(arg)
        params.update(kwargs)

        if self.method in ["POST", "PUT", "PATCH", "DELETE"]:
            data = params
            params = None
        path = self.path
        # Request remote server
        if path_params:
            try:
                path = render_string(path, path_params)
            except KeyError as e:
                raise APIException(f"{e} is not in path_params")
        url = self.host.rstrip("/") + path
        try:
            resp = self.client.request(method=self.method, url=url, params=params, data=data)
        except Exception as e:
            logger.exception("Error occurred when requesting method=%s, url=%s", self.method, url)
            raise APIException("API调用出错, Exception: %s" % str(e), url=url)

        # Parse result
        if resp.status_code != self.HTTP_STATUS_OK:
            message = "请求出现错误，请求HTTP状态码：%s" % resp.status_code
            raise APIException(message, resp=resp, url=url)

        # Response format json or text
        try:
            return resp.json()
        except Exception:
            raise APIException("返回数据格式不正确，统一为json", resp=resp, url=url)
