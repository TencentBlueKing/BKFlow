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

from bamboo_engine import local as engine_local
from werkzeug.local import Local

local = Local()


class TraceIDInjectFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = getattr(local, "trace_id", None)
        return True


class BambooEngineNodeInfoFilter(logging.Filter):
    def filter(self, record):
        node_info = engine_local.get_node_info()
        if node_info:
            record.node_id = node_info.node_id
            record.version = node_info.version
        return True
