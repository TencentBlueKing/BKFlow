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


class CustomCredential(BaseCredential):
    """
    自定义凭证，支持任意key-value对
    """

    def value(self):
        """
        获取凭证真实值

        :return: 凭证的实际内容
        """
        # todo 这里会涉及到加解密的操作
        return self.data

    def display_value(self):
        """
        获取凭证脱敏后的值

        :return: 脱敏后的凭证内容（所有value替换为星号）
        """
        display_data = {}
        for key in self.data.keys():
            display_data[key] = "*********"
        return display_data

    def validate_data(self):
        """
        校验凭证数据格式

        :return: 验证后的数据
        """
        if not isinstance(self.data, dict):
            raise serializers.ValidationError("自定义凭证内容必须是字典类型")

        if not self.data:
            raise serializers.ValidationError("自定义凭证内容不能为空")

        for key, value in self.data.items():
            if not isinstance(key, str):
                raise serializers.ValidationError(f"凭证key必须是字符串类型: {key}")
            if not isinstance(value, str):
                raise serializers.ValidationError(f"凭证value必须是字符串类型: {key}={value}")
            # 验证值不是全为 '*'
            if all(char == "*" for char in value):
                raise serializers.ValidationError(f"凭证值格式有误，不应全为 * 字符: {key}")

        return self.data
