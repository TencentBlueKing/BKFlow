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

import pytest
from pipeline.component_framework.models import ComponentModel

from bkflow.exceptions import ValidationError
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser


class TestSpacePluginConfigParser:
    @pytest.mark.django_db(transaction=True)
    def test_valid_config(self):
        config = {
            "default": {"mode": "allow_list", "plugin_codes": ["plugin1", "plugin2"]},
            "scope1": {"mode": "deny_list", "plugin_codes": ["plugin3"]},
        }
        parser = SpacePluginConfigParser(config)
        assert parser.is_valid() is True
        assert parser.get_scope_config("scope1") == {"mode": "deny_list", "plugin_codes": ["plugin3"]}
        assert parser.get_filtered_plugins("scope1", ["plugin1", "plugin2", "plugin3"]) == {"plugin1", "plugin2"}
        assert set(parser.get_filtered_plugin_qs("scope1", ComponentModel.objects.all())) == set(
            ComponentModel.objects.filter(code__in=["plugin1", "plugin2"])
        )

    def test_filtered_plugins_allow_list(self):
        config = {
            "default": {"mode": "allow_list", "plugin_codes": ["plugin1", "plugin2"]},
            "scope1": {"mode": "deny_list", "plugin_codes": ["plugin3"]},
        }
        parser = SpacePluginConfigParser(config)
        assert parser.get_filtered_plugins("default", ["plugin1", "plugin2", "plugin3"]) == {"plugin1", "plugin2"}

    def test_invalid_config(self):
        config = {
            "default": {"mode": "allow_list", "plugins": ["plugin1", "plugin2"]},
            "scope1": {"mode": "deny_list", "plugins": ["plugin3"]},
        }
        with pytest.raises(ValidationError):
            SpacePluginConfigParser(config)

    def test_validate_true(self):
        config = {
            "default": {"mode": "allow_list", "plugins": ["plugin1", "plugin2"]},
            "scope1": {"mode": "deny_list", "plugins": ["plugin3"]},
        }
        with pytest.raises(ValidationError):
            SpacePluginConfigParser(config)

    def test_missing_required_fields(self):
        config = {"default": {"mode": "allow_list"}, "scope1": {"mode": "deny_list", "plugin_codes": ["plugin3"]}}
        with pytest.raises(ValidationError):
            SpacePluginConfigParser(config)
