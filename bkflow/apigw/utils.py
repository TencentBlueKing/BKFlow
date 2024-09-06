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
import traceback

from bkflow.apigw.exceptions import PaginateParamsException
from bkflow.space.models import SpaceConfig

logger = logging.getLogger("root")


def get_space_config_presentation(space_id: int):
    """
    @summary: 获取space_id对应的空间相关配置信息
    @param space_id: 空间ID
    @return: 所有空间相关配置信息
    {
        "space_id": 1,
        "config": [{"key": "key1", "value": "value1"}]
    }
    """
    return {"space_id": int(space_id), "config": SpaceConfig.objects.get_space_config_info(space_id=space_id)}


def paginate_list_data(request, queryset):
    """
    @summary: 读取request中的offset和limit参数，对筛选出的queryset进行分页
    @return: 分页结果列表, 分页前数据总数
    """
    try:
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 100))
        # limit 最大数量为200
        limit = 200 if limit > 200 else limit
        count = queryset.count()

        if offset < 0 or limit < 0:
            raise PaginateParamsException("offset and limit must be greater or equal to 0.")
        else:
            results = queryset[offset : offset + limit]
        return results, count
    except Exception as e:
        message = "[API] pagination error: {}".format(e)
        logger.error(message + "\n traceback: {}".format(traceback.format_exc()))
        raise Exception(message)
