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
from functools import wraps

from bkflow.contrib.operation_record import OPERATION_RECORDER

logger = logging.getLogger("root")


def record_operation(recorder_type: str, operate_type: str, operate_source: str, extra_info: dict = None):
    """
    记录操作日志
    """

    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                adjusted_operate_type = operate_type
                if kwargs.get("loop", False) and operate_type == "skip":
                    adjusted_operate_type = "loop_skip"
                elif kwargs.get("loop", False) and operate_type == "retry":
                    adjusted_operate_type = "loop_retry"
                recorder = OPERATION_RECORDER.recorders[recorder_type](
                    adjusted_operate_type, operate_source, extra_info
                )
                record_kwargs = {**kwargs, "func_result": result}
                recorder.record(*args, **record_kwargs)
            except Exception as e:
                logger.exception(f"record operate failed, error:{e}")
            return result

        return decorator

    return wrapper
