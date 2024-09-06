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

from datetime import datetime

from django.utils.translation import ugettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.permission.exceptions import TokenRenewalException
from bkflow.permission.models import Token
from bkflow.utils.views import ReadOnlyViewSet


class TokenViewSet(ReadOnlyViewSet):
    queryset = Token.objects.filter(expired_time__gte=datetime.now())

    @swagger_auto_schema(
        method="POST",
        operation_summary="续期",
    )
    @action(methods=["POST"], detail=True)
    def renewal(self, request, *args, **kwargs):
        obj = self.get_object()

        if request.user.username != obj.user:
            raise TokenRenewalException(_("Token 续期失败，当前续期的用户与正在登录的用户不一致"))

        result, message = obj.renewal()

        return Response({"result": result, "message": message, "expired_time": obj.expired_time})
