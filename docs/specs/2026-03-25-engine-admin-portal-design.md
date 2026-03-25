# Engine 模块 Django Admin 管理入口设计

## 背景

BKFlow 采用一个 Interface 对应多个 Engine 的部署模式。当前只有 Interface 模块有前端页面入口，Engine 模块的 web 进程仅接收来自 Interface 的内部 API 调用，没有对外暴露的页面。

这导致一个问题：Django Admin 只能查看 Interface 的数据库，无法查看各个 Engine 模块的数据库。对于排障查数据、数据运维操作、运营监控等场景，开发/运维人员缺少方便的 Engine 数据管理手段。

## 设计目标

- 让 BKFlow 管理员能够方便地访问和管理每个 Engine 模块的数据库
- 复用 Engine 侧已有的 Django Admin 注册（`bkflow/task/admin.py`），不重复建设
- 改动范围最小化，不引入新的模块间通信模式

## 方案概述

1. **Engine 侧**：确保 Django Admin 可独立登录和访问
2. **Interface 侧**：在 Django Admin 中增加跳转到各 Engine 模块 Admin 的入口
3. **部署侧**：调整 Engine 模块的 web 进程，使其对 BKFlow 管理员可访问

## 详细设计

### 1. Engine 侧改动

#### 1.1 迁移 `sync_superuser` 命令到共享应用

`sync_superuser` 命令当前位于 `bkflow/interface/management/commands/sync_superuser.py`，属于 `bkflow.interface` 应用。Engine 的 `INSTALLED_APPS` 不包含 `bkflow.interface`，因此无法直接在 Engine 模块中执行该命令。

**改动**：将 `sync_superuser` 命令从 `bkflow/interface/management/commands/` 迁移到 `bkflow/contrib/operation_record/management/commands/`。`bkflow.contrib.operation_record` 是 Interface 和 Engine 双模块共享的应用，迁移后两侧均可执行该命令。

迁移后需验证 Interface 侧原有的 `sync_superuser` 调用不受影响（命令名不变，仅所属应用变化）。

#### 1.2 修改 `bin/pre_release.sh`

让 Engine 模块也执行 `sync_superuser`：

```bash
#!/bin/bash
python manage.py migrate
python manage.py createcachetable django_cache
python manage.py update_component_models
python manage.py update_variable_models
# 所有模块都执行 sync_superuser，确保 Django Admin 可登录
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

#### 1.3 环境变量要求

`sync_superuser` 依赖环境变量 `BKFLOW_INIT_SUPERUSERS`（逗号分隔的用户名列表）。**每个 Engine 模块的部署环境中必须配置此变量**，否则命令为空操作，管理员仍无法登录 Engine 的 Django Admin。

建议在 `app_desc.yaml` 中为 Engine 模块模板添加该环境变量的声明。

#### 1.4 Engine 侧无需其他代码改动

- **路由**：`urls.py` 中 `url(r"^bkflow_admin/", admin.site.urls)` 对所有模块生效
- **Model 注册**：`bkflow/task/admin.py` 已注册 `TaskInstance`、`PeriodicTask`、`AutoRetryNodeStrategy`、`TaskMockData`、`TaskOperationRecord`
- **认证**：Engine 与 Interface 均挂载 `blueapps` 账号模块与 `/account/` 路由，管理员通过蓝鲸统一登录进入各自模块

### 2. Interface 侧改动

#### 2.1 Admin 首页增加 Engine 模块卡片区域

在 Django Admin 首页顶部增加一个 "Engine 模块" 卡片区域，列出所有已注册的 Engine 模块及其 Admin 跳转链接，管理员进入 Admin 首页即可一目了然地看到所有 Engine 入口。

**实现方式**：自定义 `AdminSite` 子类 + 覆写 Admin 首页模板。

**a) 自定义 AdminSite**

新建 `bkflow/admin/admin_site.py`：

```python
from django.contrib.admin import AdminSite

class BKFlowAdminSite(AdminSite):
    site_header = "BKFlow 管理后台"
    site_title = "BKFlow Admin"
    index_title = "管理首页"
    index_template = "admin/bkflow_index.html"

    def each_context(self, request):
        context = super().each_context(request)
        from bkflow.admin.models import ModuleInfo
        engine_modules = ModuleInfo.objects.all()
        context["engine_modules"] = [
            {
                "code": m.code,
                "space_id": m.space_id,
                "isolation_level": m.isolation_level,
                "admin_url": f"{m.url.rstrip('/')}/bkflow_admin/" if m.url else "",
            }
            for m in engine_modules
        ]
        return context
```

**b) 自定义首页模板**

新建 `bkflow/admin/templates/admin/bkflow_index.html`，继承 Django 默认的 `admin/index.html`，在应用列表之前插入 Engine 模块卡片：

```html
{% extends "admin/index.html" %}
{% block content %}
<div id="engine-modules" style="margin-bottom: 20px;">
    <h2>Engine 模块</h2>
    <div style="display: flex; flex-wrap: wrap; gap: 12px;">
        {% for module in engine_modules %}
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; min-width: 220px; background: #f9f9f9;">
            <h3 style="margin: 0 0 8px;">{{ module.code }}</h3>
            <p style="margin: 4px 0; color: #666;">空间 ID: {{ module.space_id }}</p>
            <p style="margin: 4px 0; color: #666;">隔离级别: {{ module.isolation_level }}</p>
            {% if module.admin_url %}
            <a href="{{ module.admin_url }}" target="_blank"
               style="display: inline-block; margin-top: 8px; padding: 6px 16px; background: #417690; color: #fff; border-radius: 4px; text-decoration: none;">
                打开 Django Admin
            </a>
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

**c) 替换全局 admin.site**

修改 `urls.py`，将 `admin.site` 替换为自定义的 `BKFlowAdminSite` 实例：

```python
from bkflow.admin.admin_site import BKFlowAdminSite

bkflow_admin_site = BKFlowAdminSite(name="bkflow_admin")

urlpatterns = [
    url(r"^bkflow_admin/", bkflow_admin_site.urls),
    ...
]
```

注意：使用自定义 `AdminSite` 后，所有 `@admin.register(Model)` 需要改为 `@admin.register(Model, site=bkflow_admin_site)`，或在各 app 的 `admin.py` 中使用 `bkflow_admin_site.register(Model, ModelAdmin)` 替代。也可以通过在 `AdminConfig.ready()` 中将 `django.contrib.admin.site` 替换为自定义实例来避免修改所有注册代码。

#### 2.2 ModuleInfo 列表页增加跳转链接（辅助入口）

作为首页卡片的补充，在 `ModuleInfoAdmin` 的列表页也增加跳转链接列，方便管理员在查看模块详情时直接跳转。

修改 `bkflow/admin/admin.py`：

```python
from django.utils.html import format_html

@admin.register(ModuleInfo)
class ModuleInfoAdmin(admin.ModelAdmin):
    list_display = ("code", "space_id", "type", "url", "isolation_level", "admin_link")
    search_fields = ("space_id", "url", "type", "isolation_level", "code")
    list_filter = ("type", "isolation_level")

    def admin_link(self, obj):
        if not obj.url:
            return "-"
        admin_url = f"{obj.url.rstrip('/')}/bkflow_admin/"
        return format_html('<a href="{}" target="_blank">打开 Django Admin</a>', admin_url)

    admin_link.short_description = "Engine Admin"
```

### 3. 部署侧改动

#### 3.1 Engine web 访问策略

在蓝鲸 PaaS 平台调整 Engine 模块的访问策略，使 BKFlow 管理员能够通过浏览器访问 Engine 模块的 web 进程。

**关键要求**：
- `ModuleInfo.url` 字段存储的地址需要是**管理员浏览器可达的 URL**，不能是仅内部可达的集群地址
- 如果当前 `ModuleInfo.url` 使用的是内部地址，需要为管理员访问单独配置一个可达的域名/路径，或将 `ModuleInfo.url` 更新为管理员可达的地址
- Engine 的 web 访问地址需要在蓝鲸统一登录的 SSO 域名配置范围内，确保登录跳转正常

#### 3.2 安全边界

- **访问范围**：Engine web 仅对 BKFlow 管理员开放，通过 PaaS 平台的访问控制（白名单/VPN/内网限制等）约束
- **Django Admin 权限**：即使能访问 Engine web，也需要 `is_staff=True` 才能进入 Django Admin
- **注意**：Engine 与 Interface 是独立的 Django 进程，各自维护独立的 session。管理员登录 Interface 后跳转到 Engine 时，如果尚未在 Engine 侧登录，会被重定向到蓝鲸统一登录

#### 3.3 环境变量配置

每个 Engine 模块需确保以下环境变量已配置：

| 变量 | 说明 |
|---|---|
| `BKFLOW_INIT_SUPERUSERS` | 管理员用户名列表（逗号分隔），与 Interface 保持一致 |

## 改动清单

| 改动点 | 文件 | 工作量 |
|---|---|---|
| 迁移 `sync_superuser` 到共享应用 | `bkflow/interface/management/commands/sync_superuser.py` → `bkflow/contrib/operation_record/management/commands/sync_superuser.py` | 移动文件，创建 `management/commands/` 目录结构 |
| 修改 `pre_release.sh` | `bin/pre_release.sh` | ~2 行调整 |
| 自定义 AdminSite | `bkflow/admin/admin_site.py`（新建） | ~30 行 |
| Admin 首页模板 | `bkflow/admin/templates/admin/bkflow_index.html`（新建） | ~30 行 |
| 替换全局 admin.site | `urls.py` + 各 `admin.py` 注册适配 | ~10 行调整 |
| ModuleInfo 列表增加跳转链接 | `bkflow/admin/admin.py` | ~10 行 |
| Engine 模块环境变量配置 | PaaS 平台 | 运维配置 |
| Engine web 对管理员开放 | PaaS 平台 | 运维配置 |

## 使用流程

1. 管理员登录 Interface 的 Django Admin（`/bkflow_admin/`）
2. 在首页顶部的 "Engine 模块" 卡片区域，找到目标 Engine 模块
3. 点击 "打开 Django Admin" 按钮，跳转到对应 Engine 的 Django Admin
4. 通过蓝鲸统一登录后即可管理 Engine 数据

也可通过 "模块信息表"（ModuleInfo）列表页的 "Engine Admin" 链接列跳转。

## Engine 侧已注册的 Admin Model

| Model | 管理能力 |
|---|---|
| `TaskInstance` | 按 instance_id/name/creator 搜索，按创建/结束时间过滤 |
| `PeriodicTask` | 按 template_id/trigger_id/name/creator 搜索 |
| `AutoRetryNodeStrategy` | 按 root_pipeline_id/node_id 精确搜索 |
| `TaskMockData` | 按 taskflow_id/mock_data_ids 搜索 |
| `TaskOperationRecord` | 操作记录管理 |
| Pipeline 引擎表 | 由 `pipeline.contrib.engine_admin` 提供的引擎管理能力 |

## 后续扩展

- 如果需要在 Engine 侧管理更多 Model，只需在 `bkflow/task/admin.py` 中添加 `@admin.register` 注册即可，Interface 侧无需改动
- 如果需要更丰富的导航（如按空间分组、显示 Engine 健康状态），可以后续在 Interface Admin 中添加自定义视图
