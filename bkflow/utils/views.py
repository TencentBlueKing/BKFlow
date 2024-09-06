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
import logging

from rest_framework import mixins, status
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from bkflow.utils.mixins import CustomViewSetMixin
from bkflow.utils.permissions import AdminPermission

logger = logging.getLogger("root")


class SimpleGenericViewSet(GenericViewSet):
    """
    最基础的视图函数，不支持model, view_set 的 创建，查看，更新，删除方法，只支持用户自定义的action
    """

    EXEMPT_STATUS_CODES = {status.HTTP_204_NO_CONTENT}
    RESPONSE_WRAPPER = None

    def default_response_wrapper(self, data):
        return {"result": True, "data": data, "code": "0", "message": ""}

    def finalize_response(self, request, response, *args, **kwargs):
        # 对rest_framework的Response进行统一处理

        if isinstance(response, Response):
            if response.exception is True:
                # todo 需要处理下用户异常自定义的Code
                error = response.data.get("detail") or response.data or ErrorDetail("Error from API exception")
                error_code = getattr(error, "code", 500)
                logger.error(
                    f"[ApiMixin response exception] request: {request.path}, "
                    f"params: {request.query_params or request.data}, response: {response.data}"
                )
                response.status_code = 200
                response.data = {"result": False, "data": response.data, "code": error_code, "message": str(error)}
            elif self.RESPONSE_WRAPPER and callable(self.RESPONSE_WRAPPER):
                response.data = self.RESPONSE_WRAPPER(response.data)
            elif response.status_code not in self.EXEMPT_STATUS_CODES:
                response.data = self.default_response_wrapper(response.data)

        return super(SimpleGenericViewSet, self).finalize_response(request, response, *args, **kwargs)


class UserModelViewSet(CustomViewSetMixin, SimpleGenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    """
    用户视图的view set 不支持创建，删除，和列表视图
    """


class ReadOnlyViewSet(SimpleGenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """
    用户视图的view set 不支持创建，删除，和列表视图
    """


class AdminModelViewSet(CustomViewSetMixin, ModelViewSet, SimpleGenericViewSet):
    """
    管理员视角的ViewSet支持所有操作
    """

    permission_classes = [AdminPermission]
