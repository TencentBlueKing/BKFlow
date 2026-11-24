### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

画布侧判断空间是否启用插件目录（SDK接口）

返回内容与空间配置页的 4.1 `plugin_catalog_migration` 完全一致（复用同一个 `get_status_view`），但权限不同：本接口面向画布前端的普通编排用户，权限为 `AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions`，持有效 `BKFLOW_TOKEN` 即可读取。管理页的 1.1 `plugins/summary` 与 4.1 权限不变。

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
|--------------|--------|----|------------------------------------------------------------|
| X-Bk-Tenant-Id | string | 否 | 多租户开启时全租户应用必填，单租户应用可省略；必须与资源空间租户一致 |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------------|---------|-----|----------|
| space_id | int | 是 | 空间ID |

### 请求参数示例

```
GET /api/plugin_catalog/plugins/migration_status/?space_id=1
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "space_id": 1,
        "ready": true,
        "migrated_at": "2026-09-23 14:32",
        "migrated_by": "admin",
        "legacy_snapshot": {
            "filter_mode": "allow_list",
            "filter_mode_text": "仅显示名单中的插件",
            "plugins": [
                {"code": "bk_http_request", "name": "HTTP 请求"},
                {"code": "python_code", "name": "Python代码"}
            ],
            "scope_overrides": [
                {"scope": "node_bk_http_request_1", "mode": "deny_list", "plugin_codes": ["bk_display"]}
            ],
            "snapshot_note": "初始化插件目录时保存；如有改动，再次初始化插件分类目录时可以恢复此配置",
            "open_plugin_enabled_count": 12
        }
    },
    "message": "",
    "code": "0"
}
```

### 返回结果参数说明

| 字段 | 类型 | 描述 |
|---------|--------|-----------------------|
| result | bool | 返回结果，true为成功，false为失败 |
| code | string | 返回码，0表示成功，其他值表示失败 |
| message | string | 错误信息 |
| data | dict | 返回数据 |

#### data 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| space_id | int | 空间ID |
| ready | bool | 是否已完成插件目录初始化迁移；false 表示本空间尚未启用插件目录 |
| migrated_at | string | 迁移时间，格式 YYYY-MM-DD HH:MM（不带秒） |
| migrated_by | string | 迁移操作人 |
| legacy_snapshot | dict | 迁移那一刻的旧配置只读快照，已加工成可直接渲染的结构 |

> `ready=false` 时前端应提示「本空间尚未启用插件目录，请联系运维执行初始化命令」。本接口只读，不提供触发迁移的入口；存量空间初始化只有运维命令 `python manage.py initialize_plugin_catalog --all-spaces`，新空间在 `create_space` 时自动初始化。
