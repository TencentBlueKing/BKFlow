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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""


class HarnessServiceError(RuntimeError):
    """Base class for deterministic Harness service failures."""


class InvalidStateTransition(HarnessServiceError):
    """Raised when a state change is outside the approved P0 graph."""


class IdempotencyConflict(HarnessServiceError):
    """Raised when one idempotency key is reused for another request."""


class IdempotencyInFlight(HarnessServiceError):
    """Raised when an acquired idempotency record is still being processed."""


class IdempotencyRecordImmutable(HarnessServiceError):
    """Raised when a completed idempotency record would be changed."""
