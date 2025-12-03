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

import curlify
import requests

from bkflow.utils.handlers import handle_plain_log

logger = logging.getLogger("component")


def _gen_header():
    headers = {
        "Content-Type": "application/json",
    }
    return headers


def _http_request(
    method,
    url,
    headers=None,
    data=None,
    verify=False,
    cert=None,
    timeout=None,
    cookies=None,
):
    resp = requests.Response()
    request_id = None

    try:
        if method == "GET":
            resp = requests.get(
                url=url,
                headers=headers,
                params=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "HEAD":
            resp = requests.head(
                url=url,
                headers=headers,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "POST":
            resp = requests.post(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "DELETE":
            resp = requests.delete(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "PUT":
            resp = requests.put(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        else:
            return {"result": False, "message": "Unsupported http method %s" % method}
    except Exception as e:
        logger.exception("Error occurred when requesting method={} url={}".format(method, url))
        return {"result": False, "message": "Request API error, exception: %s" % str(e)}
    else:
        if not resp.ok:
            try:
                resp_message = resp.json()
            except Exception:
                resp_message = resp.content
            message = "Request API error, status_code: {}, url: {}, method: {}, data:{}, resp data: {}".format(
                resp.status_code, url, method, json.dumps(data), resp_message
            )

            return {"result": False, "message": message}

        log_message = (
            "API return: message: %(message)s, request_id=%(request_id)s, "
            "url=%(url)s, data=%(data)s, response=%(response)s"
        )

        try:
            json_resp = resp.json()
            request_id = json_resp.get("request_id")
            if not json_resp.get("result"):
                logger.error(
                    log_message
                    % {
                        "request_id": request_id,
                        "message": json_resp.get("message"),
                        "url": url,
                        "data": data,
                        "response": resp.text,
                    }
                )
            else:
                logger.debug(
                    log_message
                    % {
                        "request_id": request_id,
                        "message": json_resp.get("message"),
                        "url": url,
                        "data": data,
                        "response": resp.text,
                    }
                )
        except Exception:
            logger.exception("Return data format is incorrect, which shall be unified as json: %s", resp.content[200:])
            return {"result": False, "message": "API return is not a valid json"}

        return json_resp
    finally:
        if resp.request is None:
            resp.request = requests.Request(method, url, headers=headers, data=data, cookies=cookies).prepare()

        logger.debug(
            "the request_id: `%s`. curl: `%s`",
            request_id,
            handle_plain_log(curlify.to_curl(resp.request, verify=False)),
        )


def get(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="GET",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def post(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="POST",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def put(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="PUT",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def delete(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="DELETE",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )
