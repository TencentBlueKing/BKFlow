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
from functools import wraps

from django.core.handlers.wsgi import WSGIRequest
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.request import Request

from bkflow.exceptions import ValidationError


def params_valid(serializer: serializers.Serializer, add_params: bool=True):
    """参数校验装饰器

    :param serializer: serializer类
    :param add_params: 是否将校验后的参数添加到request.cleaned_params中
    :return: 参数校验装饰器
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            # 获得Django的request对象
            _request = kwargs.get("request")

            if not _request:
                for arg in args:
                    if isinstance(arg, (Request, WSGIRequest)):
                        _request = arg
                        break

            if not _request:
                raise ValidationError(_("该装饰器只允许用于Django的View函数(包括普通View函数和Class-base的View函数)"))

            # 校验request中的参数
            params = {}
            if _request.method in ["GET"]:
                if isinstance(_request, Request):
                    params = _request.query_params
                else:
                    params = _request.GET
            elif _request.is_ajax():
                if isinstance(_request, Request):
                    params = _request.data
                else:
                    params = _request.json()
            else:
                if isinstance(_request, Request):
                    params = _request.data
                else:
                    params = _request.POST

            cleaned_params = custom_params_valid(serializer=serializer, params=params)
            _request.cleaned_params = cleaned_params

            # 执行实际的View逻辑
            params_add = False
            try:
                # 语法糖，使用这个decorator的话可直接从view中获得参数的字典
                if "params" not in kwargs and add_params:
                    kwargs["params"] = cleaned_params
                    params_add = True
            except TypeError:
                if params_add:
                    del kwargs["params"]
            resp = view_func(*args, **kwargs)
            return resp

        return wrapper

    return decorator


def format_serializer_errors(errors: dict, fields: dict, params: dict, prefix: str="  "):
    """格式化序列化器错误信息

    :param errors: 错误信息
    :param fields: 序列化器字段
    :param params: 参数
    :return: 格式化后的错误信息
    """
    message = _("参数校验失败:{wrap}").format(wrap="\n") if prefix == "  " else "\n"
    for key, field_errors in list(errors.items()):
        sub_message = ""
        label = key
        if key not in fields:
            sub_message = json.dumps(field_errors, ensure_ascii=False)
        else:
            field = fields[key]
            label = field.label or field.field_name
            if (
                hasattr(field, "child")
                and isinstance(field_errors, list)
                and len(field_errors) > 0
                and not isinstance(field_errors[0], str)
            ):
                for index, sub_errors in enumerate(field_errors):
                    if sub_errors:
                        sub_format = format_serializer_errors(
                            sub_errors, field.child.fields, params, prefix=prefix + "    "
                        )
                        # return sub_format
                        sub_message += _("{wrap}{prefix}第{index}项:").format(
                            wrap="\n",
                            prefix=prefix + "  ",
                            index=index + 1,
                        )
                        sub_message += sub_format
            else:
                if isinstance(field_errors, dict):
                    if hasattr(field, "child"):
                        sub_foramt = format_serializer_errors(
                            field_errors, field.child.fields, params, prefix=prefix + "  "
                        )
                    else:
                        sub_foramt = format_serializer_errors(field_errors, field.fields, params, prefix=prefix + "  ")
                    sub_message += sub_foramt
                elif isinstance(field_errors, list):
                    for index in range(len(field_errors)):
                        field_errors[index] = field_errors[index].format(**{key: params.get(key, "")})
                        sub_message += "{index}.{error}".format(index=index + 1, error=field_errors[index])
                    sub_message += "\n"
        # 对使用 Validate() 时 label == 'non_field_errors' 的特殊情况做处理
        if label == "non_field_errors":
            message += "{prefix} {message}".format(prefix=prefix, message=sub_message)
        else:
            message += "{prefix}{label}: {message}".format(prefix=prefix, label=label, message=sub_message)
    return message


def custom_params_valid(serializer: serializers.Serializer, params: dict, many: bool=False):
    """校验参数

    :param serializer: 校验器
    :param params: 原始参数
    :param many: 是否为多个参数
    :return: 校验通过的参数
    """
    _serializer = serializer(data=params, many=many)
    try:
        _serializer.is_valid(raise_exception=True)
    except serializers.ValidationError as e:  # pylint: disable=broad-except # noqa
        try:
            message = format_serializer_errors(_serializer.errors, _serializer.fields, params)
        except Exception as e:  # pylint: disable=broad-except
            if isinstance(e.message, str):
                message = e.message
            else:
                message = _("参数校验失败，详情请查看返回的errors")
        raise ValidationError(message=message, errors=_serializer.errors)
    return list(_serializer.validated_data) if many else dict(_serializer.validated_data)