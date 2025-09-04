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
import datetime
import decimal
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.utils.timezone import is_aware


def format_datetime(dt: datetime.datetime, tz: datetime.tzinfo = None):
    """
    时间转换为字符串格式（附带时区）
    """
    # translate to time in local timezone
    if timezone.is_aware(dt):
        dt = dt.astimezone(tz) if tz else timezone.localtime(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S %z")


def json_encoder_default(self, o):
    # See "Date Time String Format" in the ECMA-262 specification.
    if isinstance(o, Promise):
        return force_str(o)
    elif isinstance(o, datetime.datetime):
        r = o.isoformat()
        if o.microsecond:
            r = r[:23] + r[26:]
        if r.endswith("+00:00"):
            r = r[:-6] + "Z"
        return r
    elif isinstance(o, datetime.date):
        return o.isoformat()
    elif isinstance(o, datetime.time):
        if is_aware(o):
            raise ValueError("JSON can't represent timezone-aware times.")
        r = o.isoformat()
        if o.microsecond:
            r = r[:12]
        return r
    elif isinstance(o, (decimal.Decimal, uuid.UUID)):
        return str(o)
    elif isinstance(o, bytes):
        return o.decode("utf-8")
    else:
        try:
            return super(DjangoJSONEncoder, self).default(o)
        except TypeError:
            return str(o)
