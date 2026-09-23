"""Engine 通过父任务空间读取子流程，且保留单租户旧请求。"""

from unittest.mock import patch

import pytest
from django.test import override_settings
from pipeline.core.data.base import DataObject

from bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0 import (
    SubprocessPluginService,
)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("latest", [False, True])
def test_subprocess_query_uses_parent_space_only_in_multi(enabled, latest):
    """旧版本/最新版本都保持单租户协议，多租户增加可信父任务空间。"""
    data = DataObject(
        inputs={
            "subprocess": {
                "template_id": 22,
                "subprocess_name": "child",
                "version": "a" * 32,
                "constants": {},
                "always_use_latest": latest,
            }
        }
    )
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch(
        "bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0.InterfaceModuleClient"
    ) as client:
        client.return_value.get_template_data.return_value = {"result": True, "data": {}}
        template, _ = SubprocessPluginService()._get_subprocess_template(data, space_id=11)
    query = {"version": None if latest else "a" * 32}
    if enabled:
        query["space_id"] = 11
    client.return_value.get_template_data.assert_called_once_with(template_id="22", data=query)
    assert template["result"] is True


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_missing_parent_space_rejected_before_request():
    """缺少父任务空间时不能按内部凭证查询任意模板。"""
    data = DataObject(
        inputs={"subprocess": {"template_id": 22, "subprocess_name": "child", "version": "a" * 32, "constants": {}}}
    )
    with patch(
        "bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0.InterfaceModuleClient"
    ) as client:
        assert SubprocessPluginService()._get_subprocess_template(data) == (None, None)
    client.return_value.get_template_data.assert_not_called()
    assert "空间" in data.get_one_of_outputs("ex_data")
