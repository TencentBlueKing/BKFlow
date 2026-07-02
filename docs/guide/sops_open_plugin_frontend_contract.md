# 标准运维开放插件前后端对接协议

## 场景范围

本协议只覆盖以下三组页面的前端消费需求：

- 空间开放插件管理页
- 模板编辑中的插件选择与版本展示页
- 任务页中的插件异常提示页

这份文档只保留前端必需字段、状态和展示规则，不重复后端主 spec 中的完整协议设计。

## 页面到接口映射

### 1. 空间开放插件管理页

前端至少依赖以下能力：

- 空间开放插件列表接口  
  用于获取当前空间下的来源、插件、开启状态、目录可用状态、最近同步时间
- 单个插件开关接口  
  用于切换 `enabled`
- 当前可见插件一键全开接口  
  用于对当前已发现插件执行批量开启
- 按来源批量关闭接口  
  作为增强态的来源级 kill switch

### 2. 模板编辑插件选择与版本展示页

前端至少依赖以下能力：

- `list_plugins`  
  用于展示开放插件来源、来源别名、插件类型和列表项
- `get_plugin_schema`  
  用于按 `plugin_id + plugin_version` 获取当前版本 schema
- 模板保存接口  
  用于保存节点当前绑定的插件引用和版本

### 3. 任务页异常提示

前端至少依赖以下能力：

- 创建任务 / 启动任务接口  
  用于得到任务运行结果或异常状态
- 任务详情接口  
  用于获取任务当前异常说明、插件快照和建议动作提示所需字段

## 核心展示实体

### 1. 开放插件来源

前端只关心以下最小字段：

- `source_key`
- `display_name`
- `status`
- `last_sync_at`
- `plugin_total`
- `enabled_plugin_total`

### 2. 开放插件

前端最小字段：

- `plugin_id`
- `plugin_code`
- `plugin_source`
- `display_name`
- `plugin_type`
- `enabled`
- `availability_status`
- `default_version`
- `latest_version`
- `last_sync_at`

### 3. 插件版本

前端最小字段：

- `plugin_version`
- `status`
- `version_note`
- `is_default`
- `is_latest`

### 4. 任务异常信息

前端最小字段：

- `error_type`
- `error_title`
- `error_message`
- `plugin_id`
- `plugin_source`
- `plugin_version`
- `template_id`
- `space_id`
- `suggested_actions`
- `is_history_snapshot`

## 页面字段清单

### 空间开放插件管理页

表格建议至少消费：

- `display_name`
- `source_display_name`
- `plugin_type`
- `enabled`
- `availability_status`
- `default_version`
- `latest_version`
- `last_sync_at`

### 模板编辑页

插件选择和摘要区至少消费：

- `plugin_id`
- `plugin_source`
- `plugin_code`
- `display_name`
- `plugin_type`
- `plugin_version`
- `default_version`
- `latest_version`
- `availability_status`

参数区至少消费：

- `inputs`
- `schema_protocol_version`

### 任务异常页

错误卡片至少消费：

- `error_type`
- `error_title`
- `error_message`
- `plugin_source`
- `plugin_id`
- `plugin_version`
- `impact_scope`
- `suggested_actions`
- `is_history_snapshot`

## 状态枚举

建议前端统一按以下状态命名消费：

### 插件开放状态

- `enabled`
- `disabled`

### 插件可用状态

- `available`
- `unavailable`

### 来源状态

- `ready`
- `sync_failed`
- `temporarily_unreachable`

### 任务异常类型

- `plugin_not_enabled`
- `plugin_version_unavailable`
- `plugin_removed`
- `source_unreachable`

如果后端需要扩展更多错误类型，应优先在 `error_type` 层扩展，而不是让前端自行解析错误文本。

## 展示规则

### 空间开放插件管理页

- `enabled=false` 时默认展示为未开启，可执行单个开启动作
- `availability_status=unavailable` 时，展示为历史记录或不可用记录，不允许继续开启
- 来源异常时，应保留列表，但页面顶部给出来源异常提示

### 模板编辑页

- `plugin_version` 始终显式展示
- 当 `availability_status=available` 时允许正常编辑和保存
- 当版本不可用但存在历史快照时，允许回看，但页面需提示不能继续新用
- 仅当后端返回可选新版本时，前端才展示“切换到可用版本”的引导

### 任务异常页

- `error_type` 决定错误卡片标题、说明和建议动作
- 任务页默认不提供原地修复能力
- `is_history_snapshot=true` 时，页面需补充“当前展示的是历史快照，不代表该版本仍可新建任务”的说明

## 错误态与建议动作映射

| error_type | 页面标题建议 | 建议动作 |
| --- | --- | --- |
| `plugin_not_enabled` | 插件未在当前空间开放 | 去空间开放插件管理页检查插件状态 |
| `plugin_version_unavailable` | 插件版本不可用 | 返回模板切换到可用版本 |
| `plugin_removed` | 插件已从来源目录下线 | 联系管理员或维护人确认替代方案 |
| `source_unreachable` | 插件来源暂时不可达 | 稍后重试，或联系管理员检查来源状态 |

前端不需要自己生成复杂动作逻辑，但应保证不同错误类型下的按钮文案和引导方向一致。

## 跳转与回退规则

建议页面按以下规则组织跳转：

- 空间管理页 ←→ 模板编辑页  
  不直接强耦合，主要通过“建议动作”或上下文提示关联
- 模板编辑页 → 任务页  
  正常启动后统一进入任务页
- 任务页 → 模板编辑页  
  仅通过“回模板切换版本”这类引导动作返回
- 任务页 → 空间开放插件管理页  
  仅在错误类型与空间治理有关时引导跳转

回退规则上，前端不承担数据恢复逻辑，只负责把用户带回合适的配置入口。

## 增强态预留字段

为后续增强态预留的字段建议集中在以下几类：

- `version_diff_summary`  
  用于展示版本切换时的高层差异说明
- `source_status_detail`  
  用于解释来源异常的更细粒度原因
- `action_target`  
  用于更明确地指导按钮跳向模板页、空间页或其他位置
- `history_snapshot_note`  
  用于细化历史任务的只读说明

这些字段在一期可以为空或缺省，前端不应把它们作为 MVP 的强依赖。
