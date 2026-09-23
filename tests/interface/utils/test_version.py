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
import semver

from bkflow.utils.version import bump_custom


class TestBumpCustom:
    """bump_custom 函数单元测试"""

    def test_normal_patch_increment(self):
        """测试正常 patch 版本递增"""
        assert bump_custom("1.0.0") == "1.0.1"
        assert bump_custom("2.3.5") == "2.3.6"
        assert bump_custom("0.1.8") == "0.1.9"

    def test_patch_9_minor_increment(self):
        """测试 patch=9 时 minor 版本递增"""
        assert bump_custom("1.0.9") == "1.1.0"
        assert bump_custom("3.5.9") == "3.6.0"
        assert bump_custom("0.8.9") == "0.9.0"

    def test_minor_9_patch_9_major_increment(self):
        """测试 minor=9, patch=9 时 major 版本递增"""
        assert bump_custom("1.9.9") == "2.0.0"
        assert bump_custom("5.9.9") == "6.0.0"

    def test_with_old_version_validation(self):
        """测试带老版本号的验证功能"""
        # 新版本大于老版本，正常通过
        assert bump_custom("1.0.1", "1.0.0") == "1.0.2"
        assert bump_custom("1.1.0", "1.0.9") == "1.1.1"

    def test_with_old_version_validation_error(self):
        """测试新版本小于等于老版本时的异常"""
        with pytest.raises(ValueError, match="new version 1.0.0 is less than old version 1.0.1"):
            bump_custom("1.0.0", "1.0.1")
        with pytest.raises(ValueError, match="new version 1.0.0 is less than old version 1.0.2"):
            bump_custom("1.0.0", "1.0.2")
        with pytest.raises(ValueError, match="new version 1.0.9 is less than old version 1.1.0"):
            bump_custom("1.0.9", "1.1.0")
        with pytest.raises(ValueError, match="new version 1.9.9 is less than old version 2.0.0"):
            bump_custom("1.9.9", "2.0.0")

    def test_edge_cases(self):
        """测试边界情况"""
        assert bump_custom("9.9.9") == "10.0.0"
        assert bump_custom("0.0.0") == "0.0.1"
        assert bump_custom("0.0.9") == "0.1.0"
        assert bump_custom("0.9.9") == "1.0.0"

    def test_invalid_version_format(self):
        """测试无效版本格式"""
        with pytest.raises(ValueError):
            bump_custom("invalid")
        with pytest.raises(ValueError):
            bump_custom("1.0")

    def test_old_version_invalid_format(self):
        """测试老版本号格式无效"""
        with pytest.raises(ValueError):
            bump_custom("1.0.0", "invalid")

    def test_complex_scenarios(self):
        """测试复杂场景"""
        versions = ["1.0.0", "1.0.1", "1.0.2", "1.0.3", "1.0.4", "1.0.5", "1.0.6", "1.0.7", "1.0.8", "1.0.9", "1.1.0"]

        current = "1.0.0"
        for expected in versions[1:]:
            current = bump_custom(current)
            assert current == expected

    def test_semantic_version_parsing(self):
        """测试语义版本号解析正确性"""
        result = bump_custom("1.2.3")
        parsed = semver.VersionInfo.parse(result)
        assert isinstance(parsed, semver.VersionInfo)
        assert str(parsed) == result
