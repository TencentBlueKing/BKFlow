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

UNIFORM_API_PLUGIN_API_META_INPUT_KEY = "uniform_api_plugin_api_meta"


def build_api_meta_span_attributes(api_meta):
    """从 API 插件元信息中提取适合检索的 Span 属性"""
    if not isinstance(api_meta, dict):
        return {}

    category = api_meta.get("category") or {}
    attributes = {
        "api_id": api_meta.get("id"),
        "api_name": api_meta.get("name"),
        "api_key": api_meta.get("api_key"),
    }

    if isinstance(category, dict):
        attributes.update(
            {
                "api_category_id": category.get("id"),
                "api_category_name": category.get("name"),
            }
        )

    return {key: value for key, value in attributes.items() if value not in (None, "")}


def get_uniform_api_span_attributes(data):
    """获取 API 插件通用 Span 属性"""
    attributes = {
        "url": data.get_one_of_inputs("uniform_api_plugin_url", ""),
        "http_method": data.get_one_of_inputs("uniform_api_plugin_method", ""),
    }
    api_meta = data.get_one_of_inputs(UNIFORM_API_PLUGIN_API_META_INPUT_KEY, {})
    attributes.update(build_api_meta_span_attributes(api_meta))
    return attributes
