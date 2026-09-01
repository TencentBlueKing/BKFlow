# 空间配置改版设计（可配置 / 可解释 / 可验证 / 可扩展）

- 日期：2026-07-06
- 状态：设计已评审（分段确认通过），待评审整篇后转实现计划
- 范围：空间管理页（`Space/SpaceConfig`）的公开配置项交互与后端元数据机制

## 1. 背景与问题

当前空间配置（`bkflow/space/configs.py` + `frontend/src/views/admin/Space/SpaceConfig/index.vue`）存在两类突出的可用性问题：

1. **裸 JSON 配置难用**：`uniform_api`、`space_plugin_config`、`superusers`、`engine_space_config`、`api_gateway_credential_name` 等配置要求用户手写符合"隐藏 schema"的 JSON，`example` 仅作为 placeholder，填错要保存后甚至用到时才发现。
2. **裸下拉不达意**：`canvas_mode`（horizontal/vertical）、`gateway_expression`（boolrule/FEEL/MAKO）、`token_auto_renewal`、`flow_versioning`、`allow_multiple_triggers` 等只展示裸值，用户不知道"选了/开了会怎样"。

此外，部分配置与其它功能模块存在**隐性联动**却没有在交互上体现，典型是 `api_gateway_credential_name` 实际引用了**凭证管理**中的凭证，却让用户手打凭证名。

## 2. 目标（成功标准）

1. **可配置**：裸 JSON / 裸下拉 → 领域感知的结构化表单控件；复杂项保留 JSON 源码兜底。
2. **可解释**：每项清楚表达"是什么、选/开之后影响什么"，支持 用途说明 + 每个选项含义 + 图文/GIF 位 + 文档链接。
3. **可验证**：连外部服务的配置（如 API 插件）可一键测试，成功回显拉取到的数据预览，失败回显具体错误。
4. **可扩展**：前端由后端元数据驱动；新增普通配置项只写后端声明，前端零改动。

### 非目标（本期不做）

- 不改系统管理页（`System/SpaceConfig`）与内部配置（`callback_hooks`，`is_public=False`）的渲染机制。
- 不改流程编辑内 control 配置（`get_control_config`）的既有交互（元数据增强对其无破坏）。
- 不做数据迁移脚本（改版为纯读写兼容）。
- 不生产 GIF/示意图素材（仅预留位 + 文字说明，素材后补）。

## 3. 选定方案

**方案 A：声明式配置 Schema + 双栏配置中心 + 通用验证能力。**

后端为每个配置补一套声明式元数据（分组 / 说明 / 控件描述 / 验证声明），通过 `config_meta` 下发；前端一个"配置中心"页按元数据自动渲染表单、说明与验证区；新增普通配置项只写后端声明。存储结构不变，旧值兼容，复杂项保留 JSON 源码兜底。

（备选方案 B「轻量元数据 + 保留表格弹窗」因无法很好承载复杂 JSON 的结构化被否；方案 C「逐项手写专用组件」因违背元数据驱动、维护成本高被否。）

## 4. 配置项分组

范围为空间管理页 11 个公开配置项，分 3 组：

| 分组 key | 组名 | 配置项 |
|---|---|---|
| `access_security` | 权限与安全 | `superusers`、`token_expiration`、`token_auto_renewal`、`api_gateway_credential_name` |
| `flow_canvas` | 流程与画布行为 | `flow_versioning`、`allow_multiple_triggers`、`gateway_expression`、`canvas_mode` |
| `api_integration` | API 与插件集成 | `uniform_api`、`space_plugin_config`、`engine_space_config` |

## 5. 后端设计

### 5.1 `BaseSpaceConfig` 声明式属性（全部可选、对现有逻辑零破坏）

在既有属性（`name / desc / value_type / default_value / choices / example / is_mix_type / is_public / control`）基础上新增：

- `group`：分组 key（`access_security` / `flow_canvas` / `api_integration`）。
- `help`：`{ "summary": 用途, "effect": 影响说明, "media": [{ "type": "image|gif", "src": url, "caption": str }], "doc_link": url }`。
- `ui`：控件描述（见 5.2），前端据此渲染。
- `verify()`：新增可选类方法，声明并实现"测试"能力，默认抛"不支持验证"。

`to_dict()` 一并输出上述字段；`SpaceConfigAdminViewSet.config_meta` 已返回全部配置的 `to_dict()`，前端由此获得渲染所需的全部元数据。

### 5.2 `ui` 控件描述结构

```jsonc
{
  "control": "switch | radio | select | input | number | url | string_list | member_selector | credential_map | api_plugin_config | plugin_scope | engine_kv | json",
  "label": "...",
  "help": "字段级说明",
  "required": true,
  "options": [{ "value": "boolrule", "label": "Boolrule（默认）", "desc": "选了会怎样…" }],   // radio/select
  "data_source": { "type": "credential", "credential_type": "BK_APP" },                     // 引用型控件
  "validation": { "type": "apigw_url" },                                                    // 校验规则
  "params": { }                                                                             // 复合控件参数
}
```

**设计取舍**：标量/简单项用通用控件（覆盖多数）；少数复杂项用具名**复合控件**（`credential_map`、`api_plugin_config`、`plugin_scope`、`engine_kv`），后端仍只声明"控件名 + 参数"，前端为每个复合控件配一个组件（很少新增）。这样"加普通配置项只写后端声明"仍然成立，复杂项也不失控。

### 5.3 通用验证接口

- 新增 `POST api/space/admin/space_config/verify/`，入参 `{ space_id, name, value, params }`，分发到对应配置的 `verify()`。
- 返回结构化结果：
  - 成功：`{ "ok": true, "preview": { ... } }`
  - 失败：`{ "ok": false, "error": { "message": str, "status_code": int?, "raw_snippet": str? } }`
- 关键点：验证用的是**表单当前填的值**（未保存也能测）。`uniform_api` 的 `verify()` 复用 `bkflow/pipeline_plugins/query/uniform_api` 的 `UniformAPIClient` meta/分类拉取逻辑；由于其需要凭证，`params` 带上待测的 `api_key` 与用于鉴权的凭证（默认取空间默认凭证）。
- 权限：`verify` action 沿用 `SpaceConfigAdminViewSet` 权限（`AdminPermission | SpaceSuperuserPermission`）。

## 6. 前端设计

### 6.1 页面形态：双栏 master-detail

替换现在的扁平表格 + 编辑弹窗。

- **左栏**：按 3 组分区（可折叠）+ 顶部搜索；每项带状态徽标（`已配置`=自定义值 / `默认`=用默认值 / 校验异常标红，如凭证悬空引用）。
- **右栏（选中项详情）**：
  1. `说明区`：`help.summary` + `help.effect` + 媒体位（GIF/图示）+ 文档链接。
  2. `表单区`：按 `ui.control` 渲染；`radio/select` 每个选项显示 label + desc。
  3. `验证区`：仅支持验证的配置出现；"测试"按钮 + 成功预览 / 失败报错。
  4. 底部：`恢复默认值` / `高级(JSON 源码)` / `取消` / `保存`。

### 6.2 控件注册表

`control 名 → 组件` 映射，新增控件类型只加一处：

| control | 组件 | 用于 |
|---|---|---|
| `switch` | 布尔开关 | `token_auto_renewal`、`allow_multiple_triggers`、`flow_versioning` |
| `radio` / `select` | 带 desc 的单选/下拉 | `canvas_mode`、`gateway_expression` |
| `input` / `number` / `url` | 带校验输入 | `token_expiration` 等 |
| `string_list` | 字符串列表编辑 | 通用 |
| `member_selector` | 复用 `frontend/src/components/common/Individualization/MemberSelect.vue` | `superusers` |
| `credential_map` | 默认 + 作用域覆盖 + 凭证联动 | `api_gateway_credential_name` |
| `api_plugin_config` | API 插件多 api_key 结构化编辑 + 实时预览 | `uniform_api` |
| `plugin_scope` | 白/黑名单 + 插件选择 | `space_plugin_config` |
| `engine_kv` | space / scope 两级键值编辑 | `engine_space_config` |
| `json` | Monaco 源码（兜底） | 任意复合项的高级模式 |

### 6.3 高级/JSON 源码兜底

复合控件右上角可切换"结构化 ↔ JSON 源码"（复用 `FullCodeEditor`），双向同步、校验后互转，为熟练用户提供逃生通道。

### 6.4 保存链路

结构化控件产出值 → 按 `value_type`/`is_mix_type` 落到 `text_value` 或 `json_value` → 复用现有 `updateSpaceConfig`（POST 新建 / PATCH 更新）、`deleteSpaceConfig`（恢复默认）、`getSpaceConfigData`、`getSpaceConfigMeta`（`frontend/src/store/modules/spaceConfig.js`）。接口无破坏性改动，仅新增 `verify`。

## 7. 凭证联动（`api_gateway_credential_name`，完整联动）

该配置本质是一张"按作用域选用哪个凭证"的路由表，存储为字符串（仅默认）或 `{ "default": 凭证名, "{scope_type}_{scope_value}": 凭证名 }`。引用的凭证来自凭证管理（`Credential`：`name/type/scope_level`，API 场景用 `BK_APP` 类型）。

`credential_map` 复合控件：

- **默认凭证**（必选）：下拉列出本空间 `BK_APP` 凭证（显示 名称 + 类型 + 描述 + 作用域级别），可搜索。
- **按作用域覆盖**（可选，可增删行）：每行 = [作用域选择器] + [凭证选择器]，对应存储的 `{scope_type}_{scope_value}: name`。
- **就近新建**：选择器带"+ 新建凭证"，就地打开凭证管理创建侧滑，建完自动回填。
- **跳转管理 / 查看**：已选凭证旁给"管理"链接跳凭证管理。
- **引用完整性**：加载时比对存储引用的凭证名与凭证列表（复用 `credentialConfig/loadCredentialList` → `api/space/admin/credential_config/`），缺失则该行标红提示"凭证不存在，请重选"，不自动清除。
- **作用域校验**：对 `scope_level=none` 或作用域不匹配的凭证做置灰/警告，避免选到"用不了"的凭证。
- **存储兼容**：无覆盖写字符串、有覆盖写 dict，`is_mix_type` 不变。

该"引用型控件（reference control）"抽象为通用能力：`data_source` 指向其它模块的列表接口，自带 搜索 / 就近新建 / 跳转管理 / 引用完整性校验，供将来其它引用型配置复用。

## 8. 各配置项目标形态

### 权限与安全

| 配置 | 控件 | 说明要点（summary / effect） | 验证 | 存储 |
|---|---|---|---|---|
| `superusers` 空间管理员 | `member_selector` | 拥有本空间全部管理权限的人；加入后可管理配置、凭证、全部流程/任务 | — | `json_value`（list） |
| `token_expiration` Token 过期时间 | `input`（时长校验） | 访问 Token 有效期；过期需重新获取，最短 1h；格式 `[n]m/[n]h/[n]d` | — | `text_value` |
| `token_auto_renewal` Token 自动续期 | `switch` | 开：临期自动延长，减少中断；关：到期即失效 | — | `text_value` `true/false` |
| `api_gateway_credential_name` 网关凭证 | `credential_map` | 默认凭证 + 按作用域覆盖，引用凭证管理 BK_APP 凭证（见 §7） | 可选：测所选凭证有效性 | `text_value` 或 `json_value`（`is_mix_type`） |

### 流程与画布行为

| 配置 | 控件 | 说明要点 | 验证 | 存储 |
|---|---|---|---|---|
| `flow_versioning` 流程版本控制 | `switch` | 开：保存产生版本、可回溯/回滚；关：只留最新 | — | `text_value` |
| `allow_multiple_triggers` 允许多触发器 | `switch` | 开：一个流程可挂多个触发器同时生效；关：仅一个 | — | `text_value` |
| `gateway_expression` 网关表达式 | `radio`（带 desc） | `boolrule` 默认·简单布尔规则、可视化友好 / `FEEL` DMN 标准、功能强 / `MAKO` Python 模板、最灵活但需谨慎；影响分支网关条件书写与求值 | — | `text_value` |
| `canvas_mode` 画布模式 | `radio`（带 desc + GIF 位） | `horizontal` 横向从左到右 / `vertical` 纵向从上到下；影响画布默认排布 | — | `text_value` |

### API 与插件集成

| 配置 | 控件 | 说明要点 | 验证 | 存储 |
|---|---|---|---|---|
| `uniform_api` API 插件 | `api_plugin_config` | 按 api_key 结构化：`display_name` / `meta_apis`(apigw URL) / `api_categories`(apigw URL，可选) / `headers`(键值) + common 开关；改动可能影响已用数据（提示谨慎） | 实时预览：拉 meta/分类，回显数量+样例或报错 | `json_value` |
| `space_plugin_config` 空间插件 | `plugin_scope` | `mode`：allow_list 只允许所列 / deny_list 屏蔽所列 + `plugin_codes` 插件多选 | — | `json_value` |
| `engine_space_config` 引擎模块配置 | `engine_kv` | 两级键值：`space`（空间级）+ `scope`（按作用域）；高级项，影响引擎运行参数 | — | REF |

媒体位（GIF/图示）本期预留占位 + 写好文字说明；`canvas_mode`、`gateway_expression` 最该补图，素材后补。

## 9. 兼容性（无需数据迁移）

- 存储结构（`text_value`/`json_value`/REF）完全不变，旧值照常读。
- `api_gateway_credential_name`：旧字符串值被 `credential_map` 识别为"仅默认凭证"，有覆盖时才写回 dict。
- `uniform_api`：读值时用现有 `UniformAPIConfigHandler` 把旧 V1（顶层 `meta_apis`）归一化为 V2 展示，保存写 V2；**无法结构化解析的值自动落到 JSON 源码模式**，不卡死用户。

## 10. 权限与安全

- 沿用 `SpaceConfigAdminViewSet` 权限（`AdminPermission | SpaceSuperuserPermission`），`verify` 同级。
- 只下发引用名与展示信息，**凭证明文内容不下发**；保留 `check_space_config` 的 superuser 可见性判断。

## 11. 错误处理

- 前端控件即时校验（必填 / 格式 / apigw 域名），后端 `SpaceConfigHandler.validate` 为最终防线，保存失败回显 `detail`。
- 验证接口失败：结构化 `error`（message + status_code + raw_snippet）在验证区展示；采用**"警告不阻断保存"**——外部可用性可能临时波动，不拦住存配置。
- `credential_map` 悬空引用：标红 + 允许重选，不自动清除。

## 12. 测试策略（TDD）

- **后端 pytest**：各 config `to_dict()` 含新字段；`verify()` 分发与 `uniform_api` 验证成功/失败（mock `UniformAPIClient`）；旧值读写兼容；`verify` 接口权限。
- **前端**：控件注册表渲染各 control；`credential_map` 悬空引用；`api_plugin_config` 旧值归一化 + 源码互转；验证结果展示。

## 13. 分期交付

- **P1**：后端元数据框架（`group/help/ui/verify` + `config_meta` 下发 + `verify` 接口）+ 前端双栏骨架 + 通用控件（switch/radio/select/input/number/url/string_list/member_selector）→ 覆盖 8 个简单项。
- **P2**：复合控件 `credential_map`（凭证完整联动）+ `api_plugin_config`（实时预览）。
- **P3**：`plugin_scope`、`engine_kv`、JSON 源码兜底、媒体位补图。

## 14. 涉及的主要文件（参考）

- 后端：`bkflow/space/configs.py`（元数据声明 + `verify`）、`bkflow/space/views.py`（`SpaceConfigAdminViewSet.verify`）、`bkflow/space/serializers.py`、`bkflow/pipeline_plugins/query/uniform_api/`（复用 `UniformAPIClient`）。
- 前端：`frontend/src/views/admin/Space/SpaceConfig/`（配置中心页 + 控件）、`frontend/src/store/modules/spaceConfig.js`（新增 `verify` action）、复用 `MemberSelect.vue` 与 `credentialConfig` store。
