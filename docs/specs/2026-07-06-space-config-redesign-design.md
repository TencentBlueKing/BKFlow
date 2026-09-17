# 空间配置改版设计与已合入实现

- 初始设计：2026-07-06；实现核对：2026-09-15。
- 状态：按 master 已合入代码整理，不是待执行的实施计划。
- 核对基线：[`fd32a87f6fb3bf2c7629c00df4691c7b61633d14`](https://github.com/TencentBlueKing/BKFlow/commit/fd32a87f6fb3bf2c7629c00df4691c7b61633d14)。记录的是源码行为，不代表某个部署环境已验收。
- 用户操作与字段示例见[空间配置说明](../guide/space_config.md)；存储与扩展入口见[空间配置技术参考](../../.ai/docs/specs/space-config.md)。

## 1. 背景与设计取舍

空间配置包含简单开关、管理员列表、凭证路由和 API 插件等不同结构。原有通用编辑方式难以同时说明配置用途、影响和复杂字段的填写方式。

采用声明式元数据与双栏配置中心：后端集中声明分组、帮助、控件和验证能力；前端使用通用控件及少量复合控件。相比继续使用表格弹窗，这种方式可容纳复杂配置及说明；相比每个配置单独开发页面，它让使用已有控件的新配置复用页面框架。

设计保留现有配置存储及读写入口。配置校验、保存和外部连通性测试分别处理，复杂项提供 JSON 源码入口。JSON 入口支持维护表单未覆盖的字段，但不意味着所有字段都能在两种模式间无损往返。

## 2. 当前公开配置范围

`config_meta` 仅返回 `is_public=True` 的配置。当前共 10 项：

| 分组 | 配置名 | 控件 | 无配置记录时的默认值 |
|---|---|---|---|
| 权限与安全 `access_security` | `superusers` | `member_selector` | `[]`；创建空间时写入创建者 |
| 权限与安全 | `token_expiration` | `input` | `"1h"` |
| 权限与安全 | `token_auto_renewal` | `switch` | `"true"` |
| 权限与安全 | `api_gateway_credential_name` | `credential_map` | 无默认凭证 |
| 流程与画布行为 `flow_canvas` | `flow_versioning` | `switch` | `"false"`；创建空间时写入 `"true"` |
| 流程与画布行为 | `allow_multiple_triggers` | `switch` | `"false"` |
| 流程与画布行为 | `gateway_expression` | `radio` | `"boolrule"` |
| 流程与画布行为 | `canvas_mode` | `radio` | `"horizontal"` |
| API 与插件集成 `api_integration` | `uniform_api` | `api_plugin_config` | `{}` |
| API 与插件集成 | `space_plugin_config` | `plugin_scope` | `{"default":{"mode":"allow_all","plugin_codes":[]}}` |

`engine_space_config` 为非公开的 `REF` 配置；虽然保留了 `engine_kv` 元数据和控件，但它不出现在当前配置中心。已废弃的 `callback_hooks` 同样不公开。缺失分组或未知分组归入前端“未分类”。

上述默认值指配置类的回退值，不等于创建空间后的实际记录。`config_meta` 的 `process_config` 会把空列表、空对象等假值转成 `null`，页面再结合配置类型处理展示。

## 3. 元数据与控件契约

后端实现：[configs.py](../../bkflow/space/configs.py)。`SpaceConfigMeta` 自动注册配置类，`BaseSpaceConfig.to_dict()` 输出：

| 属性 | 当前用途 |
|---|---|
| `name`、`desc` | 配置标识与显示名称 |
| `is_public` | 是否纳入公开元数据 |
| `value_type`、`default_value`、`choices`、`example` | 存储类型、默认值、候选值与示例 |
| `is_mix_type` | 同一配置允许 TEXT 字符串或 JSON 对象，如网关凭证 |
| `group` | 页面分组 |
| `help` | `summary`、`effect`、`media`、`doc_link` |
| `ui` | `control` 及对应控件需要的标签、选项、校验提示等参数 |
| `verifiable` | 是否声明测试能力；当前仅 `uniform_api=True` |

`validate(value)` 用于写入前的配置校验；`verify(space_id, value, **params)` 用于外部请求和预览，基类默认抛出 `SpaceConfigVerifyNotSupported`。两者不互相替代，保存也不要求先调用测试。

前端以 [controls/index.js](../../frontend/src/views/admin/Space/SpaceConfig/controls/index.js) 的注册表为准：

- 通用控件：`switch`、`radio`、`select`、`input`、`member_selector`、`json`。
- 复合控件：`credential_map`、`api_plugin_config`、`plugin_scope`、`engine_kv`。
- 未声明或未注册的控件回退到 JSON 编辑器。旧方案列出的 `number`、`url`、`string_list` 没有独立注册组件，不能仅凭声明就视为已支持。

帮助信息的展示也以页面实现为准：当前画布模式使用内置横向/纵向示意图；不能把 `help.media` 的声明当作所有配置均有通用媒体展示能力。

## 4. 页面与保存流程

实现入口：[SpaceConfig/index.vue](../../frontend/src/views/admin/Space/SpaceConfig/index.vue)、[ConfigDetail.vue](../../frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue)。

1. 页面并行获取公开元数据和空间已存配置，按 `name` 合并。没有记录的项标为“默认”，有记录的项标为“已配置”，并非通过比较数值判断状态。
2. 左侧按分组列出配置，可按显示标签或配置名搜索；右侧展示帮助与控件。
3. 编辑仅改变当前表单值，点击“保存”才提交当前项。无变更时保存按钮禁用。当前切换配置项会重新创建详情组件，没有未保存变更的离开确认。
4. 保存前运行控件校验；管理员至少保留一位。空间插件配置另有保存确认，提醒对已有流程编辑的影响。
5. 有记录时 PATCH 更新，无记录时 POST 创建。失败状态用于当前页面提示，不是后台持续探测配置健康状态。
6. “恢复默认”经确认后删除当前配置记录，再按默认值展示；空间管理员项不提供该按钮。

TEXT 开关存储 `"true"` / `"false"` 字符串。JSON 项写入 `json_value`；网关凭证根据值的类型选择 TEXT 或 JSON。复合控件可切换“表单结构 / JSON源码”，源码保存仍需通过后端校验。

页面的逐项保存不使用 `batch_apply`。批量接口虽存在，但明确拒绝 `REF`，且不应据此推定它与逐项保存具有相同的混合类型、引擎同步语义。

## 5. 管理接口

路由前缀为 `/api/space/admin/space_config/`，实现见 [urls.py](../../bkflow/space/urls.py)、[views.py](../../bkflow/space/views.py)、[serializers.py](../../bkflow/space/serializers.py)。以下是站内管理接口，不等同于 APIGW 对外资源声明。

| 方法与相对路径 | 主要参数 | 用途 |
|---|---|---|
| GET `config_meta/` | `space_id` | 公开配置元数据字典，按配置名索引 |
| GET `get_all_space_configs/` | `space_id` | 空间已存配置记录列表，不补齐未存的默认项 |
| POST 空路径 | `space_id`、`name`、`value_type`、`text_value` 或 `json_value` | 创建配置记录 |
| PATCH `{id}/` | 页面传入配置标识、类型和值 | 修改已有记录；`id` 是配置记录 ID |
| DELETE `{id}/` | 配置记录 ID | 删除记录，恢复默认行为 |
| POST `batch_apply/` | `space_id`、`configs` | 批量应用非 REF 配置，非当前页面保存入口 |
| POST `verify/` | `space_id`、`name`、可选 `value`、可选 `params` | 测试配置，不保存 |

管理视图使用 `AdminPermission | SpaceSuperuserPermission`，并继承 `TenantScopeMixin`；租户及空间访问约束继续适用。公开元数据控制页面枚举，不替代接口鉴权。

### 5.1 验证请求与响应

验证一条 API 接入的请求示例（域名需替换为部署允许的 APIGW 地址）：

```json
{
  "space_id": 1,
  "name": "uniform_api",
  "value": {
    "api": {
      "demo": {
        "display_name": "示例 API",
        "meta_apis": "https://apigw.example.com/prod/api/list/",
        "api_categories": "https://apigw.example.com/prod/api/category_list/"
      }
    }
  },
  "params": {"api_key": "demo", "credential_name": "demo_app"}
}
```

HTTP 响应有 [SimpleGenericViewSet](../../bkflow/utils/views.py) 的统一外层包装。下面是结构示例，不是实际环境的测试结果：

```json
{
  "result": true,
  "code": "0",
  "message": "",
  "data": {
    "ok": true,
    "data": {
      "api_key": "demo",
      "credential_name": "demo_app",
      "category_length": 1,
      "api_length": 1,
      "samples": [{"id": "demo_api", "name": "示例接口", "method": "GET"}]
    }
  }
}
```

校验通过后的验证异常通常返回外层 `result=true`、内层 `data.ok=false` 与 `data.error.message`；不支持验证时另带 `not_supported=true`。序列化、鉴权等异常按外层异常流程处理。调用方不能只检查 HTTP 状态或外层 `result`，还需检查内层 `ok`。成功字段是 `data`，不是旧方案中的 `preview`。

### 5.2 `uniform_api.verify` 的实际范围

- 非空 `value` 使用请求中的待测值并先做基础校验；未提供或传入空值时回退到空间已存配置。页面逐条测试发送该条表单值，不落库。
- `api_key` 缺省为 `default`；凭证名缺省取该空间已保存的默认网关凭证。页面测试不传凭证覆盖参数，因此需要先保存默认凭证配置。
- 视图强制使用 `request.user.username` 作为 `operator`，并从 `params` 删除 `space_id`、`value`，避免参数覆盖或重复传参。不能恢复旧计划中的 `params.setdefault("operator", ...)`。
- 查找当前空间的凭证并读取 `bk_app_code` / `bk_app_secret`，生成默认 APIGW 鉴权头；请求不跟随重定向。当前测试流程没有合并条目里的自定义 `headers`。
- 依次请求分类列表、分类下的 API 列表和部分 API 详情，并校验各级响应协议。详情 URL 支持直接 `meta_url`，以及用 `latest_version` 或 `default_version` 解析 `meta_url_template`。
- 默认最多处理 50 个分类、发起 50 次列表请求、抽样 5 个详情，并在阶段之间检查 60 秒总时间预算。分别对应 `UNIFORM_API_VERIFY_MAX_CATEGORIES`、`UNIFORM_API_VERIFY_MAX_LIST_REQUESTS`、`UNIFORM_API_VERIFY_MAX_META_SAMPLES`、`UNIFORM_API_VERIFY_MAX_TOTAL_TIMEOUT`；预算检查不是对在途请求的精确中断。
- 每个分类只取首批列表；详情样本来自遇到的首个非空 API 列表。`category_length` 是截断后的分类数，`api_length` 是已请求分类返回的 `total` 之和，不是全目录去重计数。存在 API 但没有成功校验任何详情时返回失败。

测试成功表示这些目录及样本请求通过，不代表全部 API、插件执行、回调或所有自定义请求头已验证。

## 6. 兼容行为与实现边界

| 内容 | 当前实现 |
|---|---|
| 网关凭证 | 兼容旧 TEXT 凭证名和含 `default`、scope 覆盖的 JSON；表单从当前空间的 BK_APP 凭证中选择，编辑后输出对象 |
| 凭证创建与作用域 | 跳转“凭证管理”创建；未实现旧原型中的侧滑新建、失效引用专用状态和按凭证 scope 禁选 |
| API 插件结构 | 后端 `UniformAPIConfigHandler` 保留 V1 读取兼容；新写入以 V2 的 `api` 字典校验，前端表单不自动转换旧 V1 顶层结构 |
| API 插件高级字段 | 表单编辑 `api_key`、`display_name`、`meta_apis`、`api_categories`、`headers`；`common` 可随顶层对象保留，但没有专用表单 |
| API 表单往返 | 修改表单会重建每条 API 对象，未覆盖的 `source_key`、`catalog_mode` 等条目字段不会完整保留；含这些字段的配置应在 JSON 源码模式编辑并保存 |
| 分类 URL | 虽然旧设计及部分帮助文字写“可选”，当前 `ApiModel` 要求该字段，表单和验证流程均要求填写 |
| 插件可见范围 | 支持 `allow_all`、`allow_list`、`deny_list`；`allow_all` 保存时清空 `plugin_codes`。影响画布可见性及已有节点编辑，不是运行时授权开关 |
| 引擎配置 | `engine_space_config` 不公开，`batch_apply` 拒绝 REF；不能把存在 `EngineKv.vue` 解读为页面已开放引擎配置 |
| Token | 实际续期与上限以 [Token 授权说明](../guide/token_authorization.md) 为准，不能理解为后台临期自动延长或普通业务请求自动续期 |

## 7. 扩展与维护

1. 在配置类声明 `name`、`desc`、存储类型、默认值、`group`、`help`、`ui` 及实际校验逻辑。使用已注册的普通控件可以复用现有页面。
2. 新增控件时检查注册表、`ConfigDetail` 的类型转换与源码模式、默认值展示和输入输出约定，不能仅增加一个 `ui.control` 名称。
3. 新增验证实现需同时接入前端交互。`verifiable=True` 不会自动生成任意配置的测试按钮；当前 API 复合控件自行提供测试入口。
4. 检查已有值、混合类型、JSON 源码往返、恢复默认和权限范围，再更新用户说明。涉及 REF 时沿用专用引擎同步流程。

## 8. 交付记录与历史方案

| 阶段 | 实际交付 |
|---|---|
| 元数据、校验与后端接口 | [#893](https://github.com/TencentBlueKing/BKFlow/pull/893)，源分支 `kaedePing:feat/optimize_space_config_final` |
| 双栏页面、通用与复合控件 | [#896](https://github.com/TencentBlueKing/BKFlow/pull/896)，源分支 `Mianhuatang8:merge_space_rebuild_to_master` |
| V4 API 详情验证兼容修复 | [#903](https://github.com/TencentBlueKing/BKFlow/pull/903) |
| 本文核对 | 包含上述 PR 及基线 master 中后续改动；原 P1/P2/P3 步骤不再视为待执行清单 |

最初方案及原型保留在 [#782](https://github.com/TencentBlueKing/BKFlow/pull/782)。以下固定到历史提交，仅用于追溯设计，不作为现行接口或验收标准：

- [P1 实施计划](https://github.com/TencentBlueKing/BKFlow/blob/dea2ac2cad5553adb6733fca7f4a2598e511a242/docs/plans/2026-07-06-space-config-redesign.md)。
- [P2/P3 实施计划](https://github.com/TencentBlueKing/BKFlow/blob/dea2ac2cad5553adb6733fca7f4a2598e511a242/docs/plans/2026-07-10-space-config-redesign-p2-p3.md)。
- [历史原型与截图](https://github.com/TencentBlueKing/BKFlow/tree/dea2ac2cad5553adb6733fca7f4a2598e511a242/prototypes/output/space-config-redesign)。
