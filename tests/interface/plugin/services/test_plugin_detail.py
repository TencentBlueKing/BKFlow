"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.utils.translation import ugettext_lazy as _
from pipeline.exceptions import ComponentNotExistException
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from bkflow.exceptions import APIResponseError
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.serializers.plugin_detail import PluginDetailRequestSerializer
from bkflow.plugin.services.plugin_detail import PluginDetailService
from bkflow.utils.api_client import HttpRequestResult
from plugin_service.exceptions import PluginServiceException

EXPECTED_DETAIL_KEYS = {
    "plugin_type",
    "plugin_code",
    "plugin_version",
    "source_key",
    "plugin_source",
    "protocol",
    "wrapper_version",
    "name",
    "description",
    "inputs",
    "outputs",
    "credentials",
    "forms",
    "form_schema",
    "form_context",
    "execution_kind",
    "url",
    "methods",
    "response_data_path",
    "polling",
    "callback",
    "credential_key",
}

EXPECTED_FORM_DESCRIPTOR_KEYS = {"type", "key", "data", "is_embedded", "base"}

JOB_EXECUTE_TASK_OUTPUT_FORM_FIXTURE = {
    "path": "components/job_execute_task_output.js",
    "script": "window.$.atoms.job_execute_task = []",
}


def assert_contract(detail):
    assert set(detail) == EXPECTED_DETAIL_KEYS
    assert set(detail["forms"]) == {"input", "output"}


def assert_form_descriptor(descriptor):
    assert set(descriptor) == EXPECTED_FORM_DESCRIPTOR_KEYS


def uniform_request(**overrides):
    request = {
        "space_id": "245",
        "template_id": "2329",
        "plugin_type": "uniform_api",
        "plugin_code": "open_plugin_001",
        "plugin_version": "1.0.0",
        "source_key": "sops",
    }
    request.update(overrides)
    return request


def uniform_result(data=None, result=True, message="", response_result=True):
    """构造统一 API HTTP 与业务层响应。"""
    return HttpRequestResult(
        result=result,
        message=message,
        json_resp={
            "result": response_result,
            "message": message,
            "data": data,
        },
    )


def uniform_detail_data(**overrides):
    """构造完整的 V4 插件详情响应。"""
    data = {
        "id": "builtin__job_fast_execute_script",
        "plugin_code": "job_fast_execute_script",
        "plugin_version": "v2.0",
        "plugin_source": "builtin",
        "wrapper_version": "v4.0.0",
        "name": "快速执行脚本",
        "desc": "执行 JOB 脚本",
        "inputs": [],
        "outputs": [],
        "credentials": [],
        "forms": {
            "input": {
                "type": "component_js",
                "key": "job_fast_execute_script",
                "data": "https://bksops.example.com/static/job.js",
                "is_embedded": False,
                "base": None,
            },
            "output": None,
        },
        "form_context": {"biz_cc_id": 100605},
        "url": "https://bksops.example.com/runs/",
        "methods": ["POST"],
        "response_data_path": "data.outputs",
        "credential_key": "sops",
    }
    data.update(overrides)
    return data


class FakeComponent:
    desc = _("快速执行脚本")
    form = "components/job.js"
    output_form = "components/job_output.js"
    embedded_output_form = "window.$.outputs.job = []"
    base = {"resource": "job"}

    @classmethod
    def form_is_embedded(cls):
        return False

    @classmethod
    def inputs_format(cls):
        return [{"key": "script_content", "name": _("脚本内容"), "type": "string", "required": True}]

    @classmethod
    def outputs_format(cls):
        return [{"key": "_result", "name": _("执行结果"), "type": "bool"}]


@pytest.fixture
def service():
    return PluginDetailService(
        space_id="245",
        template_id="2329",
        operator="dannydeng",
        scope_type="biz",
        scope_value="100605",
    )


@pytest.fixture
def available_open_plugin():
    """创建已准入、已开放且目录可用的 V4 插件。"""
    catalog = OpenPluginCatalogIndex(
        space_id=245,
        source_key="sops",
        plugin_id="builtin__job_fast_execute_script",
        plugin_code="job_fast_execute_script",
        plugin_name="快速执行脚本",
        plugin_source="builtin",
        group_name="作业平台",
        wrapper_version="v4.0.0",
        default_version="v2.0",
        latest_version="v2.1",
        versions=["v2.0", "v2.1"],
        meta_url_template="https://bksops.example.com/meta/{version}/",
        description="执行 JOB 脚本",
        status=OpenPluginCatalogIndex.Status.AVAILABLE,
    )
    availability = SpaceOpenPluginAvailability(
        space_id=245,
        source_key="sops",
        plugin_id=catalog.plugin_id,
        enabled=True,
    )
    grant = SimpleNamespace(space_id=245, source_key="sops", enabled=True)

    class FakeQuerySet:
        def __init__(self, items):
            self.items = list(items)

        def exists(self):
            return bool(self.items)

        def filter(self, **kwargs):
            items = self.items
            if "source_key" in kwargs:
                items = [item for item in items if item.source_key == kwargs["source_key"]]
            if "source_key__in" in kwargs:
                items = [item for item in items if item.source_key in kwargs["source_key__in"]]
            if "status" in kwargs:
                items = [item for item in items if item.status == kwargs["status"]]
            if "wrapper_version" in kwargs:
                items = [item for item in items if item.wrapper_version == kwargs["wrapper_version"]]
            if "plugin_id" in kwargs:
                items = [item for item in items if item.plugin_id == kwargs["plugin_id"]]
            return FakeQuerySet(items)

        def order_by(self, *args):
            return self

        def first(self):
            return self.items[0] if self.items else None

        def values_list(self, *fields):
            return [tuple(getattr(item, field) for field in fields) for item in self.items]

        def __iter__(self):
            return iter(self.items)

    def filter_catalog(**kwargs):
        matches = [catalog]
        if "space_id" in kwargs:
            matches = [item for item in matches if str(item.space_id) == str(kwargs["space_id"])]
        if "plugin_id" in kwargs:
            matches = [item for item in matches if item.plugin_id == kwargs["plugin_id"]]
        if "source_key" in kwargs:
            matches = [item for item in matches if item.source_key == kwargs["source_key"]]
        if "source_key__in" in kwargs:
            matches = [item for item in matches if item.source_key in kwargs["source_key__in"]]
        if "status" in kwargs:
            matches = [item for item in matches if item.status == kwargs["status"]]
        if "wrapper_version" in kwargs:
            matches = [item for item in matches if item.wrapper_version == kwargs["wrapper_version"]]
        return FakeQuerySet(matches)

    def filter_availability(**kwargs):
        matches = [availability]
        if "space_id" in kwargs:
            matches = [item for item in matches if str(item.space_id) == str(kwargs["space_id"])]
        if "source_key" in kwargs:
            matches = [item for item in matches if item.source_key == kwargs["source_key"]]
        if "source_key__in" in kwargs:
            matches = [item for item in matches if item.source_key in kwargs["source_key__in"]]
        if "plugin_id" in kwargs:
            matches = [item for item in matches if item.plugin_id == kwargs["plugin_id"]]
        if "enabled" in kwargs:
            matches = [item for item in matches if item.enabled is kwargs["enabled"]]
        return FakeQuerySet(matches)

    catalog._test_availability = availability
    catalog._test_grant = grant
    with patch(
        "bkflow.plugin.services.plugin_schema_service.OpenPluginCatalogIndex.objects.filter",
        side_effect=filter_catalog,
    ), patch(
        "bkflow.plugin.services.plugin_schema_service.SpaceOpenPluginAvailability.objects.filter",
        side_effect=filter_availability,
    ), patch(
        "bkflow.plugin.services.plugin_schema_service.OpenPluginGrantService.granted_source_keys",
        side_effect=lambda space_id: [grant.source_key] if grant.enabled else [],
    ), patch(
        "bkflow.plugin.services.plugin_schema_service.OpenPluginGrantService.is_granted",
        side_effect=lambda space_id, source_key: grant.enabled and source_key == grant.source_key,
    ):
        yield catalog


def test_request_rejects_unknown_plugin_type():
    """不接受详情契约之外的插件类型。"""
    serializer = PluginDetailRequestSerializer(
        data={
            "space_id": "245",
            "template_id": "2329",
            "plugin_type": "unknown",
            "plugin_code": "x",
            "plugin_version": "1.0",
        }
    )

    assert serializer.is_valid() is False


def test_uniform_api_requires_source_key():
    """uniform_api 必须明确所属来源。"""
    serializer = PluginDetailRequestSerializer(data=uniform_request(source_key=""))

    assert serializer.is_valid() is False


@pytest.mark.parametrize("field", ("operator", "unknown"))
def test_request_rejects_unknown_fields(field):
    """请求契约不接受 operator 或其他未声明字段。"""
    serializer = PluginDetailRequestSerializer(data=uniform_request(**{field: "attacker"}))

    assert serializer.is_valid() is False
    assert field in serializer.errors


@pytest.mark.parametrize("scope_type", ("biz", "cmdb_biz"))
def test_request_rejects_non_integer_business_scope(scope_type):
    """业务范围值必须能安全转换为整数。"""
    serializer = PluginDetailRequestSerializer(
        data=uniform_request(scope_type=scope_type, scope_value="not-an-integer")
    )

    assert serializer.is_valid() is False
    assert "scope_value" in serializer.errors


@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
@override_settings(SITE_URL="https://bkflow.example.com")
def test_component_adapter_returns_native_component_js(component_class, component_model, service):
    """内置组件返回完整的原生 component_js 表单描述。"""
    component_model.objects.filter.return_value.first.return_value = MagicMock(
        code="job_fast_execute_script", version="v2.0", name="作业平台(JOB)-快速执行脚本"
    )
    component_class.return_value = FakeComponent

    detail = service.get_detail(
        plugin_type="component",
        plugin_code="job_fast_execute_script",
        plugin_version="v2.0",
    )

    assert_contract(detail)
    assert detail["source_key"] == "bkflow"
    assert detail["plugin_source"] == "builtin"
    assert detail["protocol"] == "native"
    assert detail["execution_kind"] == "component"
    assert_form_descriptor(detail["forms"]["input"])
    assert_form_descriptor(detail["forms"]["output"])
    assert detail["forms"]["input"] == {
        "type": "component_js",
        "key": "job_fast_execute_script",
        "data": "https://bkflow.example.com/components/job.js",
        "is_embedded": False,
        "base": {"resource": "job"},
    }
    assert detail["forms"]["output"] == {
        "type": "component_js",
        "key": "job_fast_execute_script",
        "data": "https://bkflow.example.com/components/job_output.js",
        "is_embedded": False,
        "base": {"resource": "job"},
    }
    assert detail["description"] == "快速执行脚本"
    assert detail["inputs"] == [
        {"key": "script_content", "name": "脚本内容", "type": "string", "description": "", "required": True}
    ]
    assert detail["outputs"] == [{"key": "_result", "name": "执行结果", "type": "bool", "description": ""}]
    assert json.loads(json.dumps(detail["form_context"]))["biz_cc_id"] == 100605
    component_model.objects.filter.assert_called_once_with(code="job_fast_execute_script", version="v2.0", status=True)
    component_class.assert_called_once_with("job_fast_execute_script", "v2.0")


@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
def test_component_adapter_uses_embedded_output_form(component_class, component_model, service):
    """内嵌组件保留内嵌输出表单，不回退为静态路径。"""
    component_model.objects.filter.return_value.first.return_value = MagicMock(name="内嵌组件")
    component = type(
        "EmbeddedComponent",
        (FakeComponent,),
        {"form": "window.$.atoms.job = []", "form_is_embedded": classmethod(lambda cls: True)},
    )
    component_class.return_value = component

    detail = service.get_detail("component", "embedded_job", "v2.0")

    assert detail["forms"]["input"]["data"] == "window.$.atoms.job = []"
    assert detail["forms"]["input"]["is_embedded"] is True
    assert detail["forms"]["output"]["data"] == "window.$.outputs.job = []"
    assert detail["forms"]["output"]["key"] == "embedded_job"


@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
@override_settings(SITE_URL="https://bkflow.example.com")
def test_component_output_descriptor_uses_provider_registered_key(component_class, component_model, service):
    """输出 JS 文件名可带 _output，但实际注册 key 仍是插件 code。"""
    component_model.objects.filter.return_value.first.return_value = MagicMock(name="作业平台(JOB)-执行任务")
    component_class.return_value = type(
        "JobExecuteTaskComponent",
        (FakeComponent,),
        {
            "form": "components/job_execute_task.js",
            "output_form": JOB_EXECUTE_TASK_OUTPUT_FORM_FIXTURE["path"],
        },
    )

    detail = service.get_detail("component", "job_execute_task", "v2.0")

    assert "$.atoms.job_execute_task" in JOB_EXECUTE_TASK_OUTPUT_FORM_FIXTURE["script"]
    assert detail["forms"]["output"] == {
        "type": "component_js",
        "key": "job_execute_task",
        "data": "https://bkflow.example.com/components/job_execute_task_output.js",
        "is_embedded": False,
        "base": {"resource": "job"},
    }


@pytest.mark.parametrize(
    ("form", "output_form", "has_input", "has_output"),
    (
        ("", "components/job_output.js", False, True),
        ("components/job.js", "", True, False),
        ("", "", False, False),
    ),
    ids=("no-input", "no-output", "no-input-or-output"),
)
@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
@override_settings(SITE_URL="https://bkflow.example.com")
def test_component_adapter_uses_null_for_empty_forms(
    component_class, component_model, form, output_form, has_input, has_output, service
):
    """组件未提供输入或输出表单时，固定 forms 槽位必须为 null。"""
    component_model.objects.filter.return_value.first.return_value = MagicMock(name="空表单组件")
    component_class.return_value = type(
        "PartialFormComponent",
        (FakeComponent,),
        {"form": form, "output_form": output_form},
    )

    detail = service.get_detail("component", "partial_form", "v2.0")

    if has_input:
        assert_form_descriptor(detail["forms"]["input"])
    else:
        assert detail["forms"]["input"] is None
    if has_output:
        assert_form_descriptor(detail["forms"]["output"])
    else:
        assert detail["forms"]["output"] is None


@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
def test_component_adapter_maps_missing_registered_component_to_not_found(component_class, component_model, service):
    """DB 版本尚存但组件库无法解析时，返回受控的 NotFound。"""
    component_model.objects.filter.return_value.first.return_value = MagicMock(name="已遗失组件")
    component_class.side_effect = ComponentNotExistException("component has been removed")

    with pytest.raises(NotFound):
        service.get_detail("component", "missing_component", "v2.0")


@patch("bkflow.plugin.services.plugin_detail.ComponentModel")
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
def test_component_adapter_rejects_missing_exact_version(component_class, component_model, service):
    """组件版本不存在或下架时不回退到其他版本。"""
    component_model.objects.filter.return_value.first.return_value = None

    with pytest.raises(NotFound):
        service.get_detail(
            plugin_type="component",
            plugin_code="job_fast_execute_script",
            plugin_version="v2.1",
        )

    component_model.objects.filter.assert_called_once_with(code="job_fast_execute_script", version="v2.1", status=True)
    component_class.assert_not_called()


@pytest.fixture
def authorized_remote_plugin():
    with patch("bkflow.plugin.services.plugin_detail.BKPluginAuthorization") as authorization:
        authorization.objects.get_codes_by_space_id.return_value = ["demo"]
        yield authorization


@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_preserves_renderform(client_cls, authorized_remote_plugin, service):
    """远程插件 renderform 保持原始脚本，不改写为 schema。"""
    client_cls.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.1.0", "1.0.0"]},
    }
    client_cls.return_value.get_detail.return_value = {
        "result": True,
        "data": {
            "version": "1.0.0",
            "inputs": {"type": "object", "properties": {}},
            "outputs": {"type": "object", "properties": {}},
            "credentials": [],
            "forms": {
                "renderform": "window.$.atoms.demo = [{tag_code: 'x', type: 'input'}]",
            },
        },
    }

    detail = service.get_detail(
        plugin_type="remote_plugin",
        plugin_code="demo",
        plugin_version="1.0.0",
    )

    assert_contract(detail)
    assert detail["plugin_source"] == "third_party"
    assert detail["protocol"] == "plugin_service"
    assert detail["execution_kind"] == "remote_plugin"
    assert_form_descriptor(detail["forms"]["input"])
    assert detail["forms"]["input"] == {
        "type": "renderform",
        "key": "demo",
        "data": "window.$.atoms.demo = [{tag_code: 'x', type: 'input'}]",
        "is_embedded": True,
        "base": None,
    }
    client_cls.return_value.get_detail.assert_called_once_with("1.0.0")


def test_remote_adapter_rejects_plugin_without_space_grant(service):
    """远程插件未授权给当前空间时不得查询远端详情。"""
    with patch("bkflow.plugin.services.plugin_detail.BKPluginAuthorization") as authorization:
        authorization.objects.get_codes_by_space_id.return_value = []

        with pytest.raises(PermissionDenied):
            service.get_detail(
                plugin_type="remote_plugin",
                plugin_code="demo",
                plugin_version="1.0.0",
            )


@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_rejects_missing_exact_version(client_cls, authorized_remote_plugin, service):
    """远程插件请求不存在版本时不请求详情接口。"""
    client_cls.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.1.0"]},
    }

    with pytest.raises(NotFound):
        service.get_detail(
            plugin_type="remote_plugin",
            plugin_code="demo",
            plugin_version="1.0.0",
        )

    client_cls.return_value.get_detail.assert_not_called()


@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_rejects_meta_without_data(client_cls, authorized_remote_plugin, service):
    """远程 meta 没有有效 data 时不能继续请求详情。"""
    client_cls.return_value.get_meta.return_value = {"result": True, "data": None}

    with pytest.raises(APIException):
        service.get_detail(
            plugin_type="remote_plugin",
            plugin_code="demo",
            plugin_version="1.0.0",
        )

    client_cls.return_value.get_detail.assert_not_called()


@pytest.mark.parametrize("response", (None, [], {"result": False, "data": {}}, {"result": True, "data": []}))
@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_rejects_malformed_meta_response(client_cls, response, authorized_remote_plugin, service):
    """上游成功标记却没有对象 data 时必须受控失败。"""
    client_cls.return_value.get_meta.return_value = response

    with pytest.raises(APIException):
        service.get_detail("remote_plugin", "demo", "1.0.0")

    client_cls.return_value.get_detail.assert_not_called()


@pytest.mark.parametrize("failure_point", ("client", "meta", "detail"))
@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_maps_plugin_service_exceptions(client_cls, failure_point, authorized_remote_plugin, service):
    """client 构造和远端调用异常都映射为受控上游错误。"""
    if failure_point == "client":
        client_cls.side_effect = PluginServiceException("network unavailable")
    elif failure_point == "meta":
        client_cls.return_value.get_meta.side_effect = PluginServiceException("network unavailable")
    else:
        client_cls.return_value.get_meta.return_value = {"result": True, "data": {"versions": ["1.0.0"]}}
        client_cls.return_value.get_detail.side_effect = PluginServiceException("network unavailable")

    with pytest.raises(APIException):
        service.get_detail("remote_plugin", "demo", "1.0.0")


@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_uses_jsonschema_when_renderform_is_missing(client_cls, authorized_remote_plugin, service):
    """没有 renderform 时输入原始 JSON schema 仍可被表单端消费。"""
    inputs = {
        "type": "object",
        "required": ["message"],
        "properties": {
            "message": {
                "title": "消息",
                "type": "string",
                "description": "发送给远程插件的消息",
                "default": "hello",
                "schema": {"minLength": 1},
            },
            "timeout": {"name": "超时", "type": "int", "default": 60},
        },
    }
    client_cls.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.0.0"]},
    }
    client_cls.return_value.get_detail.return_value = {
        "result": True,
        "data": {
            "inputs": inputs,
            "outputs": {"type": "object", "properties": {}},
            "credentials": [],
            "forms": {},
        },
    }

    detail = service.get_detail(
        plugin_type="remote_plugin",
        plugin_code="demo",
        plugin_version="1.0.0",
    )

    assert_form_descriptor(detail["forms"]["input"])
    assert detail["forms"]["input"] == {
        "type": "jsonschema",
        "key": "demo",
        "data": inputs,
        "is_embedded": True,
        "base": None,
    }
    assert detail["inputs"] == [
        {
            "key": "message",
            "name": "消息",
            "type": "string",
            "description": "发送给远程插件的消息",
            "required": True,
            "default": "hello",
            "schema": {"minLength": 1},
        },
        {"key": "timeout", "name": "超时", "type": "int", "description": "", "required": False, "default": 60},
    ]


@pytest.mark.parametrize(
    "data",
    (None, {"inputs": {"type": "object", "properties": []}}),
)
@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_rejects_malformed_detail_data(client_cls, data, authorized_remote_plugin, service):
    """detail 成功标记却没有有效对象 data 或 JSON Schema 时必须受控失败。"""
    client_cls.return_value.get_meta.return_value = {"result": True, "data": {"versions": ["1.0.0"]}}
    client_cls.return_value.get_detail.return_value = {"result": True, "data": data}

    with pytest.raises(APIException):
        service.get_detail("remote_plugin", "demo", "1.0.0")


class TestUniformApiDetailAdapter:
    """验证 V4 adapter 的准入、精确版本与 provider 契约。"""

    @patch("bkflow.plugin.services.plugin_detail.PluginSchemaService._get_single_by_type")
    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_selects_requested_source(
        self,
        client_cls,
        get_credential,
        get_single_by_type,
        service,
    ):
        """Uniform adapter 查询目录时必须把 source_key 传给 schema service。"""
        get_single_by_type.return_value = {
            "code": "shared_open_plugin",
            "source_key": "second-source",
            "plugin_source": "second",
            "wrapper_version": "v4.0.0",
            "versions": ["second-v2"],
            "meta_url_template": "https://second.example/{version}",
        }
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(
            data=uniform_detail_data(plugin_version="second-v2", plugin_source="second")
        )

        service.get_detail(
            plugin_type="uniform_api",
            plugin_code="shared_open_plugin",
            plugin_version="second-v2",
            source_key="second-source",
        )

        get_single_by_type.assert_called_once_with(
            "shared_open_plugin",
            "uniform_api",
            version="second-v2",
            source_key="second-source",
        )
        assert client_cls.return_value.request.call_args.kwargs["url"] == "https://second.example/second-v2"

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_forwards_scope_and_operator(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """V4 请求必须透传真实 operator、来源与 scope。"""
        get_credential.return_value = {
            "bk_app_code": "bkflow",
            "bk_app_secret": "secret",
        }
        client_cls.return_value.request.return_value = uniform_result(data=uniform_detail_data())

        detail = service.get_detail(
            plugin_type="uniform_api",
            plugin_code="builtin__job_fast_execute_script",
            plugin_version="v2.0",
            source_key="sops",
        )

        assert_contract(detail)
        assert detail["plugin_code"] == "builtin__job_fast_execute_script"
        assert detail["plugin_source"] == "builtin"
        assert detail["protocol"] == "uniform_api"
        assert detail["execution_kind"] == "uniform_api"
        assert detail["form_context"]["biz_cc_id"] == 100605
        assert detail["forms"] == uniform_detail_data()["forms"]
        assert detail["response_data_path"] == "data.outputs"
        assert detail["credential_key"] == "sops"
        get_credential.assert_called_once_with(space_id="245", template_id="2329")
        headers_kwargs = client_cls.return_value.gen_default_apigw_header.call_args.kwargs
        assert headers_kwargs == {
            "app_code": "bkflow",
            "app_secret": "secret",
            "username": "dannydeng",
        }
        request_kwargs = client_cls.return_value.request.call_args.kwargs
        assert request_kwargs["url"] == "https://bksops.example.com/meta/v2.0/"
        assert request_kwargs["username"] == "dannydeng"
        assert request_kwargs["data"] == {
            "source_key": "sops",
            "scope_type": "biz",
            "scope_value": "100605",
        }

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_preserves_form_schema(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """V4 provider 的完整 JSON Schema 表单不能退化为扁平 inputs。"""
        form_schema = {
            "type": "object",
            "required": ["vendor"],
            "properties": {
                "vendor": {
                    "type": "string",
                    "title": "云厂商",
                    "ui:component": {
                        "name": "select",
                        "props": {
                            "datasource": [
                                {"label": "腾讯云-自研云", "value": "tcloud-ziyan"},
                                {"label": "腾讯云-公有云", "value": "tcloud"},
                            ]
                        },
                    },
                }
            },
        }
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(
            data=uniform_detail_data(
                inputs=[{"key": "vendor", "name": "云厂商", "type": "string", "required": True}],
                forms={"input": None, "output": None},
                form_schema=form_schema,
            )
        )

        detail = service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        assert detail["forms"] == {"input": None, "output": None}
        assert detail["form_schema"] == form_schema

    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_source_without_grant(self, client_cls, available_open_plugin, service):
        """来源 grant 被撤销后不得查询 provider。"""
        available_open_plugin._test_grant.enabled = False

        with pytest.raises(PermissionDenied, match="未准入"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_disabled_availability(self, client_cls, available_open_plugin, service):
        """空间关闭插件后不得查询 provider。"""
        available_open_plugin._test_availability.enabled = False

        with pytest.raises(PermissionDenied, match="未开放"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_unavailable_catalog_item(self, client_cls, available_open_plugin, service):
        """目录状态不可用时不得查询 provider。"""
        available_open_plugin.status = OpenPluginCatalogIndex.Status.UNAVAILABLE

        with pytest.raises(NotFound, match="当前不可用"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_version_outside_catalog(self, client_cls, available_open_plugin, service):
        """请求版本必须仍在目录 versions 中。"""
        with pytest.raises(NotFound, match="版本"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v9.9", "sops")

        client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_does_not_fallback_invalid_saved_version(self, client_cls, available_open_plugin, service):
        """已保存版本下架后不能自动改用 latest_version。"""
        available_open_plugin.versions = ["v2.1"]
        available_open_plugin.latest_version = "v2.1"

        with pytest.raises(NotFound, match="v2.0"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_provider_version_mismatch(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """provider 不能用 latest 版本响应已保存的精确版本请求。"""
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(data=uniform_detail_data(plugin_version="v2.1"))

        with pytest.raises(APIResponseError, match="v2.0.*v2.1"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_requires_provider_version_for_v4(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """V4 provider 响应必须携带可核对的精确插件版本。"""
        data = uniform_detail_data()
        data.pop("plugin_version")
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(data=data)

        with pytest.raises(APIResponseError, match="V4.*plugin_version"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

    @pytest.mark.parametrize("wrapper_version", ("v2.0.0", "v3.0.0"))
    @patch("bkflow.plugin.services.plugin_detail.PluginSchemaService._get_single_by_type")
    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_keeps_legacy_version_and_forms_optional(
        self,
        client_cls,
        get_credential,
        get_single_by_type,
        wrapper_version,
        service,
    ):
        """V2/V3 走远端列表，provider 可继续省略 plugin_version 和原生 forms。"""
        get_single_by_type.return_value = {
            "code": "legacy_sops_execute",
            "source_key": "sops",
            "wrapper_version": wrapper_version,
            "_meta_url": "https://bksops.example.com/meta/v2.0/",
        }
        data = uniform_detail_data()
        for field in ("plugin_source", "plugin_code", "plugin_version", "wrapper_version", "forms"):
            data.pop(field)
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(data=data)

        detail = service.get_detail("uniform_api", "legacy_sops_execute", "v2.0", "sops")

        assert detail["wrapper_version"] == wrapper_version
        assert detail["forms"] == {"input": None, "output": None}

    @pytest.mark.parametrize(
        "provider_result",
        (
            uniform_result(data=None, result=False, message="network failed"),
            uniform_result(data=None, response_result=False, message="provider rejected"),
        ),
        ids=("http-result-false", "business-result-false"),
    )
    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_provider_failure(
        self,
        client_cls,
        get_credential,
        provider_result,
        available_open_plugin,
        service,
    ):
        """HTTP 或 provider 业务失败必须抛出明确上游错误。"""
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = provider_result

        with pytest.raises(APIResponseError, match=provider_result.message):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_rejects_invalid_provider_schema(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """provider detail 违反统一 schema 时必须明确失败。"""
        data = uniform_detail_data(methods=["DELETE"])
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.return_value = uniform_result(data=data)

        with pytest.raises(APIResponseError, match="validate response data error"):
            service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

    @patch("bkflow.plugin.services.plugin_detail._get_api_credential", create=True)
    @patch("bkflow.plugin.services.plugin_detail.UniformAPIClient", create=True)
    def test_uniform_adapter_does_not_cache_form_context(
        self,
        client_cls,
        get_credential,
        available_open_plugin,
        service,
    ):
        """每次详情请求都使用 provider 当前返回的 form_context。"""
        get_credential.return_value = {"bk_app_code": "bkflow", "bk_app_secret": "secret"}
        client_cls.return_value.request.side_effect = [
            uniform_result(data=uniform_detail_data(form_context={"biz_cc_id": 100605})),
            uniform_result(data=uniform_detail_data(form_context={"biz_cc_id": 100606})),
        ]

        first = service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")
        second = service.get_detail("uniform_api", available_open_plugin.plugin_id, "v2.0", "sops")

        assert first["form_context"] == {"biz_cc_id": 100605}
        assert second["form_context"] == {"biz_cc_id": 100606}
        assert client_cls.return_value.request.call_count == 2
