# 移除开放插件来源准入（OpenPluginSpaceGrant）

> 本文是 [2026-06-26-sops-open-plugin-full-capability-design.md](./2026-06-26-sops-open-plugin-full-capability-design.md) 第 4 章「两层空间准入」的后续决策，取消其中的第 1 层。

## 1. 背景

开放插件 V4 原设计采用两层准入：

- 第 1 层（平台级）`OpenPluginSpaceGrant`：平台管理员授权某个空间可接入某个 `source_key`
- 第 2 层（空间级）`SpaceOpenPluginAvailability`：空间管理员逐个开启插件

第 1 层在发布前的风险评估中被判定为不可接受，随本文一并移除。

## 2. 问题

### 2.1 准入判断的落点过高，会静默打掉存量面板

`is_granted` 被加在 `_get_space_uniform_api_list_info` 的最外层，即**所有** `uniform_api` 目录/分类查询的入口，而不只是 V4 开放插件路径：

```python
source_key = api_entry.source_key or api_name
if not OpenPluginGrantService.is_granted(space_id=space_id, source_key=source_key):
    return _empty_catalog_data(config_key)
```

存量 V2/V3 API 插件与 V4 目录机制无关，但共用这个入口。未授予 grant 的空间调用列表接口会拿到空列表且 `result=true`，前端表现为「一个插件都没有」，没有任何报错可循，排查成本极高。

### 2.2 没有自动授予入口

数据迁移 `plugin/0005_backfill_open_plugin_grant` 只回填了迁移执行那一刻已配置 `uniform_api` 的空间。此后：

- 新建空间配置 `uniform_api` 后不会自动获得 grant
- 已有空间新增一个 `api_key`（新 `source_key`）后不会自动获得 grant

两种情况都必须平台管理员手工执行 `grant_open_plugin_source` 管理命令才能恢复，且失败方式是静默的（见 2.1）。

### 2.3 收益不足以抵消风险

第 1 层想解决的是「哪些空间可以接入某个开放来源」。但接入一个来源本身就需要空间管理员在空间配置里填写 `uniform_api` 的 `meta_apis`/`api_categories` 地址，并配置 APIGW 凭证——这已经是一道显式的人工闸门。第 1 层在其之上叠加的是一道**静默失败**的闸门，边界与既有配置动作重叠（原设计 §9.2 已把这个边界列为关注点）。

## 3. 决策

整体移除 `OpenPluginSpaceGrant` 准入机制。V4 开放插件的管控完全交给 `SpaceOpenPluginAvailability` 空间级开关（新插件默认关闭，属于保守默认）。

## 4. 移除后的管控模型

### 4.1 存量 V2/V3 API 插件

空间配置里配好 `uniform_api` 即可使用，无任何额外开关。这是移除前的历史行为，本次改动是恢复而非放宽。

### 4.2 V4 开放插件

需要走完四步，缺一不可：

1. **空间配置**：空间管理员配置 `uniform_api`（`meta_apis` / `api_categories` / 可选 `source_key`），并配置 `ApiGatewayCredentialConfig` 指向的 APIGW 凭证——目录同步取不到凭证会直接失败。
2. **目录同步**：interface beat 的 `dispatch_open_plugin_catalog_sync` 按 `BKAPP_OPEN_PLUGIN_CATALOG_SYNC_CRONTAB`（默认 `*/30 * * * *`）遍历全部已配置来源投递同步。`_refresh_catalog_index` 只索引 `wrapper_version == v4.0.0` 的条目写入 `OpenPluginCatalogIndex`，同时为每个插件建一条 `SpaceOpenPluginAvailability` 且 **`enabled=False`**。
3. **空间开启**：空间管理员通过 `SpaceConfigAdminViewSet` 的 `open_plugins/toggle`、`open_plugins/enable_all`、`open_plugins/disable_source` 开启插件。
4. **使用**：保存模板、建任务、启动任务时 `OpenPluginSnapshotService` 会重新校验目录项存在、`status=available`、精确业务版本仍在 `versions` 列表中、且 `enabled=True`。

### 4.3 两类插件的可用条件对比

| 条件 | 存量 V2/V3 | V4 开放插件 |
|---|---|---|
| 空间配置 `uniform_api` | 必需 | 必需 |
| APIGW 凭证 | 调用时需要 | 目录同步 + 调用都需要 |
| 目录同步落库 | 不涉及 | 必需 |
| 空间 per-plugin 开关 | 不涉及 | 必需，默认关 |
| 保存/建任务/启动预检 | 不涉及 | 必需 |

## 5. 变更清单

### 5.1 删除

| 文件 | 说明 |
|---|---|
| `bkflow/plugin/models.py` | `OpenPluginSpaceGrant` 模型 |
| `bkflow/plugin/services/open_plugin_grant.py` | `OpenPluginGrantService` |
| `bkflow/plugin/management/commands/grant_open_plugin_source.py` | 批量授予/撤销管理命令 |
| `bkflow/plugin/admin.py` | `OpenPluginSpaceGrantAdmin` 注册 |
| `bkflow/plugin/migrations/0004_open_plugin_space_grant.py` | 建表迁移 |
| `bkflow/plugin/migrations/0005_backfill_open_plugin_grant.py` | 存量回填数据迁移 |

### 5.2 清理的校验点

| 位置 | 原行为 | 现行为 |
|---|---|---|
| `uniform_api.py::_get_space_uniform_api_list_info` | 未准入返回空目录 | 不再判断，直接按 `catalog_mode` 取数 |
| `uniform_api.py::_validate_open_plugin_meta_source` | 未准入抛 `ValidationError` | 整个函数删除，`source_key` 仍从请求中弹出以免透传远端 |
| `OpenPluginCatalogService.list_space_plugins` | 按 grant 过滤来源 | 只按 `space_id` / `source_key` 过滤 |
| `OpenPluginCatalogService.enable_all_visible_plugins` | 未准入抛 `ValueError` | 直接按目录可见项开启 |
| `PluginSchemaService._list_uniform_api_plugins_from_catalog` | 无 grant 返回空列表 | 只按空间开关过滤 |
| `PluginSchemaService._raise_uniform_api_catalog_access_error` | 未准入抛「来源未准入」 | 只判断目录状态与空间开关 |
| `OpenPluginSnapshotService._validate_resolved_reference` | 未准入抛 `ValidationError`，签名含 `space_id` | 去掉 grant 判断，`space_id` 入参一并移除 |
| `SpaceConfigAdminViewSet` 的 open_plugins 三个写接口 | 未准入返回 400 | 不再判断，同时移除为返回该 400 而加的 `EXEMPT_STATUS_CODES` 覆写 |

### 5.3 行为变化

- `dispatch_open_plugin_catalog_sync` 从「已配置 ∩ 已准入」改为覆盖全部已配置来源。由于回填迁移已把当时全部已配置来源授予 grant，两个集合在存量数据上基本一致，实际投递量无明显变化。
- 空间开放插件列表接口去掉了恒为 `true` 的 `granted` 字段（前端未使用）。
- APIGW 文档中 `list_plugins`、`get_plugin_schema`、`create_task` 系列、`operate_task` 系列的准入描述与失败示例已同步。

## 6. 迁移处理

`plugin/0004` 与 `plugin/0005` **没有进入过任何 release tag**——最新的 `release_master_202608071158` 早于开放插件合入 master。因此直接从迁移链摘除，`0006_remove_open_plugin_run_callback_ref` 依赖回指 `0003_openpluginruncallbackref`，不再叠加一个删表迁移。生产环境走的是干净的全新建表路径，`makemigrations --check` 确认 `plugin` app 无待生成迁移。

已经跑过这批迁移的预发布/开发环境会残留一张空的 `plugin_openpluginspacegrant` 表和两条 `django_migrations` 记录，不影响启动和后续迁移，可按需手工清理：

```sql
DROP TABLE IF EXISTS plugin_openpluginspacegrant;
DELETE FROM django_migrations
WHERE app = 'plugin'
  AND name IN ('0004_open_plugin_space_grant', '0005_backfill_open_plugin_grant');
```

## 7. 已知缺口

以下两点在移除 grant 之前就存在，但此前被第 1 层闸门遮挡，现在会更容易被触发，需要后续处理：

1. **默认 `remote` 模式下 V4 插件「看得见但用不了」**。`catalog_mode` 默认为 `remote`，此时列表直接透传远端返回，不经过 `SpaceOpenPluginAvailability` 过滤；而保存模板/建任务时的预检会要求 `enabled=True`。因此远端返回的 V4 插件会出现在画布面板里，选中后保存报「开放插件 [x] 在当前空间未开放」。`cache_first` / `cache_only` 模式没有这个问题。
2. **没有前端开关页面**。`open_plugins` 系列管理接口只有后端实现，前端未接入。本次一并把 `OpenPluginCatalogIndex` 和 `SpaceOpenPluginAvailability` 注册进 Django admin（后者的 `enabled` 支持列表页直接勾选），作为页面补齐前的运维兜底；此前这两张表在 admin 里都不可见，开放插件那批模型中唯一注册过的恰恰是本次删除的 `OpenPluginSpaceGrant`。在前端页面补齐之前，V4 插件的开启仍是一个纯后台动作。

## 8. 关联

- 原设计：[2026-06-26-sops-open-plugin-full-capability-design.md](./2026-06-26-sops-open-plugin-full-capability-design.md)
- 原实现计划：[../plans/2026-06-26-sops-open-plugin-full-capability.md](../plans/2026-06-26-sops-open-plugin-full-capability.md)
- PR：[TencentBlueKing/BKFlow#862](https://github.com/TencentBlueKing/BKFlow/pull/862)
