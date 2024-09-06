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

import jsonschema
from django.db.models import QuerySet

from bkflow.exceptions import ValidationError

logger = logging.getLogger("root")


class SpacePluginConfigParser:
    SPACE_PLUGIN_CONFIG_SCHEMA = {
        "type": "object",
        "required": ["default"],
        "properties": {
            "default": {
                "type": "object",
                "required": ["mode", "plugin_codes"],
                "properties": {
                    "mode": {"type": "string", "enum": ["allow_list", "deny_list"]},
                    "plugin_codes": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }

    def __init__(self, config: dict, *args, **kwargs):
        self.config = config
        if kwargs.get("validate", True):
            self.is_valid(raise_exception=True)

    def is_valid(self, raise_exception=True, *args, **kwargs):
        try:
            jsonschema.validate(instance=self.config, schema=self.SPACE_PLUGIN_CONFIG_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            logger.exception(f"SpacePluginConfigParser is_valid error: {e}")
            if raise_exception:
                raise ValidationError(f"SpacePluginConfigParser is_valid error: {e}")
            return False
        return True

    def get_scope_config(self, scope: str, *args, **kwargs):
        return self.config.get(scope, self.config["default"])

    def get_filtered_plugins(self, scope: str, plugin_codes: list, *args, **kwargs) -> set:
        scope_config = self.get_scope_config(scope)
        mode = scope_config["mode"]
        config_plugin_codes = scope_config["plugin_codes"]
        if mode == "allow_list":
            return set(plugin_codes) & set(config_plugin_codes)
        else:
            return set(plugin_codes) - set(config_plugin_codes)

    def get_filtered_plugin_qs(self, scope: str, plugin_qs: QuerySet, *args, **kwargs) -> QuerySet:
        scope_config = self.get_scope_config(scope)
        mode = scope_config["mode"]
        config_plugin_codes = scope_config["plugin_codes"]
        if mode == "allow_list":
            return plugin_qs.filter(code__in=config_plugin_codes)
        else:
            return plugin_qs.exclude(code__in=config_plugin_codes)
