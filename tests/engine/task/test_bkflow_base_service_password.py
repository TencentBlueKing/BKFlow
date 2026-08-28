# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import copy
import json

import pytest
from pipeline.core.data.base import DataObject

from bkflow.constants import MASK_META_SYSTEM_MASK_INFO_KEY
from bkflow.pipeline_plugins.components.collections.base import (
    BKFlowBaseService,
    PASSWORD_MASK_VALUE,
    PASSWORD_VALUE_TYPE,
    PasswordDecryptFailed,
)
from bkflow.utils import crypto

PLAINTEXT_SECRET = "plaintext_secret"
CIPHER = "rsa_str:::ENC"
PASSWORD_STRUCT = {"type": PASSWORD_VALUE_TYPE, "value": CIPHER}


def _fake_decrypt(cipher):
    """模拟密钥可用时，crypto.decrypt 返回明文"""
    return PLAINTEXT_SECRET


def _fail_decrypt(cipher):
    """模拟未配置密钥/密钥变更时，crypto.decrypt 抛异常（AsymmetricCipherSelector 返回 None 的场景）"""
    raise ValueError("No asymmetric cipher available")


class _PasswordService(BKFlowBaseService):
    """用于集成测试的子类，覆盖依赖外部 runtime 的 _get_raw_password_map，避免真实访问引擎"""

    plugin_name = "test_password_plugin"
    enable_plugin_span = False

    def _get_raw_password_map(self):
        return getattr(self, "_raw_map_result", (True, {}))

    def plugin_execute(self, data, parent_data):
        # 记录插件执行时看到的 inputs（此时密码已解密为明文）
        self.execute_inputs = copy.deepcopy(dict(data.inputs))
        self.execute_parent_inputs = copy.deepcopy(dict(parent_data.inputs))
        # 模拟插件执行过程中对 inputs 新增字段，用于验证掩码流程不会丢失插件新增字段
        data.inputs["plugin_added"] = "added_value"
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        # 记录轮询时看到的 inputs，用于验证 schedule 阶段恢复了明文密码
        self.schedule_inputs = copy.deepcopy(dict(data.inputs))
        self.finish_schedule()
        return True


@pytest.mark.django_db(transaction=True)
class TestBKFlowBaseServicePassword:
    # ---------------------- 单元：_auto_decrypt_password_inputs ----------------------

    def test_auto_decrypt_password_inputs_decrypts_top_level_password_struct(self, monkeypatch):
        """顶层 value 为密码结构体时，应被解密为明文"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})

        service._auto_decrypt_password_inputs(data)

        assert data.inputs["password"] == PLAINTEXT_SECRET

    def test_auto_decrypt_password_inputs_masks_top_level_password_struct(self, monkeypatch):
        """mask_flag=True 时，顶层密码结构体应被替换为掩码值而非明文"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})

        service._auto_decrypt_password_inputs(data, mask_flag=True)

        assert data.inputs["password"] == PASSWORD_MASK_VALUE

    def test_auto_decrypt_password_inputs_decrypts_nested_password_in_dict(self, monkeypatch):
        """嵌套在 dict 中的密码结构体应被递归解密"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"config": {"nested_pwd": copy.deepcopy(PASSWORD_STRUCT)}})

        service._auto_decrypt_password_inputs(data)

        assert data.inputs["config"]["nested_pwd"] == PLAINTEXT_SECRET

    def test_auto_decrypt_password_inputs_decrypts_nested_password_in_list(self, monkeypatch):
        """嵌套在 list 中的密码结构体应被递归解密"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"items": [copy.deepcopy(PASSWORD_STRUCT)]})

        service._auto_decrypt_password_inputs(data)

        assert data.inputs["items"][0] == PLAINTEXT_SECRET

    def test_auto_decrypt_password_inputs_replaces_string_password_variable(self, monkeypatch):
        """字符串中引用的密码变量应被替换为明文"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        input_password_refs = {"customerPassword": copy.deepcopy(PASSWORD_STRUCT)}
        str_password = json.dumps(input_password_refs["customerPassword"]).replace('"', "'")
        data = DataObject(inputs={"cmd": "prefix{}suffix".format(str_password)})

        service._auto_decrypt_password_inputs(data, input_password_refs=input_password_refs)

        assert data.inputs["cmd"] == "prefix{}suffix".format(PLAINTEXT_SECRET)

    def test_auto_decrypt_password_inputs_masks_string_password_variable(self, monkeypatch):
        """字符串型密码变量在 mask_flag=True 时应被替换为掩码值"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        input_password_refs = {"customerPassword": copy.deepcopy(PASSWORD_STRUCT)}
        str_password = json.dumps(input_password_refs["customerPassword"]).replace('"', "'")
        data = DataObject(inputs={"cmd": "prefix{}suffix".format(str_password)})

        service._auto_decrypt_password_inputs(data, input_password_refs=input_password_refs, mask_flag=True)

        assert data.inputs["cmd"] == "prefix{}suffix".format(PASSWORD_MASK_VALUE)

    def test_auto_decrypt_password_inputs_skips_string_without_refs(self, monkeypatch):
        """未提供 input_password_refs 时，字符串分支直接跳过，不应触发解密"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"cmd": "prefix{'type': 'password_value', 'value': 'x'}suffix"})

        service._auto_decrypt_password_inputs(data)

        assert data.inputs["cmd"] == "prefix{'type': 'password_value', 'value': 'x'}suffix"

    def test_auto_decrypt_password_inputs_empty_cipher_no_raise(self, monkeypatch):
        """密码结构体中 value 为空时，get_decrypt_value 直接返回 None，不应抛异常"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"password": {"type": PASSWORD_VALUE_TYPE, "value": ""}})

        service._auto_decrypt_password_inputs(data)

        assert data.inputs["password"] is None

    def test_decrypt_failure_raises_password_decrypt_failed(self, monkeypatch):
        """解密抛异常时应转换为 PasswordDecryptFailed，且错误信息仅携带来源不携带密文"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = BKFlowBaseService()
        setattr(service, "id", "node1")
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})

        with pytest.raises(PasswordDecryptFailed):
            service._auto_decrypt_password_inputs(data)

    # ---------------------- 单元：_sync_new_fields / _deep_update ----------------------

    def test_sync_new_fields_only_adds_new_keys(self):
        """_sync_new_fields 只同步 target 中不存在的字段，不覆盖已有字段"""
        service = BKFlowBaseService()
        target = {"a": 1, "b": {"x": 1}}
        source = {"a": 999, "b": {"x": 1, "y": 2}, "c": 3}

        service._sync_new_fields(target, source)

        assert target["a"] == 1
        assert target["b"]["x"] == 1
        assert target["b"]["y"] == 2
        assert target["c"] == 3

    def test_sync_new_fields_recursive_for_nested_dict(self):
        """_sync_new_fields 对嵌套 dict 应递归同步新增子字段"""
        service = BKFlowBaseService()
        target = {"b": {"x": 1}}
        source = {"b": {"x": 1, "y": 2}}

        service._sync_new_fields(target, source)

        assert target["b"]["y"] == 2

    def test_deep_update_recursive(self):
        """_deep_update 对嵌套 dict 应递归更新，非容器值直接替换"""
        service = BKFlowBaseService()
        target = {"a": {"b": 1}, "c": 2}
        source = {"a": {"b": 10, "d": 20}, "c": 30}

        service._deep_update(target, source)

        assert target["a"]["b"] == 10
        assert target["a"]["d"] == 20
        assert target["c"] == 30

    def test_deep_update_list(self):
        """_deep_update 对 list 应按索引递归更新元素"""
        service = BKFlowBaseService()
        target = [{"a": 1}, {"b": 2}]
        source = [{"a": 10}, {"b": 20}]

        service._deep_update(target, source)

        assert target[0]["a"] == 10
        assert target[1]["b"] == 20

    # ---------------------- 集成：execute / schedule 全流程 ----------------------

    def test_execute_decrypts_and_masks_inputs(self, monkeypatch):
        """execute 后，inputs 中的密码应被掩码，避免明文落库"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is True
        assert data.inputs["password"] == PASSWORD_MASK_VALUE
        assert data.inputs["plugin_added"] == "added_value"

    def test_execute_stores_original_inputs_in_mask_output(self, monkeypatch):
        """execute 应将掩码前的原始 inputs（此处为密文结构体）暂存到 outputs 私有 key，供 schedule 恢复"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        service.execute(data=data, parent_data=parent_data)

        mask_info = data.get_one_of_outputs(MASK_META_SYSTEM_MASK_INFO_KEY)
        assert mask_info is not None
        # 暂存的是掩码前的原始值（密文结构体），避免明文落库
        assert mask_info["decrypt_input_data"]["password"] == PASSWORD_STRUCT
        # 插件执行时看到的是解密后的明文
        assert service.execute_inputs["password"] == PLAINTEXT_SECRET

    def test_execute_get_raw_password_map_failure_returns_false(self):
        """_get_raw_password_map 失败时 execute 应直接返回 False 并写入 ex_data"""
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (False, "get_raw_password_map failed")
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is False
        assert data.get_one_of_outputs("ex_data") == "get_raw_password_map failed"

    def test_execute_decrypt_failure_returns_false(self, monkeypatch):
        """解密失败（如未配置密钥）时 execute 应返回 False，且错误信息不泄露密文"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is False
        ex_data = data.get_one_of_outputs("ex_data")
        assert ex_data is not None
        assert "密码变量解密失败" in ex_data
        assert CIPHER not in ex_data

    def test_execute_then_schedule_restores_plaintext(self, monkeypatch):
        """execute 掩码后，schedule 应基于私有 key 恢复原始输入并重新解密出明文"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        setattr(service, "__need_schedule__", True)
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        service.execute(data=data, parent_data=parent_data)
        assert data.inputs["password"] == PASSWORD_MASK_VALUE

        result = service.schedule(data=data, parent_data=parent_data)

        assert result is True
        # schedule 轮询时插件可见的是恢复并解密后的明文
        assert service.schedule_inputs["password"] == PLAINTEXT_SECRET
        # schedule 返回后 inputs 会再次被掩码，避免明文落库
        assert data.inputs["password"] == PASSWORD_MASK_VALUE

    def test_execute_passthrough_password_keeps_cipher_in_mask_output(self, monkeypatch):
        """透传型（subprocess_plugin）不解密，掩码副本应保留原始密文结构体"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service.plugin_name = "subprocess_plugin"
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is True
        mask_info = data.get_one_of_outputs(MASK_META_SYSTEM_MASK_INFO_KEY)
        assert mask_info["decrypt_input_data"]["password"] == PASSWORD_STRUCT

    def test_execute_string_password_variable_in_inputs(self, monkeypatch):
        """execute 中字符串引用的密码变量应被替换为明文，掩码副本保留隐私"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        input_password_refs = {"customerPassword": copy.deepcopy(PASSWORD_STRUCT)}
        str_password = json.dumps(input_password_refs["customerPassword"]).replace('"', "'")
        service._raw_map_result = (True, input_password_refs)
        data = DataObject(inputs={"cmd": "prefix{}suffix".format(str_password)})
        parent_data = DataObject(inputs={})

        service.execute(data=data, parent_data=parent_data)

        # 插件执行时字符串中引用的密码变量已被替换为明文
        assert service.execute_inputs["cmd"] == "prefix{}suffix".format(PLAINTEXT_SECRET)
        # 落库的 inputs 被替换为掩码，暂存的原始值仍是未替换的字符串，均不含明文
        assert data.inputs["cmd"] == "prefix{}suffix".format(PASSWORD_MASK_VALUE)
        mask_info = data.get_one_of_outputs(MASK_META_SYSTEM_MASK_INFO_KEY)
        assert mask_info["decrypt_input_data"]["cmd"] == "prefix{}suffix".format(str_password)

    def test_execute_does_not_touch_parent_data_password(self, monkeypatch):
        """parent_data 不承载密码变量，不应被本服务解密/掩码；data 中的密码变量仍正常处理。

        parent_data 实质是根流程的 data inputs（仅含任务元数据），密码变量位于流程上下文、
        渲染进节点 data.inputs。因此上层无需对 parent_data 做解密与掩码暂存。
        """
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        # 预检只看 data.inputs，因此需要 data 中也有密码变量才会触发密码处理分支
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        # parent_data 传入密码结构体，用于验证其不会被本服务解密/掩码
        parent_data = DataObject(inputs={"parent_password": copy.deepcopy(PASSWORD_STRUCT)})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is True
        # data 中的密码照常解密为明文供插件使用
        assert service.execute_inputs["password"] == PLAINTEXT_SECRET
        # 落库的 data inputs 被掩码
        assert data.inputs["password"] == PASSWORD_MASK_VALUE
        # parent_data 不解密、不掩码、不挂私有 key
        assert parent_data.inputs["parent_password"] == PASSWORD_STRUCT
        assert parent_data.inputs.get("_mask_meta_system_parent_mask_info") is None

    def test_execute_without_password_inputs_skips_mask(self, monkeypatch):
        """inputs 中无密码变量时，不进入密码处理分支，不写入掩码私有 key"""
        monkeypatch.setattr(crypto, "decrypt", _fail_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"normal": "value"})
        parent_data = DataObject(inputs={})

        result = service.execute(data=data, parent_data=parent_data)

        assert result is True
        assert data.get_one_of_outputs(MASK_META_SYSTEM_MASK_INFO_KEY) is None

    def test_execute_preserves_plugin_added_fields_after_mask(self, monkeypatch):
        """掩码流程不应丢失插件对 inputs 新增的字段"""
        monkeypatch.setattr(crypto, "decrypt", _fake_decrypt)
        service = _PasswordService()
        setattr(service, "id", "node1")
        service._raw_map_result = (True, {})
        data = DataObject(inputs={"password": copy.deepcopy(PASSWORD_STRUCT)})
        parent_data = DataObject(inputs={})

        service.execute(data=data, parent_data=parent_data)

        assert data.inputs["plugin_added"] == "added_value"
