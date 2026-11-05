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

from io import StringIO

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

import env
from bkflow.pipeline_plugins.utils import get_node_callback_url

VALID_CALLBACK_KEY = Fernet.generate_key()
ENGINE_TOKEN = "e" * 32
INTERFACE_TOKEN = "i" * 32


@pytest.fixture
def product_engine(monkeypatch):
    """模拟配置齐全的生产 default-engine 模块。"""
    monkeypatch.setattr(env, "BKFLOW_MODULE_TYPE", "engine")
    monkeypatch.setattr(env, "CALLBACK_KEY", VALID_CALLBACK_KEY)
    monkeypatch.setattr(env, "INTERFACE_APP_INTERNAL_TOKEN", INTERFACE_TOKEN)
    with override_settings(RUN_MODE="PRODUCT", APP_INTERNAL_TOKEN=ENGINE_TOKEN):
        yield


@pytest.fixture
def product_interface(monkeypatch):
    """模拟配置齐全、尚未登记默认引擎的生产 interface 模块。"""
    monkeypatch.setattr(env, "BKFLOW_MODULE_TYPE", "interface")
    monkeypatch.setattr(env, "CALLBACK_KEY", VALID_CALLBACK_KEY)
    monkeypatch.setenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", ENGINE_TOKEN)
    with override_settings(
        RUN_MODE="PRODUCT",
        APP_INTERNAL_TOKEN=INTERFACE_TOKEN,
        BKAPP_DEFAULT_ENGINE_MODULE_ENTRY="http://default-engine.example.com",
    ):
        yield


def run_check():
    """执行检查命令并返回标准输出和标准错误。"""
    stdout, stderr = StringIO(), StringIO()
    call_command("check_deploy_secrets", stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


def create_default_engine_module(token=ENGINE_TOKEN):
    """登记存量默认引擎模块。"""
    from bkflow.admin.models import ModuleInfo

    return ModuleInfo.objects.create(
        space_id=0,
        code="default",
        url="http://old-engine.example.com",
        token=token,
        type="TASK",
        isolation_level="all_resource",
    )


def test_develop_mode_skips_check(monkeypatch):
    """本地开发环境不要求注入生产密钥。"""
    monkeypatch.setattr(env, "CALLBACK_KEY", b"")
    with override_settings(RUN_MODE="DEVELOP", APP_INTERNAL_TOKEN=""):
        stdout, _ = run_check()
    assert "skip deploy secret check" in stdout


def test_engine_with_all_secrets_passes(product_engine):
    """引擎模块密钥齐全时可以继续发布。"""
    stdout, _ = run_check()
    assert "deploy secret check passed" in stdout


def test_engine_missing_secrets_fail_without_leaking_values(product_engine, monkeypatch):
    """引擎模块缺少 token 或回调密钥时阻止发布，只输出配置项名称。"""
    monkeypatch.setattr(env, "CALLBACK_KEY", b"not-a-fernet-key")
    monkeypatch.setattr(env, "INTERFACE_APP_INTERNAL_TOKEN", "")
    with override_settings(APP_INTERNAL_TOKEN=""):
        with pytest.raises(CommandError) as error:
            run_check()

    message = str(error.value)
    assert "APP_INTERNAL_TOKEN(未配置)" in message
    assert "BKFLOW_DEFAULT_CALLBACK_KEY" in message
    assert "INTERFACE_APP_INTERNAL_TOKEN(未配置)" in message
    assert "not-a-fernet-key" not in message


def test_engine_token_longer_than_module_info_field_fails(product_engine):
    """引擎 token 要写入模块信息，超过字段长度时提前拦截。"""
    with override_settings(APP_INTERNAL_TOKEN="x" * 33):
        with pytest.raises(CommandError, match="超过32个字符"):
            run_check()


@pytest.mark.django_db
def test_interface_first_deploy_requires_default_engine_token(product_interface, monkeypatch):
    """首次部署尚未登记默认引擎时，必须提供默认引擎 token。"""
    run_check()

    monkeypatch.setenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", "")
    with pytest.raises(CommandError, match="DEFAULT_ENGINE_APP_INTERNAL_TOKEN"):
        run_check()

    monkeypatch.setenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", "x" * 33)
    with pytest.raises(CommandError, match="超过32个字符"):
        run_check()


@pytest.mark.django_db
def test_interface_existing_default_engine_keeps_stored_token(product_interface, monkeypatch):
    """已登记默认引擎时不要求重新注入 token，发布也不改动存量记录。"""
    module_info = create_default_engine_module(token="stored-token")
    monkeypatch.setenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", "")

    stdout, stderr = run_check()

    assert "deploy secret check passed" in stdout
    assert stderr == ""
    module_info.refresh_from_db()
    assert module_info.token == "stored-token"


@pytest.mark.django_db
def test_interface_warns_when_env_token_differs_from_stored(product_interface):
    """环境变量与存量 token 不一致时只提醒手工轮换，不输出任何取值。"""
    create_default_engine_module(token="stored-token")

    stdout, stderr = run_check()

    assert "deploy secret check passed" in stdout
    assert "不会覆盖存量记录" in stderr
    assert "stored-token" not in stderr and ENGINE_TOKEN not in stderr


@pytest.mark.django_db
def test_interface_missing_callback_key_fails(product_interface, monkeypatch):
    """interface 模块需要同一回调密钥解密节点回调地址。"""
    monkeypatch.setattr(env, "CALLBACK_KEY", b"")
    with pytest.raises(CommandError, match="BKFLOW_DEFAULT_CALLBACK_KEY"):
        run_check()


def test_node_callback_url_requires_callback_key(monkeypatch):
    """未配置回调密钥时给出明确错误，配置后可解密还原节点信息。"""
    monkeypatch.setattr(env, "CALLBACK_KEY", b"")
    with pytest.raises(ValueError, match="BKFLOW_DEFAULT_CALLBACK_KEY 未配置"):
        get_node_callback_url(1, 2, "node")

    monkeypatch.setattr(env, "CALLBACK_KEY", VALID_CALLBACK_KEY)
    token = get_node_callback_url(1, 2, "node", "v1").rstrip("/").rsplit("/", 1)[-1]
    assert Fernet(VALID_CALLBACK_KEY).decrypt(token.encode()).decode() == "1:2:node:v1"
