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
import copy
import json
import logging
from functools import reduce
from operator import getitem
from typing import Union

import jmespath
import jsonschema
import requests
from django.conf import settings
from pydantic import BaseModel
from requests import Response

from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.utils.apigw import check_url_from_apigw

logger = logging.getLogger("root")


class ApigwClientMixin:
    @staticmethod
    def check_url_from_apigw(url: str) -> bool:
        """
        检查URL是否来自API网关
        :return:
        """
        return check_url_from_apigw(url)

    @staticmethod
    def gen_default_apigw_header(app_code: str, app_secret: str, username: str = None):
        auth_info = {"bk_app_code": app_code, "bk_app_secret": app_secret}
        if username:
            auth_info["bk_username"] = username
        return {
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": json.dumps(auth_info),
        }


class HttpRequestResult(BaseModel):
    result: bool
    message: str = ""
    resp: Response = None
    json_resp: Union[dict, list] = {}

    def extract_json_resp(self, keys: list):
        return reduce(getitem, keys, self.json_resp)

    def extract_json_resp_with_jmespath(self, path):
        return jmespath.search(path, self.json_resp)

    class Config:
        arbitrary_types_allowed = True


class HttpRequestMixin:
    @staticmethod
    def gen_default_header():
        return {"Content-Type": "application/json"}

    @staticmethod
    def http_request(
        url: str,
        method: str,
        headers=None,
        data=None,
        verify=False,
        cert=None,
        timeout=None,
        cookie=None,
        request_id_key="request_id",
        *args,
        **kwargs,
    ) -> HttpRequestResult:

        masked_data, masked_headers = {}, {}
        if headers and isinstance(headers, dict):
            masked_headers = copy.deepcopy(headers)
            if "X-Bkapi-Authorization" in masked_headers:
                masked_headers["X-Bkapi-Authorization"]

        if data and isinstance(data, dict):
            masked_data = copy.deepcopy(data)
            if "bk_app_secret" in masked_data:
                masked_data["bk_app_secret"] = "******"

        base_message = (
            f"[request api base info] url: {url}, method: {method}, headers: {masked_headers or headers}, "
            f"data: {masked_data or data}, verify: {verify}, cert: {cert}, timeout: {timeout}, "
            f"cookie: {cookie}, request_id_key: {request_id_key}."
        )

        response = requests.Response()
        request_id = None
        try:
            if method == "GET":
                response = requests.get(
                    url=url,
                    headers=headers,
                    params=data,
                    verify=verify,
                    cert=cert,
                    timeout=timeout,
                    cookies=cookie,
                )
            elif method == "HEAD":
                response = requests.head(
                    url=url,
                    headers=headers,
                    verify=verify,
                    cert=cert,
                    timeout=timeout,
                    cookies=cookie,
                )
            elif method == "POST":
                response = requests.post(
                    url=url,
                    headers=headers,
                    json=data,
                    verify=verify,
                    cert=cert,
                    timeout=timeout,
                    cookies=cookie,
                )
            elif method == "DELETE":
                response = requests.delete(
                    url=url,
                    headers=headers,
                    json=data,
                    verify=verify,
                    cert=cert,
                    timeout=timeout,
                    cookies=cookie,
                )
            elif method == "PUT":
                response = requests.put(
                    url=url,
                    headers=headers,
                    json=data,
                    verify=verify,
                    cert=cert,
                    timeout=timeout,
                    cookies=cookie,
                )
            else:
                message = f"request api error: method {method} is not supported."
                logger.error(f"{base_message}, {message}")
                raise APIRequestError(message)
        except Exception as e:
            message = f"request api error: {e}."
            logger.error(f"{base_message}, {message}")
            raise APIRequestError(message)
        else:
            if not response.ok:
                message = f"[request api error] status_code: {response.status_code}."
                logger.error(f"{message}, response: {response.text}, {base_message}")
                return HttpRequestResult(result=False, message=message, resp=response)

            try:
                json_resp = response.json()
                if not isinstance(json_resp, dict):
                    return HttpRequestResult(result=True, resp=response, json_resp=json_resp)
                request_id = json_resp.get(request_id_key)
                if not json_resp.get("result"):
                    message = f"[request api error] message: {json_resp.get('message')}."
                    logger.error(f"{message}, response: {response.text}, {base_message}, request_id: {request_id}")
                    return HttpRequestResult(result=False, message=message, resp=response, json_resp=json_resp)
                else:
                    logger.debug(base_message + f"response: {response.text}, request_id: {request_id}")
            except Exception as e:
                message = f"[request api error] the response is not valid json format: {e}"
                logger.error(f"{message}, response: {response.text}, {base_message}")
                return HttpRequestResult(result=False, message=message, resp=response)

            return HttpRequestResult(result=True, resp=response, json_resp=json_resp)

    @staticmethod
    def validate_response_data(data: dict, schema: dict, *args, **kwargs):
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            message = f"validate response data error: {e}."
            logger.exception(message)
            raise ValidationError(message)


class ApiGwClient(ApigwClientMixin, HttpRequestMixin):
    SUPPORT_METHODS = ["GET", "POST", "DELETE", "PUT", "HEAD"]
    TIMEOUT = 30

    def __init__(self, from_apigw_check=True, *args, **kwargs):
        self.from_apigw_check = from_apigw_check
        super(ApiGwClient, self).__init__(*args, **kwargs)

    def request(self, url: str, method: str, data=None, headers=None, *args, **kwargs) -> HttpRequestResult:
        """
        请求统一API，可能抛出APIRequestError
        """
        method = method.upper()
        if method not in self.SUPPORT_METHODS:
            raise APIRequestError(f"method not supported: {method}，supported methods: {self.SUPPORT_METHODS}")

        if self.from_apigw_check and self.check_url_from_apigw(url) is False:
            raise APIRequestError(f"check url from apigw fail: {url}")

        if headers:
            headers.update(
                self.gen_default_apigw_header(app_code=settings.BK_APP_CODE, app_secret=settings.BK_APP_SECRET)
            )
        else:
            headers = self.gen_default_apigw_header(app_code=settings.BK_APP_CODE, app_secret=settings.BK_APP_SECRET)

        timeout = kwargs.pop("timeout", self.TIMEOUT)
        return self.http_request(
            url=url,
            method=method,
            data=data,
            headers=headers,
            timeout=timeout,
            *args,
            **kwargs,
        )
