# BK-Vision 运营统计仪表盘对接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集成 django-bkvision SDK 到 BKFlow，通过 context_processor 下发仪表盘配置给前端，为后续 iframe 嵌入 BK-Vision 仪表盘做好后端准备。

**Architecture:** 安装 django-bkvision SDK 处理 BK-Vision 的认证和 API 代理；通过环境变量管理仪表盘 UID 和网关地址；通过现有的 context_processor 机制将配置注入前端模板上下文。

**Tech Stack:** Django 3.2+, django-bkvision SDK, BK-Vision 平台

**Spec 文档:** `docs/specs/2026-03-31-bkvision-statistics-dashboard-design.md`

---

### Task 1: 安装 django-bkvision 依赖

**Files:**
- Modify: `requirements.txt:82` (末尾追加)

- [ ] **Step 1: 添加 django-bkvision 到 requirements.txt**

在 `requirements.txt` 末尾追加：

```
# BK-Vision 仪表盘嵌入 SDK
django-bkvision>=0.1.0
```

> 注：部署前确认 PyPI 上最新版本，按需锁定。

- [ ] **Step 2: 安装依赖验证**

Run: `pip install django-bkvision`
Expected: 安装成功，无冲突

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: 添加 django-bkvision SDK 依赖 --story=<TAPD_ID>"
```

---

### Task 2: 添加 BK-Vision 环境变量

**Files:**
- Modify: `env.py:203` (末尾追加)

- [ ] **Step 1: 在 env.py 末尾追加 BK-Vision 配置变量**

在 `env.py` 文件末尾（第 203 行后）追加：

```python
# BK-Vision 仪表盘对接配置
BKAPP_BKVISION_APIGW_URL = os.getenv("BKAPP_BKVISION_APIGW_URL", "")
BKAPP_BKVISION_BASE_URL = os.getenv("BKAPP_BKVISION_BASE_URL", "")
BKAPP_BKVISION_SYSTEM_DASHBOARD_UID = os.getenv("BKAPP_BKVISION_SYSTEM_DASHBOARD_UID", "")
BKAPP_BKVISION_SPACE_DASHBOARD_UID = os.getenv("BKAPP_BKVISION_SPACE_DASHBOARD_UID", "")
```

- [ ] **Step 2: 验证 env 模块可正常导入**

Run: `cd /root/Projects/bk-flow && python -c "import env; print(env.BKAPP_BKVISION_APIGW_URL)"`
Expected: 输出空字符串 `""`，无 ImportError

- [ ] **Step 3: Commit**

```bash
git add env.py
git commit -m "feat(statistics): 添加 BK-Vision 仪表盘对接环境变量 --story=<TAPD_ID>"
```

---

### Task 3: Django 配置 — INSTALLED_APPS 和 URL 路由

**Files:**
- Modify: `config/default.py:409` (在 `corsheaders` 之后追加)
- Modify: `bkflow/urls.py:31-47` (interface 模块的 urlpatterns 中追加)

- [ ] **Step 1: 在 config/default.py 中将 django_bkvision 添加到 INSTALLED_APPS**

在 `config/default.py` 中 `INSTALLED_APPS += ("corsheaders",)` 行之后追加：

```python
# BK-Vision 仪表盘嵌入 SDK
INSTALLED_APPS += ("django_bkvision",)
```

- [ ] **Step 2: 在 bkflow/urls.py 的 interface 模块路由中添加 bkvision URL**

在 `bkflow/urls.py` 的 `if settings.BKFLOW_MODULE.type == BKFLOWModuleType.interface:` 分支的 `urlpatterns` 列表中，在 `url(r"^api/statistics/", ...)` 行之后追加：

```python
        url(r"^bkvision/", include("django_bkvision.urls")),
```

即 urlpatterns 变为：

```python
if settings.BKFLOW_MODULE.type == BKFLOWModuleType.interface:
    urlpatterns += [
        url(r"^", include("bkflow.interface.urls")),
        url(r"^api/template/", include("bkflow.template.urls")),
        url(r"^api/decision_table/", include("bkflow.decision_table.urls")),
        url(r"^api/space/", include("bkflow.space.urls")),
        url(r"^api/plugin/", include("bkflow.plugin.urls")),
        url(r"^api/bk_plugin/", include("bkflow.bk_plugin.urls")),
        url(r"^api/admin/", include("bkflow.admin.urls")),
        url(r"^api/permission/", include("bkflow.permission.urls")),
        url(r"^api/plugin_query/", include("bkflow.pipeline_plugins.query.urls")),
        url(r"^api/plugin_service/", include("plugin_service.urls")),
        url(r"^api/api_plugin_demo/", include("bkflow.api_plugin_demo.urls")),
        url(r"^api/statistics/", include("bkflow.statistics.urls")),
        url(r"^bkvision/", include("django_bkvision.urls")),
        url(r"^notice/", include("bk_notice_sdk.urls")),
        url(r"^version_log/", include("version_log.urls", namespace="version_log")),
    ]
```

> 注：此处保持与项目已有的 `url()` 风格一致。项目 urls.py 全文都使用 `django.conf.urls.url`，保持统一。

- [ ] **Step 3: Commit**

```bash
git add config/default.py bkflow/urls.py
git commit -m "feat(statistics): 配置 django-bkvision INSTALLED_APPS 和 URL 路由 --story=<TAPD_ID>"
```

---

### Task 4: Context Processor 注入 BK-Vision 配置

**Files:**
- Modify: `bkflow/interface/context_processors.py:33-51` (ctx dict 中追加字段)

- [ ] **Step 1: 在 bkflow_settings 函数的 ctx 字典中追加 BK-Vision 配置**

在 `bkflow/interface/context_processors.py` 的 `ctx` 字典中，在 `"BK_PAAS_ESB_HOST"` 行之后追加三个字段：

```python
    ctx = {
        # ... 现有字段保持不变 ...
        "BK_PAAS_ESB_HOST": env.BK_PAAS_ESB_HOST,
        # BK-Vision 仪表盘配置
        "BKVISION_SYSTEM_DASHBOARD_UID": env.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID,
        "BKVISION_SPACE_DASHBOARD_UID": env.BKAPP_BKVISION_SPACE_DASHBOARD_UID,
        "BKVISION_BASE_URL": env.BKAPP_BKVISION_BASE_URL,
    }
```

- [ ] **Step 2: Commit**

```bash
git add bkflow/interface/context_processors.py
git commit -m "feat(statistics): context_processor 注入 BK-Vision 仪表盘配置 --story=<TAPD_ID>"
```

---

### Task 5: 编写单元测试

**Files:**
- Create: `tests/interface/statistics/test_bkvision_config.py`

> 注：项目 `pytest.ini` 配置 `testpaths = tests`，统计模块测试位于 `tests/interface/statistics/`。

- [ ] **Step 1: 编写测试 — 验证环境变量和 context processor**

创建 `tests/interface/statistics/test_bkvision_config.py`：

```python
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

import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestBKVisionEnvConfig:
    """BK-Vision 环境变量配置测试"""

    @patch.dict("os.environ", {}, clear=False)
    def test_bkvision_env_defaults_are_empty(self):
        """未设置环境变量时，BK-Vision 配置应为空字符串"""
        import env

        for key in [
            "BKAPP_BKVISION_APIGW_URL",
            "BKAPP_BKVISION_BASE_URL",
            "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID",
            "BKAPP_BKVISION_SPACE_DASHBOARD_UID",
        ]:
            assert hasattr(env, key), f"env.{key} should be defined"
            assert isinstance(getattr(env, key), str), f"env.{key} should be a string"

    @patch.dict(
        "os.environ",
        {
            "BKAPP_BKVISION_APIGW_URL": "https://gw.example.com",
            "BKAPP_BKVISION_BASE_URL": "https://bkvision.example.com",
            "BKAPP_BKVISION_SYSTEM_DASHBOARD_UID": "sys-uid-123",
            "BKAPP_BKVISION_SPACE_DASHBOARD_UID": "space-uid-456",
        },
    )
    def test_bkvision_env_reads_from_environ(self):
        """设置环境变量后，env 模块应读取到对应值"""
        import env

        env_module = importlib.reload(env)
        assert env_module.BKAPP_BKVISION_APIGW_URL == "https://gw.example.com"
        assert env_module.BKAPP_BKVISION_BASE_URL == "https://bkvision.example.com"
        assert env_module.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID == "sys-uid-123"
        assert env_module.BKAPP_BKVISION_SPACE_DASHBOARD_UID == "space-uid-456"


class TestBKVisionContextProcessor:
    """BK-Vision context processor 配置注入测试"""

    @patch("bkflow.interface.context_processors.EnvironmentVariables")
    @patch("bkflow.interface.context_processors.settings")
    def test_bkvision_keys_in_context(self, mock_settings, mock_env_vars):
        """bkflow_settings 返回的上下文应包含 BK-Vision 配置键"""
        mock_settings.STATIC_URL = "/static/"
        mock_settings.RUN_VER = "open"
        mock_settings.MAX_NODE_EXECUTE_TIMEOUT = 3600
        mock_settings.MEMBER_SELECTOR_DATA_HOST = ""
        mock_settings.APP_CODE = "bkflow"
        mock_settings.APP_NAME = "BKFlow"
        mock_settings.RUN_VER_NAME = "BKFlow"
        mock_env_vars.objects.get_var = MagicMock(return_value=0)

        request = MagicMock()
        request.user.username = "admin"
        request.COOKIES = {"blueking_language": "zh-cn"}

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(request)

        assert "BKVISION_SYSTEM_DASHBOARD_UID" in ctx
        assert "BKVISION_SPACE_DASHBOARD_UID" in ctx
        assert "BKVISION_BASE_URL" in ctx

    @patch("bkflow.interface.context_processors.env")
    @patch("bkflow.interface.context_processors.EnvironmentVariables")
    @patch("bkflow.interface.context_processors.settings")
    def test_bkvision_values_from_env(self, mock_settings, mock_env_vars, mock_env):
        """BK-Vision 配置值应来自 env 模块"""
        mock_settings.STATIC_URL = "/static/"
        mock_settings.RUN_VER = "open"
        mock_settings.MAX_NODE_EXECUTE_TIMEOUT = 3600
        mock_settings.MEMBER_SELECTOR_DATA_HOST = ""
        mock_settings.APP_CODE = "bkflow"
        mock_settings.APP_NAME = "BKFlow"
        mock_settings.RUN_VER_NAME = "BKFlow"
        mock_env_vars.objects.get_var = MagicMock(return_value=0)

        mock_env.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID = "test-system-uid"
        mock_env.BKAPP_BKVISION_SPACE_DASHBOARD_UID = "test-space-uid"
        mock_env.BKAPP_BKVISION_BASE_URL = "https://bkvision.example.com"
        mock_env.BK_DOC_CENTER_HOST = "https://docs.example.com"
        mock_env.BKPAAS_SHARED_RES_URL = ""
        mock_env.BKFLOW_LOGIN_URL = ""
        mock_env.MESSAGE_HELPER_URL = ""
        mock_env.BKPAAS_BK_DOMAIN = ""
        mock_env.BK_PAAS_ESB_HOST = ""

        request = MagicMock()
        request.user.username = "admin"
        request.COOKIES = {"blueking_language": "zh-cn"}

        from bkflow.interface.context_processors import bkflow_settings

        ctx = bkflow_settings(request)

        assert ctx["BKVISION_SYSTEM_DASHBOARD_UID"] == "test-system-uid"
        assert ctx["BKVISION_SPACE_DASHBOARD_UID"] == "test-space-uid"
        assert ctx["BKVISION_BASE_URL"] == "https://bkvision.example.com"
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/interface/statistics/test_bkvision_config.py -v`
Expected: 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/interface/statistics/test_bkvision_config.py
git commit -m "test(statistics): 添加 BK-Vision 配置集成测试 --story=<TAPD_ID>"
```

---

### Task 6: 最终验证

- [ ] **Step 1: 运行统计相关测试确认无破坏**

Run: `pytest tests/interface/statistics/ -v`
Expected: 全部 PASS，无新增 FAIL

- [ ] **Step 2: 检查 lint**

Run: `cd /root/Projects/bk-flow && flake8 env.py bkflow/interface/context_processors.py bkflow/urls.py config/default.py tests/interface/statistics/test_bkvision_config.py --max-line-length=120`
Expected: 无新增 lint 错误

---

## 后续手动步骤（不在代码实现范围内）

以下步骤需要在 BK-Vision 平台和蓝鲸 API 网关上手动操作，参考 spec 文档 `docs/specs/2026-03-31-bkvision-statistics-dashboard-design.md` 第 8 节：

1. 在蓝鲸 API 网关申请 `bk-vision` 接口权限
2. 在 BK-Vision 平台创建 `BKFlow` 工作空间
3. 配置 MySQL 数据源（连接统计数据库）
4. 按 spec 第 7.3 节创建系统仪表盘（16 panels）
5. 按 spec 第 7.4 节创建空间仪表盘（10 panels）
6. 创建并发布两个仪表盘的分享链接
7. 将分享链接 UID 配置到环境变量 `BKAPP_BKVISION_SYSTEM_DASHBOARD_UID` 和 `BKAPP_BKVISION_SPACE_DASHBOARD_UID`
8. 配置 `BKAPP_BKVISION_APIGW_URL` 和 `BKAPP_BKVISION_BASE_URL`
9. 部署验证

## 前端对接需求文档

spec 文档 `docs/specs/2026-03-31-bkvision-statistics-dashboard-design.md` 第 6 节即为前端对接需求文档，包含页面路由、iframe URL 拼装、权限控制和 i18n 要求。无需额外输出独立文档。

由前端开发单独实现，参考 spec 第 6 节：

1. 系统管理侧边栏新增"运营统计"菜单，路由 `/bkflow_engine_admin/statistics/`
2. 空间侧边栏新增"运营统计"菜单
3. 两个页面分别用 iframe 嵌入 BK-Vision 仪表盘
4. 从 `window.BKVISION_*` 全局变量获取配置
5. i18n 翻译
