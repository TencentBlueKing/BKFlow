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
import json


def format_drf_serializers_exception(error):
    err_dict = {}

    # 不是所有的error都有详情
    if getattr(error, "detail") is None:
        return str(error)

    try:
        for field, error_details in error.detail.items():
            messages = []
            # 有可能一个字段存在多个异常
            for error_detail in error_details:
                messages.append(str(error_detail))

            err_dict[field] = ",".join(messages)
    except Exception:
        return str(error)

    return json.dumps(err_dict)
