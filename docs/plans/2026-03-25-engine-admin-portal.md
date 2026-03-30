# Engine Admin Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable BKFlow admins to access Engine module Django Admin pages, with a convenient portal on Interface's Admin homepage.

**Architecture:** Migrate `sync_superuser` command to a shared app so Engine can create admin users. Override Interface's Admin index template to show Engine module cards with jump links. Use a custom template tag to inject Engine module data — avoids replacing the global `admin.site` and modifying all existing `@admin.register` calls.

**Tech Stack:** Django Admin, Django template tags, Python management commands

**Spec:** `docs/specs/2026-03-25-engine-admin-portal-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `bkflow/contrib/operation_record/management/__init__.py` | Create | Django management package init |
| `bkflow/contrib/operation_record/management/commands/__init__.py` | Create | Django commands package init |
| `bkflow/contrib/operation_record/management/commands/sync_superuser.py` | Create | Migrated sync_superuser command |
| `bkflow/interface/management/commands/sync_superuser.py` | Delete | Old location (replaced by above) |
| `bin/pre_release.sh` | Modify | Move sync_superuser before module-specific if block |
| `bkflow/admin/templatetags/__init__.py` | Create | Template tags package init |
| `bkflow/admin/templatetags/engine_admin_tags.py` | Create | Template tag to provide engine modules to template |
| `bkflow/admin/templates/admin/bkflow_index.html` | Create | Custom Admin index page with Engine module cards |
| `bkflow/admin/apps.py` | Modify | Set `admin.site.index_template` in `ready()` |
| `bkflow/admin/admin.py` | Modify | Add `admin_link` column to `ModuleInfoAdmin` |
| `app_desc.yaml` | Modify | Declare `BKFLOW_INIT_SUPERUSERS` env var for Engine module |
| `tests/interface/admin/test_engine_admin_portal.py` | Create | Tests for template tag, admin index, and admin_link |

---

### Task 1: Migrate `sync_superuser` to shared app

**Files:**
- Create: `bkflow/contrib/operation_record/management/__init__.py`
- Create: `bkflow/contrib/operation_record/management/commands/__init__.py`
- Create: `bkflow/contrib/operation_record/management/commands/sync_superuser.py`
- Delete: `bkflow/interface/management/commands/sync_superuser.py`

- [ ] **Step 1: Create management/commands directory structure**

```bash
mkdir -p bkflow/contrib/operation_record/management/commands
touch bkflow/contrib/operation_record/management/__init__.py
touch bkflow/contrib/operation_record/management/commands/__init__.py
```

- [ ] **Step 2: Copy sync_superuser.py to new location**

Copy `bkflow/interface/management/commands/sync_superuser.py` to `bkflow/contrib/operation_record/management/commands/sync_superuser.py`. The file content stays identical:

```python
import os

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = apps.get_model("account", "User")
        INIT_SUPERUSERS = os.getenv("BKFLOW_INIT_SUPERUSERS", "")
        if not INIT_SUPERUSERS:
            return

        for username in INIT_SUPERUSERS.split(","):
            User.objects.update_or_create(
                username=username, defaults={"is_staff": True, "is_active": True, "is_superuser": True}
            )
```

- [ ] **Step 3: Delete the old file**

Delete `bkflow/interface/management/commands/sync_superuser.py`.

- [ ] **Step 4: Verify command is discoverable**

Run: `BKFLOW_MODULE_TYPE=interface python manage.py help sync_superuser`
Expected: Shows help text (no "Unknown command" error).

Run: `BKFLOW_MODULE_TYPE=engine BKFLOW_MODULE_CODE=default python manage.py help sync_superuser`
Expected: Shows help text (no "Unknown command" error).

- [ ] **Step 5: Search for stale references to old path**

Run: `rg "bkflow/interface/management/commands/sync_superuser"`
Expected: No matches (old path should not be referenced anywhere).

Run: `ls bkflow/interface/management/commands/sync_superuser.py 2>&1`
Expected: "No such file or directory" (file is deleted).

- [ ] **Step 6: Commit**

```bash
git add bkflow/contrib/operation_record/management/ bkflow/interface/management/commands/sync_superuser.py
git commit -m "refactor(admin): 迁移 sync_superuser 命令到共享应用 --story=<tapdId>"
```

---

### Task 2: Modify `pre_release.sh`

**Files:**
- Modify: `bin/pre_release.sh`

- [ ] **Step 1: Move sync_superuser before the if block**

Edit `bin/pre_release.sh` to the following:

```bash
#!/bin/bash
python manage.py migrate
python manage.py createcachetable django_cache
python manage.py update_component_models
python manage.py update_variable_models
python manage.py sync_superuser
if [ "$BKPAAS_APP_MODULE_NAME" == "default" ]; then
  python manage.py sync_saas_apigw
  python manage.py sync_default_module
  python manage.py register_bkflow_to_bknotice
  python manage.py sync_webhook_events . webhook_resources.yaml
else
  echo "current module is not 'default', skip interface-only release steps"
fi
```

Key change: `python manage.py sync_superuser` is moved from inside the `if` block to before it, so all modules (interface + engine) execute it.

- [ ] **Step 2: Verify script syntax**

Run: `bash -n bin/pre_release.sh`
Expected: No output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add bin/pre_release.sh
git commit -m "feat(admin): 所有模块执行 sync_superuser 确保 Engine Admin 可登录 --story=<tapdId>"
```

---

### Task 3: Create template tag for Engine modules

**Files:**
- Create: `bkflow/admin/templatetags/__init__.py`
- Create: `bkflow/admin/templatetags/engine_admin_tags.py`
- Test: `tests/interface/admin/test_engine_admin_portal.py`

- [ ] **Step 1: Write the failing test**

Create `tests/interface/admin/test_engine_admin_portal.py`:

```python
import pytest
from django.template import Template, Context

from bkflow.admin.models import ModuleInfo


@pytest.mark.django_db
class TestGetEngineModulesTag:
    def test_returns_empty_list_when_no_modules(self):
        template = Template("{% load engine_admin_tags %}{% get_engine_modules as modules %}{{ modules|length }}")
        result = template.render(Context())
        assert result.strip() == "0"

    def test_returns_modules_with_admin_url(self):
        ModuleInfo.objects.create(
            space_id=0,
            code="default",
            url="http://engine-default.example.com",
            token="test_token",
            type="TASK",
            isolation_level="all_resource",
        )
        template = Template(
            "{% load engine_admin_tags %}"
            "{% get_engine_modules as modules %}"
            "{{ modules.0.code }}|{{ modules.0.admin_url }}"
        )
        result = template.render(Context())
        assert "default" in result
        assert "http://engine-default.example.com/bkflow_admin/" in result

    def test_strips_trailing_slash_from_url(self):
        ModuleInfo.objects.create(
            space_id=1,
            code="engine-a",
            url="http://engine-a.example.com/",
            token="test_token",
            type="TASK",
            isolation_level="all_resource",
        )
        template = Template(
            "{% load engine_admin_tags %}"
            "{% get_engine_modules as modules %}"
            "{{ modules.0.admin_url }}"
        )
        result = template.render(Context())
        assert "http://engine-a.example.com/bkflow_admin/" in result
        assert "//bkflow_admin" not in result
```

Create `tests/interface/admin/__init__.py` if it doesn't exist.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py -v`
Expected: FAIL with `TemplateSyntaxError: 'engine_admin_tags' is not a registered tag library`

- [ ] **Step 3: Create templatetags package**

```bash
mkdir -p bkflow/admin/templatetags
touch bkflow/admin/templatetags/__init__.py
```

- [ ] **Step 4: Write the template tag**

Create `bkflow/admin/templatetags/engine_admin_tags.py`:

```python
from django import template

from bkflow.admin.models import ModuleInfo

register = template.Library()


@register.simple_tag
def get_engine_modules():
    return [
        {
            "code": m.code,
            "space_id": m.space_id,
            "isolation_level": m.get_isolation_level_display(),
            "admin_url": f"{m.url.rstrip('/')}/bkflow_admin/" if m.url else "",
        }
        for m in ModuleInfo.objects.all()
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bkflow/admin/templatetags/ tests/interface/admin/
git commit -m "feat(admin): 新增 engine_admin_tags 模板标签提供 Engine 模块数据 --story=<tapdId>"
```

---

### Task 4: Create Admin index template

**Files:**
- Create: `bkflow/admin/templates/admin/bkflow_index.html`

- [ ] **Step 1: Create template directory**

```bash
mkdir -p bkflow/admin/templates/admin
```

- [ ] **Step 2: Create the custom index template**

Create `bkflow/admin/templates/admin/bkflow_index.html`:

```html
{% extends "admin/index.html" %}
{% load engine_admin_tags %}

{% block content %}
{% get_engine_modules as engine_modules %}
<div id="engine-modules" style="margin-bottom: 30px;">
    <h2 style="margin-bottom: 12px;">Engine 模块</h2>
    <div style="display: flex; flex-wrap: wrap; gap: 12px;">
        {% for module in engine_modules %}
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px 20px; min-width: 220px; background: #f9f9f9;">
            <h3 style="margin: 0 0 8px; font-size: 16px;">{{ module.code }}</h3>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">空间 ID: {{ module.space_id }}</p>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">隔离级别: {{ module.isolation_level }}</p>
            {% if module.admin_url %}
            <a href="{{ module.admin_url }}" target="_blank"
               style="display: inline-block; margin-top: 10px; padding: 6px 16px; background: #417690; color: #fff; border-radius: 4px; text-decoration: none; font-size: 13px;">
                打开 Django Admin ↗
            </a>
            {% else %}
            <span style="display: inline-block; margin-top: 10px; color: #999; font-size: 13px;">未配置地址</span>
            {% endif %}
        </div>
        {% empty %}
        <p style="color: #999;">暂无已注册的 Engine 模块</p>
        {% endfor %}
    </div>
</div>
{{ block.super }}
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add bkflow/admin/templates/
git commit -m "feat(admin): 新增 Admin 首页 Engine 模块卡片模板 --story=<tapdId>"
```

---

### Task 5: Integration test for Admin index page

**Files:**
- Test: `tests/interface/admin/test_engine_admin_portal.py`

- [ ] **Step 1: Write the integration test**

Add to `tests/interface/admin/test_engine_admin_portal.py`:

```python
from django.test import TestCase, override_settings


@pytest.mark.django_db
class TestAdminIndexPage:
    def test_admin_index_shows_engine_modules_section(self, client):
        User = apps.get_model("account", "User")
        admin_user = User.objects.create_superuser(username="admin_test", password="test123")
        client.force_login(admin_user)

        ModuleInfo.objects.create(
            space_id=0, code="default", url="http://engine.example.com",
            token="t", type="TASK", isolation_level="all_resource",
        )

        response = client.get("/bkflow_admin/")
        content = response.content.decode()
        assert response.status_code == 200
        assert "Engine 模块" in content
        assert "default" in content
        assert "http://engine.example.com/bkflow_admin/" in content

    def test_admin_index_shows_empty_message_when_no_modules(self, client):
        User = apps.get_model("account", "User")
        admin_user = User.objects.create_superuser(username="admin_test2", password="test123")
        client.force_login(admin_user)

        response = client.get("/bkflow_admin/")
        content = response.content.decode()
        assert response.status_code == 200
        assert "暂无已注册的 Engine 模块" in content
```

- [ ] **Step 2: Run test — expected to fail until Task 6 wires up the template**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py::TestAdminIndexPage -v`
Expected: FAIL (custom template not yet active).

> Note: This test will pass after Task 6 completes.

- [ ] **Step 3: Commit**

```bash
git add tests/interface/admin/test_engine_admin_portal.py
git commit -m "test(admin): 新增 Admin 首页 Engine 模块集成测试 --story=<tapdId>"
```

---

### Task 6: Wire up custom index template

**Files:**
- Modify: `bkflow/admin/apps.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/interface/admin/test_engine_admin_portal.py`:

```python
from django.contrib import admin


class TestAdminSiteConfig:
    def test_index_template_is_set(self):
        assert admin.site.index_template == "admin/bkflow_index.html"

    def test_site_header_is_set(self):
        assert admin.site.site_header == "BKFlow 管理后台"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py::TestAdminSiteConfig -v`
Expected: FAIL — `admin.site.index_template` is `None`.

- [ ] **Step 3: Modify apps.py to configure admin.site**

Edit `bkflow/admin/apps.py`:

```python
from django.apps import AppConfig


class AdminConfig(AppConfig):
    name = "bkflow.admin"
    label = "bkflow_admin"

    def ready(self):
        from django.contrib import admin

        admin.site.index_template = "admin/bkflow_index.html"
        admin.site.site_header = "BKFlow 管理后台"
        admin.site.site_title = "BKFlow Admin"
        admin.site.index_title = "管理首页"
```

This approach sets properties on the default `admin.site` instance during app initialization, avoiding the need to create a custom `AdminSite` subclass or modify any existing `@admin.register` calls across the codebase.

- [ ] **Step 4: Run tests to verify template wiring and integration**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py::TestAdminSiteConfig tests/interface/admin/test_engine_admin_portal.py::TestAdminIndexPage -v`
Expected: All PASS (including the integration tests from Task 5).

- [ ] **Step 5: Commit**

```bash
git add bkflow/admin/apps.py tests/interface/admin/test_engine_admin_portal.py
git commit -m "feat(admin): 配置 Admin 首页使用自定义模板展示 Engine 模块入口 --story=<tapdId>"
```

---

### Task 7: Add `admin_link` to `ModuleInfoAdmin`

**Files:**
- Modify: `bkflow/admin/admin.py`
- Test: `tests/interface/admin/test_engine_admin_portal.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/interface/admin/test_engine_admin_portal.py`:

```python
@pytest.mark.django_db
class TestModuleInfoAdminLink:
    def test_admin_link_with_url(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0, code="default", url="http://engine.example.com",
            token="t", type="TASK", isolation_level="all_resource"
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert "http://engine.example.com/bkflow_admin/" in result
        assert 'target="_blank"' in result

    def test_admin_link_with_trailing_slash(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0, code="default", url="http://engine.example.com/",
            token="t", type="TASK", isolation_level="all_resource"
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert "http://engine.example.com/bkflow_admin/" in result
        assert "//bkflow_admin" not in result

    def test_admin_link_without_url(self):
        from bkflow.admin.admin import ModuleInfoAdmin

        module = ModuleInfo(
            space_id=0, code="default", url="",
            token="t", type="TASK", isolation_level="all_resource"
        )
        admin_instance = ModuleInfoAdmin(ModuleInfo, None)
        result = admin_instance.admin_link(module)
        assert result == "-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py::TestModuleInfoAdminLink -v`
Expected: FAIL — `ModuleInfoAdmin` has no attribute `admin_link`.

- [ ] **Step 3: Add admin_link to ModuleInfoAdmin**

Edit `bkflow/admin/admin.py`. Preserve existing `search_fields`, `list_filter`, `ordering` — only add `admin_link` to `list_display` and add the `admin_link` method:

```python
from django.contrib import admin
from django.utils.html import format_html

from bkflow.admin.models import ModuleInfo


@admin.register(ModuleInfo)
class ModuleInfoAdmin(admin.ModelAdmin):
    list_display = ("code", "space_id", "type", "url", "isolation_level", "admin_link")
    search_fields = ("space_id", "url", "type", "isolation_level", "code")
    list_filter = ("space_id", "url", "type", "isolation_level", "code")
    ordering = ["space_id"]

    def admin_link(self, obj):
        if not obj.url:
            return "-"
        admin_url = f"{obj.url.rstrip('/')}/bkflow_admin/"
        return format_html('<a href="{}" target="_blank">打开 Django Admin</a>', admin_url)

    admin_link.short_description = "Engine Admin"
```

Note: `search_fields`, `list_filter`, `ordering` are preserved exactly from the current code. Only `list_display` gains `"admin_link"` and the method is added.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py::TestModuleInfoAdminLink -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Run all tests for this feature**

Run: `pytest tests/interface/admin/test_engine_admin_portal.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bkflow/admin/admin.py tests/interface/admin/test_engine_admin_portal.py
git commit -m "feat(admin): ModuleInfo 列表页增加 Engine Admin 跳转链接 --story=<tapdId>"
```

---

### Task 8: Update `app_desc.yaml` for Engine env vars

**Files:**
- Modify: `app_desc.yaml`

- [ ] **Step 1: Add `BKFLOW_INIT_SUPERUSERS` to Engine module env vars**

In `app_desc.yaml`, under the `default-engine` module's `env_variables` section, add:

```yaml
      - key: BKFLOW_INIT_SUPERUSERS
        value: ""
        description: Django Admin 管理员用户名列表（逗号分隔）
```

This ensures the env var is declared in the deployment descriptor. Actual values will be configured in the PaaS platform per environment.

- [ ] **Step 2: Commit**

```bash
git add app_desc.yaml
git commit -m "chore(admin): Engine 模块声明 BKFLOW_INIT_SUPERUSERS 环境变量 --story=<tapdId>"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run the full test suite for affected areas**

Run: `pytest tests/interface/admin/ tests/engine/test_engine_admin.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Verify no lint errors**

Check edited files for lint issues and fix if any.

- [ ] **Step 3: Manual smoke test (Interface module)**

Start the Interface module locally and visit `/bkflow_admin/`. Verify:
- Admin homepage shows "Engine 模块" card section at the top
- Each registered Engine module displays code, space ID, isolation level
- "打开 Django Admin" links point to correct URLs
- ModuleInfo list page shows "Engine Admin" column with working links

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix(admin): 修复 Engine Admin 入口验证中发现的问题 --story=<tapdId>"
```
