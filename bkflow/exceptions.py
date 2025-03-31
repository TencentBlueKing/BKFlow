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


class BKFLOWException(Exception):
    CODE = None
    MESSAGE = None
    STATUS_CODE = 500

    def __init__(self, message=""):
        self.message = f"{self.MESSAGE}: {message}" if self.MESSAGE else f"{message}"

    def __str__(self):
        return self.message


class ValidationError(BKFLOWException):
    pass


class NotFoundError(BKFLOWException):
    pass


class UnknownError(BKFLOWException):
    pass


class UserNotFound(BKFLOWException):
    pass


class APIRequestError(BKFLOWException):
    STATUS_CODE = 400


class APIResponseError(BKFLOWException):
    pass


class UnAuthorization(BKFLOWException):
    pass
