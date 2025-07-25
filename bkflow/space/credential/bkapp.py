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
from rest_framework import serializers

from bkflow.space.credential.base import BaseCredential


class BkAppCredential(BaseCredential):
    class BkAppSerializer(serializers.Serializer):
        bk_app_code = serializers.CharField(required=True)
        bk_app_secret = serializers.CharField(required=True)

        def validate_bk_app_secret(self, value):
            # 验证字段 bk_app_secret 的值，确保它不是全为 '*'
            if all(char == "*" for char in value):
                raise serializers.ValidationError("bk_app_secret 格式有误 不应全为 * 字符")
            return value

    def value(self):
        # todo 这里会涉及到加解密的操作
        return self.data

    def display_value(self):
        self.data["bk_app_secret"] = "*********"
        return self.data

    def validate_data(self):
        ser = self.BkAppSerializer(data=self.data)
        ser.is_valid(raise_exception=True)
        return ser.validated_data
