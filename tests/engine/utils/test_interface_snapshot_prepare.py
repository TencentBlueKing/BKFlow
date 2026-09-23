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

# 验证快照准备请求的有限重试和错误展示边界。

import json

import pytest
import requests

from bkflow.contrib.api.collections.interface import InterfaceModuleClient


def make_response(status=200, payload=None):
    """构造经过真实 HTTP 包装层的响应。"""
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode() if payload is not None else b"<html>Bad Gateway</html>"
    response.request = requests.Request("POST", "http://interface.test/snapshot").prepare()
    return response


@pytest.fixture
def snapshot_client(mocker, settings):
    """隔离网络与时钟，重试测试不实际等待。"""
    settings.INTERFACE_APP_URL = "http://interface.test"
    settings.INTERFACE_APP_INTERNAL_TOKEN = "internal-test-token"
    clock = [0.0]
    timer = mocker.patch("bkflow.contrib.api.collections.interface.time")
    timer.monotonic.side_effect = lambda: clock[0]
    timer.sleep.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    mocker.patch("bkflow.contrib.api.collections.interface.random.uniform", return_value=0.25)
    mocker.patch(
        "bkflow.contrib.api.collections.interface.get_current_trace_context", return_value={"trace_id": "abc123"}
    )
    post = mocker.patch("bkflow.contrib.api.http.requests.post")
    return InterfaceModuleClient(), post, timer, clock


@pytest.mark.parametrize("failure", [502, 503, 504, requests.ConnectionError("reset"), requests.Timeout("timeout")])
def test_snapshot_retries_only_transient_request_failures(snapshot_client, failure):
    """瞬时错误恢复后返回快照，所有尝试使用同一份请求数据。"""
    client, post, timer, _ = snapshot_client
    payload = {"space_id": 5, "pipeline_tree": {"activities": {}}, "scope_type": "biz", "scope_id": "1"}
    success = {"result": True, "data": {"extra_info": {"plugin_reference_snapshot": [{"plugin_id": "p1"}]}}}
    post.side_effect = [make_response(failure) if isinstance(failure, int) else failure, make_response(payload=success)]

    assert client.prepare_task_extra_info(payload) == success
    assert post.call_count == 2
    timer.sleep.assert_called_once_with(1.25)
    for call in post.call_args_list:
        assert call.kwargs["json"] == payload
        assert call.kwargs["timeout"] == (3.0, 10.0)
        assert call.kwargs["url"].endswith("/api/template/internal/prepare_task_extra_info/")


def test_snapshot_stops_after_three_attempts_with_safe_error(snapshot_client):
    """持续 502 只请求三次，界面保留 Trace ID 并隐藏原始 HTML 和内部 URL。"""
    client, post, timer, _ = snapshot_client
    post.return_value = make_response(502)

    result = client.prepare_task_extra_info({})

    assert post.call_count == 3
    assert [call.args[0] for call in timer.sleep.call_args_list] == [1.25, 2.25]
    assert result["result"] is False
    assert result["retryable"] is True
    assert result["code"] == "SNAPSHOT_PREPARE_UNAVAILABLE"
    assert "abc123" in result["message"]
    assert "<html>" not in result["message"]
    assert "interface.test" not in result["message"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_snapshot_does_not_retry_other_http_errors(snapshot_client, status):
    """非瞬时 HTTP 错误不进入重试。"""
    client, post, timer, _ = snapshot_client
    post.return_value = make_response(status)

    result = client.prepare_task_extra_info({})

    assert result["result"] is False
    assert result["retryable"] is False
    post.assert_called_once()
    timer.sleep.assert_not_called()


@pytest.mark.parametrize("error", [requests.exceptions.SSLError("certificate"), requests.exceptions.InvalidURL("bad")])
def test_snapshot_does_not_retry_request_configuration_errors(snapshot_client, error):
    """证书或 URL 配置错误应立即失败。"""
    client, post, timer, _ = snapshot_client
    post.side_effect = error

    assert client.prepare_task_extra_info({})["retryable"] is False
    post.assert_called_once()
    timer.sleep.assert_not_called()


@pytest.mark.parametrize("message", ["插件在当前空间未开放", "插件版本不存在", "插件已下线"])
def test_snapshot_preserves_business_validation_failure(snapshot_client, message):
    """授权和版本校验失败保留具体原因且不重试。"""
    client, post, timer, _ = snapshot_client
    failure = {"result": False, "code": "invalid", "message": message}
    post.return_value = make_response(payload=failure)

    assert client.prepare_task_extra_info({}) == failure
    post.assert_called_once()
    timer.sleep.assert_not_called()


@pytest.mark.parametrize("payload", [None, [], {"result": True}, {"result": True, "data": {"extra_info": None}}])
def test_snapshot_rejects_invalid_success_response(snapshot_client, payload):
    """损坏的成功响应不能放行创建任务，也不重复请求。"""
    client, post, timer, _ = snapshot_client
    post.return_value = make_response(payload=payload)

    result = client.prepare_task_extra_info({})

    assert result["result"] is False
    assert result["code"] == "SNAPSHOT_PREPARE_REQUEST_FAILED"
    post.assert_called_once()
    timer.sleep.assert_not_called()


def test_snapshot_respects_remaining_retry_budget(snapshot_client):
    """前次请求消耗预算后，后续请求超时随剩余预算缩短。"""
    client, post, timer, clock = snapshot_client

    def respond(**kwargs):
        clock[0] += 28.0 if post.call_count == 1 else 1.0
        return make_response(502)

    post.side_effect = respond
    assert client.prepare_task_extra_info({})["result"] is False
    assert post.call_count == 2
    assert sum(post.call_args.kwargs["timeout"]) <= 0.75
    timer.sleep.assert_called_once_with(1.25)


def test_snapshot_does_not_sleep_beyond_budget(snapshot_client):
    """没有足够预算等待下一次尝试时立即结束。"""
    client, post, timer, clock = snapshot_client

    def respond(**kwargs):
        clock[0] = 29.0
        return make_response(503)

    post.side_effect = respond
    assert client.prepare_task_extra_info({})["result"] is False
    post.assert_called_once()
    timer.sleep.assert_not_called()


def test_other_interface_requests_are_not_retried(snapshot_client):
    """事件广播等其它 POST 仍只发送一次。"""
    client, post, timer, _ = snapshot_client
    post.return_value = make_response(502)

    assert client.broadcast_task_events({})["result"] is False
    post.assert_called_once()
    timer.sleep.assert_not_called()
