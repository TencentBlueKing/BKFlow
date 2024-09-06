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
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from bkflow.admin.models import ModuleInfo
from bkflow.admin.serializers import ModuleInfoSerializer
from bkflow.utils.mixins import BKFLOWDefaultPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import SimpleGenericViewSet


class ModuleInfoAdminViewSet(ModelViewSet, SimpleGenericViewSet):
    queryset = ModuleInfo.objects.all()
    serializer_class = ModuleInfoSerializer
    pagination_class = BKFLOWDefaultPagination
    permission_classes = [AdminPermission]

    @action(methods=["get"], detail=False)
    def get_meta(self, request, *args, **kwargs):
        meta_info = {}
        for f in ModuleInfo._meta.get_fields():
            meta_info[f.name] = {"verbose_name": f.verbose_name}
            if getattr(f, "choices"):
                meta_info[f.name].update({"choices": [{"value": c[0], "text": c[1]} for c in f.choices]})
        return Response(meta_info)
