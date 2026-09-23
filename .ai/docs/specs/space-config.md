---
name: bkflow-space-config
description: Use when configuring a BKFlow space, extending config metadata or controls, tracing config verification, or understanding TEXT/JSON/REF storage and interface/engine synchronization.
---

# BKFlow 空间配置技术参考

空间配置控制画布行为、Token 有效期、API 插件接入及插件可见性。当前配置中心采用声明式元数据和通用/复合控件。

- [用户说明](../../../docs/guide/space_config.md)：操作流程、字段示例与生效范围。
- [改版设计与已合入实现](../../../docs/specs/2026-07-06-space-config-redesign-design.md)：公开配置清单、接口响应、兼容边界及实际交付 PR。
- 本文按 2026-09-15 master `fd32a87f6fb3bf2c7629c00df4691c7b61633d14` 核对；修改时重新检查对应源码。

## 1. 代码入口

| 入口 | 职责 |
|---|---|
| [configs.py](../../../bkflow/space/configs.py) | 配置类注册、默认值、元数据、写入校验、外部验证 |
| [models.py](../../../bkflow/space/models.py) | 配置记录、TEXT/JSON/REF 读写及引擎同步 |
| [serializers.py](../../../bkflow/space/serializers.py) | 单项、批量与验证请求的校验 |
| [views.py](../../../bkflow/space/views.py) | 管理接口与通用验证分发 |
| [SpaceConfig/index.vue](../../../frontend/src/views/admin/Space/SpaceConfig/index.vue) | 元数据与已存记录合并、分组、搜索、保存和恢复默认 |
| [ConfigDetail.vue](../../../frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue) | 控件值与保存参数转换、源码模式及保存确认 |
| [controls/index.js](../../../frontend/src/views/admin/Space/SpaceConfig/controls/index.js) | 实际控件注册表 |
| [spaceConfig.js](../../../frontend/src/store/modules/spaceConfig.js) | 页面使用的站内接口及响应解包 |

## 2. 配置声明与页面行为

配置类继承 `BaseSpaceConfig`，由 `SpaceConfigMeta` 自动注册到 `SpaceConfigHandler`。必需属性为 `name`、`desc`；其余常用属性包括：

- `value_type`、`default_value`、`choices`、`example`、`is_mix_type`。
- `is_public`：`config_meta` 只枚举公开项，不替代权限校验。
- `group`、`help`、`ui`：页面分组、说明和控件声明。
- `verifiable`、`verify()`：外部测试能力；当前只有 `uniform_api` 实现具体测试。

当前有 10 个公开配置。`engine_space_config`、`callback_hooks` 不公开。元数据中的空默认值可能被 `process_config` 转为 `null`，页面根据是否存在配置记录判断“默认 / 已配置”，不是比较配置值。

页面按项 POST 创建或 PATCH 更新，点击“恢复默认”会 DELETE 记录；不使用 `batch_apply`。开关仍保存 `"true"` / `"false"` 字符串。新增控件必须同步注册表与 `ConfigDetail` 的类型转换，不能把声明中出现的名称当作已注册能力。

## 3. 存储与引擎同步

当前实现使用 `SpaceConfigValueType` 区分 `TEXT`、`JSON`、`REF`，没有 `config_type=INTERFACE/ENGINE` 字段。

| 类型 | 存储与读取 |
|---|---|
| TEXT | Interface `SpaceConfig.text_value` |
| JSON | Interface `SpaceConfig.json_value` |
| REF | Interface 保留配置引用记录，专用管理方法经 `TaskComponentClient` 同步 Engine；空间配置聚合查询从 Engine 取回值 |

`SpaceConfig` 唯一键为 `(space_id, name)`。普通 `get_config()` 在没有记录时返回配置类默认值；读取网关凭证等特殊项会调用其 `get_value()`。创建空间时显式写入管理员和 `flow_versioning="true"`，因此记录删除后的类默认值未必等于新建空间的初始设置。

### REF 配置：`engine_space_config`

```json
{
  "space": {"region": "test", "retry_limit": 3},
  "scope": {
    "biz_2": {"retry_limit": 1}
  }
}
```

`space` 和 `scope` 的叶子值支持字符串、数字和布尔值。读写经过 Interface 与 Engine 两侧：

1. `create_space_config()` 先创建 Interface 引用记录，把其 ID 作为 `interface_config_id` 调用 Engine upsert。
2. `update_space_config()`、`delete_space_config()` 同步对应 Engine 操作；这些方法使用本地数据库事务并在远端响应失败时回滚本地记录，不代表跨服务分布式事务。
3. `get_space_config_info()` 对 REF 调用 `get_engine_config()`，将返回的 `interface_config_id` 映射回配置记录 ID。
4. `batch_apply` 明确拒绝 REF，不能绕过专用同步路径。`engine_kv` 控件存在，但该配置不进入公开元数据，当前页面不提供入口。

## 4. 配置校验与外部测试

- `validate(value)`：保存前检查值的结构与约束。
- `verify(space_id, value, **params)`：执行外部请求并返回预览，不保存配置，也不是保存的前置要求。
- 站内入口：`POST /api/space/admin/space_config/verify/`，参数为 `space_id`、`name`、可选 `value` 与 `params`。
- 视图使用 `AdminPermission | SpaceSuperuserPermission` 及 `TenantScopeMixin`；强制从登录用户取 `operator`，删除 `params` 中的 `space_id` / `value`。
- HTTP 响应套统一 `{result, data, code, message}`，验证结果在外层 `data` 中：成功为 `{ok: true, data: ...}`，验证失败为 `{ok: false, error: ...}`。必须同时检查外层结果和内层 `ok`。

`uniform_api` 非空待测值优先，空值回退到已存配置；凭证默认取当前空间已保存的默认网关凭证。验证请求依次读取分类、API 列表、部分详情，支持 V4 `meta_url_template` 的版本解析，不跟随重定向。详情、计数和默认资源上限见[实现说明](../../../docs/specs/2026-07-06-space-config-redesign-design.md)。

测试仅使用默认 APIGW 鉴权头，未合并条目自定义 `headers`；成功不能证明实际插件执行或全部目录有效。`verifiable=True` 本身不会自动生成其他配置的前端测试按钮。

## 5. 修改时保留的兼容边界

- 网关凭证同时兼容 TEXT 凭证名与含 `default`、scope 覆盖的 JSON。表单编辑后输出 JSON 对象；凭证路由与凭证开放范围是不同概念。
- API 插件后端保留 V1 读取兼容，新保存按 V2 校验；前端不自动转换旧 V1 配置。当前 `api_categories` 是必填项。
- API 表单没有 `source_key` / `catalog_mode` 专用输入，修改时重建条目会丢失未覆盖的条目字段；使用这些字段的配置需要在 JSON 源码模式维护。不能承诺表单与源码完全无损往返。
- `space_plugin_config` 支持 `allow_all` / `allow_list` / `deny_list`，控制画布可见性，并可能影响已有节点编辑；它不改变实际执行权限。保存前的二次确认需要保留。
- `canvas_mode` 只影响后续新建流程的默认方向；已有流程不自动重排。
- `flow_versioning` 控制草稿及版本管理，不能写成“每次保存都会发布新版本”。`allow_multiple_triggers` 的后端数量校验针对定时触发器。
- Token 最小有效期为 1 小时，上限及续期触发方式以 [Token 授权说明](../../../docs/guide/token_authorization.md) 为准。
