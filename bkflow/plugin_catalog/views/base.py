"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (see LICENSE for details).
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from bkflow.exceptions import BKFLOWException, NotFoundError, ValidationError
from bkflow.utils.views import SimpleGenericViewSet
from rest_framework.response import Response


class PluginCatalogErrorMixin:
    """
    插件目录（管理后台）接口统一的错误响应约定。

    父类 `SimpleGenericViewSet` 的既有约定是「异常时把 HTTP 状态码强制改成 200，
    错误信息放在 `message` 里」——这是项目里其它模块（画布侧）依赖的约定，前端用
    `result` 字段判断成败。但插件目录管理后台的前端要求**用 HTTP 状态码区分成败**：
    参数/业务校验错误应是 400、资源不存在应是 404，未知错误才是 500，
    否则前端拿到 500 无法区分「用户填错了」和「服务端炸了」。

    这里统一改成：

    - HTTP 状态码：参数/业务校验错误 400、资源不存在 404、其它 500
    - 响应体：`{"result": false, "data": null, "code": <与状态码一致>, "message": "..."}`
      （与项目其它模块 `return_json_response` 的响应格式保持一致）

    业务异常（`bkflow.exceptions.*`）不是 DRF 的异常，DRF 默认会把它们当未知异常
    直接冒泡成 500 页面；这里统一拦下来转成带标准 code 的响应。
    """

    def handle_exception(self, exc):
        if isinstance(exc, BKFLOWException):
            status_code = self._error_status_code(exc)
            response = Response(
                {"result": False, "data": None, "code": status_code, "message": str(exc)},
                status=status_code,
            )
            response.exception = True
            # 标记一下：finalize_response 里据此跳过父类「异常一律改成 200」的逻辑
            response.plugin_catalog_error = True
            return response
        return super().handle_exception(exc)

    @staticmethod
    def _error_status_code(exc):
        if isinstance(exc, NotFoundError):
            return 404
        if isinstance(exc, ValidationError):
            return 400
        return 500

    def finalize_response(self, request, response, *args, **kwargs):
        if getattr(response, "plugin_catalog_error", False):
            # 已是标准错误响应：保留真实状态码，只借用 DRF 的收尾逻辑（渲染器协商等），
            # 绕过父类把状态码强制改成 200 的那段。
            return super(SimpleGenericViewSet, self).finalize_response(request, response, *args, **kwargs)
        return super().finalize_response(request, response, *args, **kwargs)
