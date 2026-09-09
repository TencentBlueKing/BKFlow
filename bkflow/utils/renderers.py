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

import math

from rest_framework.renderers import JSONRenderer
from rest_framework.settings import api_settings
from rest_framework.utils.encoders import JSONEncoder


def _prepare_display_value(value):
    """复制 JSON 容器，将非有限数值及含不支持键的字典转换为展示文本。"""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        if any(
            (key is not None and not isinstance(key, (str, int, float, bool)))
            or (isinstance(key, float) and not math.isfinite(key))
            for key in value
        ):
            # 不逐个 str(key)，避免 tuple 键与同名字符串键相互覆盖。
            return repr(value)
        return {key: _prepare_display_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_prepare_display_value(item) for item in value]
    return value


class _DisplayJSONEncoder(JSONEncoder):
    """沿用 DRF 的类型编码，仅对不能表示的 Python 对象提供展示文本。"""

    def default(self, value):
        """保留日期等既有行为，兼容 Fraction、非 UTF-8 bytes 等特殊值。"""
        try:
            return _prepare_display_value(super().default(value))
        except (TypeError, ValueError):
            return repr(value)


class _EscapedDisplayJSONRenderer(JSONRenderer):
    """通过 JSON 转义保留未配对代理字符，不替换或丢弃原字符。"""

    ensure_ascii = True
    encoder_class = _DisplayJSONEncoder


class NodeDetailJSONRenderer(JSONRenderer):
    """仅用于节点详情 HTTP 响应，不用于执行结果或持久化序列化。"""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """普通响应保持不变，特殊值仅在渲染副本中降级展示。"""
        try:
            return super().render(data, accepted_media_type, renderer_context)
        except (TypeError, ValueError):
            # UnicodeEncodeError/UnicodeDecodeError 也是 ValueError。
            # engine 返回的 JSON 在 interface 解码后仍可能含代理字符，故两跳均需使用。
            return _EscapedDisplayJSONRenderer().render(
                _prepare_display_value(data), accepted_media_type, renderer_context
            )


def get_node_detail_renderer_classes():
    """只替换默认 JSON renderer，保留既有响应格式、顺序及自定义 renderer。"""
    return [
        NodeDetailJSONRenderer if renderer is JSONRenderer else renderer
        for renderer in api_settings.DEFAULT_RENDERER_CLASSES
    ]
