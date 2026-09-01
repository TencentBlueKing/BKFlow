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

from bkflow.apigw.serializers.harness.common import ENVELOPE_FIELDS
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import HarnessAuthorizationError
from bkflow.harness.services.facade import HarnessFacade, normalize_errors
from bkflow.harness.services.validator import _envelope, _error
from bkflow.utils import err_code


def dispatch_harness_tool(request, space_id, serializer_cls, method_name):
    """校验传输层输入，推导可信上下文，并调用对应 Facade 方法。"""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    try:
        context = TrustedHarnessContext.from_request(request, int(space_id))
    except HarnessAuthorizationError as exc:
        envelope = _envelope(
            ok=False,
            run_id=None,
            revision_id=None,
            plan_hash=None,
            status=None,
            summary="authorization failed",
            artifact_refs=[],
            errors=[
                _error(
                    "PERMISSION" if "FORBIDDEN" in exc.code or exc.code.endswith("DISABLED") else exc.code,
                    exc.message,
                )
            ],
            next_actions=[],
            correlation_id=getattr(request, "trace_id", None),
        )
        envelope["errors"] = normalize_errors(envelope["errors"])
        return {
            "result": False,
            "data": {key: envelope.get(key) for key in ENVELOPE_FIELDS},
            "code": err_code.VALIDATION_ERROR.code,
        }

    serializer = serializer_cls(data=payload)
    if not serializer.is_valid():
        envelope = _envelope(
            ok=False,
            run_id=None,
            revision_id=None,
            plan_hash=None,
            status=None,
            summary="invalid request",
            artifact_refs=[],
            errors=[_error("USER_INPUT", str(serializer.errors))],
            next_actions=[],
            correlation_id=context.correlation_id,
        )
        envelope["errors"] = normalize_errors(envelope["errors"])
        return {
            "result": False,
            "data": {key: envelope.get(key) for key in ENVELOPE_FIELDS},
            "code": err_code.VALIDATION_ERROR.code,
        }

    envelope = getattr(HarnessFacade(), method_name)(context, serializer.validated_data)
    return {
        "result": bool(envelope.get("ok")),
        "data": {key: envelope.get(key) for key in ENVELOPE_FIELDS},
        "code": err_code.SUCCESS.code if envelope.get("ok") else err_code.VALIDATION_ERROR.code,
    }
