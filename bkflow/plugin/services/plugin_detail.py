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

from copy import deepcopy
from urllib.parse import urljoin

from django.conf import settings
from pipeline.component_framework.library import ComponentLibrary
from pipeline.component_framework.models import ComponentModel
from pipeline.exceptions import ComponentNotExistException
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from bkflow.bk_plugin.models import BKPluginAuthorization
from bkflow.exceptions import APIResponseError
from bkflow.pipeline_plugins.query.uniform_api.uniform_api import _get_api_credential
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from plugin_service.exceptions import PluginServiceException
from plugin_service.plugin_client import PluginServiceApiClient

DETAIL_DEFAULTS = {
    "plugin_type": "",
    "plugin_code": "",
    "plugin_version": "",
    "source_key": "",
    "plugin_source": None,
    "protocol": "",
    "wrapper_version": None,
    "name": "",
    "description": "",
    "inputs": [],
    "outputs": [],
    "credentials": [],
    "forms": {"input": None, "output": None},
    "form_schema": None,
    "form_context": {},
    "execution_kind": "",
    "url": None,
    "methods": [],
    "response_data_path": None,
    "polling": {},
    "callback": {},
    "credential_key": None,
}


def build_detail(**values):
    """构建固定 key 集合的插件详情。"""
    detail = deepcopy(DETAIL_DEFAULTS)
    detail.update(values)
    detail["forms"] = {
        "input": (detail.get("forms") or {}).get("input"),
        "output": (detail.get("forms") or {}).get("output"),
    }
    return detail


def _json_value(value):
    """把惰性翻译对象和嵌套值转换为纯 JSON 类型。"""
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _component_value(component_cls, attribute, default=None):
    """兼容组件的类属性和无参 callable 属性。"""
    value = getattr(component_cls, attribute, default)
    return value() if callable(value) else value


def _normalize_io_fields(fields, is_output=False):
    """按 PluginSchemaService 语义规范 IO 列表，并兼容远端 JSON schema。"""
    if isinstance(fields, dict):
        required_fields = set(fields.get("required") or [])
        fields = [
            dict(
                value,
                key=key,
                name=value.get("name", value.get("title", "")),
                required=key in required_fields,
            )
            for key, value in (fields.get("properties") or {}).items()
        ]
    return _json_value(PluginSchemaService._normalize_io_fields(fields or [], is_output=is_output))


def _form_descriptor(form_type, key, data, is_embedded, base):
    """构建具有固定字段集合的表单描述。"""
    return _json_value(
        {
            "type": form_type,
            "key": key,
            "data": data,
            "is_embedded": is_embedded,
            "base": base,
        }
    )


def _absolute_form_path(form):
    """将非内嵌组件的相对表单路径转换为站点绝对地址。"""
    if not isinstance(form, str) or not form or form.startswith(("http://", "https://", "//")):
        return form
    return urljoin("{}/".format(settings.SITE_URL.rstrip("/")), form.lstrip("/"))


def _require_remote_data(response, action):
    """验证插件服务响应，异常结构统一视为上游故障。"""
    if (
        not isinstance(response, dict)
        or response.get("result") is not True
        or not isinstance(response.get("data"), dict)
    ):
        raise APIException("插件服务上游故障：{}".format(action))
    return response["data"]


def _is_valid_remote_io_fields(fields):
    """仅接受远端协议约定的列表或 JSON Schema 对象。"""
    if isinstance(fields, list):
        return all(isinstance(field, dict) for field in fields)
    if not isinstance(fields, dict):
        return False
    properties = fields.get("properties", {})
    return isinstance(properties, dict) and all(isinstance(field, dict) for field in properties.values())


class PluginDetailService:
    """按插件类型构建统一的原生表单详情契约。"""

    ADAPTERS = {
        "component": "_get_component_detail",
        "remote_plugin": "_get_remote_plugin_detail",
        "uniform_api": "_get_uniform_api_detail",
    }

    def __init__(self, space_id, template_id, operator, scope_type="", scope_value=""):
        self.space_id = str(space_id)
        self.template_id = str(template_id)
        self.operator = operator
        self.scope_type = scope_type
        self.scope_value = scope_value

    def get_detail(self, plugin_type, plugin_code, plugin_version, source_key=""):
        """获取指定插件的详情。"""
        method = getattr(self, self.ADAPTERS[plugin_type])
        return method(plugin_code, plugin_version, source_key)

    def _form_context(self):
        """构建本地 adapter 共用的纯 JSON 表单上下文。"""
        return {
            "project": None,
            "biz_cc_id": int(self.scope_value) if self.scope_type in ("biz", "cmdb_biz") and self.scope_value else None,
            "site_url": settings.SITE_URL,
            "component": None,
            "variable": None,
            "template": None,
            "instance": None,
            "bk_plugin_api_host": {},
        }

    def _get_component_detail(self, plugin_code, plugin_version, source_key):
        """构建内置组件的原生 component_js 表单详情。"""
        component_model = ComponentModel.objects.filter(
            code=plugin_code,
            version=plugin_version,
            status=True,
        ).first()
        if component_model is None:
            raise NotFound("插件版本不存在或已下架")

        try:
            component_cls = ComponentLibrary.get_component_class(plugin_code, plugin_version)
        except ComponentNotExistException as exc:
            raise NotFound("插件版本不存在或已下架") from exc
        is_embedded = bool(_component_value(component_cls, "form_is_embedded", False))
        base = _json_value(_component_value(component_cls, "base", None))
        form = _json_value(_component_value(component_cls, "form", None))
        output_form = _json_value(_component_value(component_cls, "output_form", None))
        if is_embedded:
            output_form = _json_value(_component_value(component_cls, "embedded_output_form", output_form))
        else:
            form = _absolute_form_path(form)
            output_form = _absolute_form_path(output_form)
        component_name = str(component_model.name).split("-", 1)[-1].strip()

        return build_detail(
            plugin_type="component",
            plugin_code=plugin_code,
            plugin_version=plugin_version,
            source_key="bkflow",
            plugin_source="builtin",
            protocol="native",
            execution_kind="component",
            name=component_name,
            description=_json_value(_component_value(component_cls, "desc", "")),
            inputs=_normalize_io_fields(_component_value(component_cls, "inputs_format", [])),
            outputs=_normalize_io_fields(_component_value(component_cls, "outputs_format", []), is_output=True),
            forms={
                "input": _form_descriptor("component_js", plugin_code, form, is_embedded, base) if form else None,
                "output": (
                    _form_descriptor("component_js", plugin_code, output_form, is_embedded, base)
                    if output_form
                    else None
                ),
            },
            form_context=_json_value(self._form_context()),
        )

    def _get_remote_plugin_detail(self, plugin_code, plugin_version, source_key):
        """构建空间已授权远程插件的原生表单详情。"""
        authorized_codes = BKPluginAuthorization.objects.get_codes_by_space_id(str(self.space_id))
        if plugin_code not in authorized_codes:
            raise PermissionDenied("插件未授权给当前空间")

        try:
            client = PluginServiceApiClient(plugin_code)
            meta_data = _require_remote_data(client.get_meta(), "查询插件版本")
        except PluginServiceException as exc:
            raise APIException("插件服务上游故障：查询插件版本") from exc

        versions = meta_data.get("versions", [])
        if not isinstance(versions, (list, tuple)):
            raise APIException("插件服务上游故障：查询插件版本")
        if plugin_version not in versions:
            raise NotFound("插件版本不存在或已下架")

        try:
            data = _require_remote_data(client.get_detail(plugin_version), "查询插件详情")
        except PluginServiceException as exc:
            raise APIException("插件服务上游故障：查询插件详情") from exc

        forms = data.get("forms", {})
        if not isinstance(forms, dict):
            raise APIException("插件服务上游故障：查询插件详情")
        renderform = forms.get("renderform")
        inputs_schema = data.get("inputs", [])
        if not _is_valid_remote_io_fields(inputs_schema):
            raise APIException("插件服务上游故障：查询插件详情")
        outputs = data.get("outputs", [])
        if not _is_valid_remote_io_fields(outputs):
            raise APIException("插件服务上游故障：查询插件详情")
        input_form = (
            _form_descriptor("renderform", plugin_code, renderform, True, None)
            if renderform
            else _form_descriptor("jsonschema", plugin_code, inputs_schema, True, None)
        )

        return build_detail(
            plugin_type="remote_plugin",
            plugin_code=plugin_code,
            plugin_version=plugin_version,
            source_key="bkflow",
            plugin_source="third_party",
            protocol="plugin_service",
            execution_kind="remote_plugin",
            name=_json_value(data.get("name", "")),
            description=_json_value(data.get("description", data.get("desc", ""))),
            inputs=_normalize_io_fields(inputs_schema),
            outputs=_normalize_io_fields(outputs, is_output=True),
            credentials=_json_value(data.get("credentials", [])),
            forms={"input": input_form, "output": None},
            form_context=_json_value(self._form_context()),
        )

    def _get_uniform_api_detail(self, plugin_code, plugin_version, source_key):
        """构建通过本地目录准入校验的 uniform_api 详情。"""
        schema_service = PluginSchemaService(
            space_id=self.space_id,
            username=self.operator,
            scope_type=self.scope_type,
            scope_id=self.scope_value,
        )
        try:
            api_item = schema_service._get_single_by_type(
                plugin_code,
                "uniform_api",
                version=plugin_version,
                source_key=source_key,
            )
        except ValueError as exc:
            message = str(exc)
            if "未准入" in message or "未开放" in message:
                raise PermissionDenied(message) from exc
            raise NotFound(message) from exc

        if api_item.get("source_key") != source_key:
            raise PermissionDenied("插件来源与请求不一致")
        meta_url = schema_service._build_uniform_api_meta_url(api_item, plugin_version)

        credential = _get_api_credential(
            space_id=self.space_id,
            template_id=self.template_id,
        )
        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential["bk_app_code"],
            app_secret=credential["bk_app_secret"],
            username=self.operator,
        )
        result = client.request(
            url=meta_url,
            method="GET",
            data={
                "source_key": source_key,
                "scope_type": self.scope_type,
                "scope_value": self.scope_value,
            },
            headers=headers,
            username=self.operator,
        )
        if not result.result:
            raise APIResponseError("请求统一API元数据失败: {}".format(result.message))
        if not isinstance(result.json_resp, dict) or result.json_resp.get("result") is not True:
            message = result.json_resp.get("message", "") if isinstance(result.json_resp, dict) else ""
            raise APIResponseError("请求统一API元数据失败: {}".format(message or "provider 返回失败"))

        data = result.json_resp.get("data")
        if not isinstance(data, dict):
            raise APIResponseError("请求统一API元数据失败: 响应体缺少 data 对象")

        provider_version = data.get("plugin_version")
        is_v4_provider = any(
            str(wrapper_version or "").lower().lstrip("v").split(".", 1)[0] == "4"
            for wrapper_version in (api_item.get("wrapper_version"), data.get("wrapper_version"))
        )
        if is_v4_provider and not provider_version:
            raise APIResponseError("V4 统一API响应缺少 plugin_version，无法校验请求版本 [{}]".format(plugin_version))
        if provider_version is not None and str(provider_version) != str(plugin_version):
            raise APIResponseError(
                "统一API响应插件版本与请求版本不一致: 请求版本 [{}], 响应版本 [{}]".format(
                    plugin_version,
                    provider_version,
                )
            )

        client.validate_response_data(data, client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

        return build_detail(
            plugin_type="uniform_api",
            plugin_code=plugin_code,
            plugin_version=plugin_version,
            source_key=source_key,
            plugin_source=_json_value(data.get("plugin_source", api_item.get("plugin_source"))),
            protocol="uniform_api",
            wrapper_version=_json_value(data.get("wrapper_version", api_item.get("wrapper_version"))),
            name=_json_value(data.get("name", api_item.get("name", ""))),
            description=_json_value(data.get("description", data.get("desc", api_item.get("description", "")))),
            inputs=_json_value(data.get("inputs", [])),
            outputs=_json_value(data.get("outputs", [])),
            credentials=_json_value(data.get("credentials", [])),
            forms=_json_value(data.get("forms", {"input": None, "output": None})),
            form_schema=_json_value(data.get("form_schema")),
            form_context=_json_value(data.get("form_context", {})),
            execution_kind="uniform_api",
            url=_json_value(data.get("url")),
            methods=_json_value(data.get("methods", [])),
            response_data_path=_json_value(data.get("response_data_path")),
            polling=_json_value(data.get("polling", {})),
            callback=_json_value(data.get("callback", {})),
            credential_key=_json_value(data.get("credential_key")),
        )
