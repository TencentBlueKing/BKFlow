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
import logging

from cryptography.fernet import Fernet

import env
from config.default import BKAPP_INNER_CALLBACK_ENTRY

logger = logging.getLogger("celery")


def get_node_callback_url(space_id, task_id, node_id, node_version=""):
    f = Fernet(env.CALLBACK_KEY)
    callback_entry = BKAPP_INNER_CALLBACK_ENTRY + "callback/%s/"
    return (
        callback_entry
        % f.encrypt(bytes("{}:{}:{}:{}".format(space_id, task_id, node_id, node_version), encoding="utf8")).decode()
    )


def convert_dict_value(data):
    # 将默认的 inputs 的 value 尝试 json loads 成 python 的基本对象类型
    inputs_data = {}
    for key, value in data.items():
        try:
            inputs_data[key] = json.loads(value)
        except Exception as e:
            logger.exception("convert value failed, key={}, value={}, err={}".format(key, value, e))
            inputs_data[key] = value
    return inputs_data
