# BKFlow Code Review Standards

> 基于项目历史 PR 评论提炼的 code review 标准，供 AI reviewer 遵循。

---

## 一、Python 后端

### 1. 代码结构与职责分离

- **Serializer 承担校验与转换**：请求参数的合法性校验、类型转换、字段归一化必须放在 Serializer 的 `validate_*` / `validate` 方法里，不能散落在 View 或 Model 方法中。
  - 反例：在 View 里直接操作 `request.data` 做 if/else 校验。
- **View 只做调度**：ViewSet 中不应出现业务逻辑；复杂逻辑提取到 Service 层或 Model 方法。
- **数据处理器统一入口**：对同一类数据的消费（如 uniform_api_config 的多版本兼容），不应在各消费点分散写 `if` 分支，应封装成统一的 Handler/Processor 类处理。
  - 示例：`uniform_api_config_data = UniformAPIConfigHandler(data=config).handle()`

### 2. 魔法数字与常量

- 代码中所有硬编码的数字、字符串（如长度限制 `32`、权限状态 `"authorized"`、列表名 `"white_list"`、定时表达式 `"*/10 * * * *"`）必须抽取为模块级或类级**命名常量**。
- 常量命名风格：`UPPER_SNAKE_CASE`，统一放在 `constants.py`。
- 版本标识常量：使用 `SCHEMA_V1` / `SCHEMA_V2` 而非 `SCHEMA` / `SCHEMA_V1`，保证命名可比较。

### 3. ORM 查询

- **避免 N+1**：循环内不能出现 ORM 查询；改用 `filter()` 批量查询 + `bulk_create()` / `bulk_update()`。
  - **例外**：低频定时任务（如 nightly batch job）中使用 `update_or_create` 保证幂等性是合理的，数据量小（< 1000 条）时无需强制改为 bulk 操作。
- **减少冗余查询**：同一次请求中对同一数据集的查询合并为一次，避免重复 `.filter()`。
- 查询结果只需要特定字段时，使用 `.values()` 或 `.values_list()` 降低内存开销。
- 排序须显式指定（`order_by(...)`），不依赖模型的默认 `Meta.ordering`，防止行为随模型变更而变化。

### 4. API / ViewSet 设计

- REST 语义：查询用 `GET`，创建用 `POST`，**增量更新用 `PATCH`**（不要用 `PUT` 传全量字段），删除用 `DELETE`。
- ViewSet 里的 `extra_actions`（如 `MOCK_ABOVE_ACTIONS`）只在该 ViewSet 确实声明了对应 action 时才添加，否则是无效配置。
- 分页器复用项目公共分页器，不要在每个 View 里自己写分页逻辑。
- 路由路径命名遵循项目约定（如 scope 路径：`{scope_type}_{scope_id}`），不能随意创造新格式。

### 5. 权限与安全

- **权限校验放在类级别**：`permission_classes` 优先在 ViewSet 类属性中声明，不在方法内临时判断。
- **过滤与鉴权使用同一 scope**：View 中过滤数据集所用的 `space_id` / `scope` 必须与鉴权时使用的一致，防止权限泄露。
  - **注意区分接口类型**：内部管理接口（admin portal / 模块间调用）使用 `AdminPermission | AppInternalPermission` 即可，不需要额外添加 `ScopePermission`。只有面向外部消费方/终端用户的接口才需要配置 `ScopePermission` / `TemplatePermission`。参考 `.ai/rules/bkflow-permission.mdc` 中的决策指南。
- **敏感字段脱敏日志**：打印 headers 或 data 时，`X-Bkapi-Authorization`、`bk_app_secret` 等敏感字段必须替换为 `"******"`，使用 `copy.deepcopy` 复制后再替换，不污染原始对象。

### 6. 异步任务（Celery）

- **集中配置**：新版 Celery 不提倡 `@task` 装饰器内嵌配置，使用集中的 `CELERY_BEAT_SCHEDULE` 配置定时任务。
- **Crontab 读环境变量**：定时周期通过 `env.py` 的环境变量注入，如 `crontab(env.SYNC_INTERVAL)`，便于运维调整，不硬编码。
- **异步任务多打日志**：任务开始、关键步骤、异常、完成均需有日志，方便问题排查。日志使用英文，格式清晰（如 `"get context values error: {e}"`）。
- 任务完成后打清理/操作结果日志（如删除了多少条记录）。

### 7. 错误处理与日志

- 日志信息加前缀上下文，例如 `"get context values error: {e}"`，而非只打 `str(e)`。
- 异常类命名需准确体现业务含义，不用含糊缩写（如 `BKPluginUnAuthorized` 而非 `BKPluginUnAu...`）。
- 清理/批量操作日志全部使用英文，保持一致性。
- **注意**：此处"日志"特指 `logging` 模块输出的运行时日志，不包括面向用户的 `ValidationError` 消息。`ValidationError` 消息遵循编码规范"中文描述为主"，或使用 `ugettext_lazy` 做国际化。

### 8. 代码整洁

- 注释只在逻辑不自明时保留，`# 已解决`、`# TODO（过时）`、调试遗留注释须清理。
- 无用变量、冗余赋值（如 `pop` 掉的 key 不记录）需标注或删除。
- `watch` 选项（Vue/前端同理）：无需 `deep`/`immediate` 时，直接写函数形式，不用 `{ handler }` 对象语法。

### 9. 模型与迁移

- 新增 Model 字段必须附带对应的 `migrations` 文件，不能缺失。
- 每个新增 Python 文件顶部须包含开源协议声明（`# -*- coding: utf-8 -*-` 及版权注释）。

### 10. 文档同步

- API 变更（新接口、协议修改、权限字段含义）必须同步更新对应的文档（`docs/` 或 `apigw/docs/zh/`）。
- 权限表中每个权限级别（VIEW / EDIT / MOCK / OPERATE）需有明确的业务描述，不能只列名称。
- 鼓励使用 AI 根据分支改动自动生成或更新文档。

---

## 二、前端（Vue）

### 1. Vue watch 写法

- 无需 `deep` / `immediate` 配置时，直接写函数：
  ```js
  // 推荐
  watch: { theExecuteTime(val) { ... } }
  // 不推荐
  watch: { theExecuteTime: { handler(val) { ... } } }
  ```

### 2. 图标使用

- 同类场景的图标保持统一，不做不必要的条件分支。例如跳转图标统一使用 `common-icon-jump-link`，不根据状态切换不同图标类名。

---

## 三、API 文档

- `apigw/docs/zh/` 下的 Markdown 文档须与实际接口保持一致。
- 权限相关字段需包含详细说明，例如：
  > VIEW：作用域下任务和流程的查看权限；EDIT：流程编辑权限；MOCK：流程编辑和调试权限；OPERATE：作用域下任务的操作权限。
- Webhook 类新接口需同步在文档中补充请求/响应示例。

---

## 四、部署架构注意事项

审查时需理解 BKFlow 的多模块部署架构，避免误报：

- BKFlow 按 `BKFLOW_MODULE_TYPE` 环境变量拆分为多个模块（`engine`、`interface`、`pipeline` 等），每个模块只加载对应的 Django apps。
- `module_settings.py` 中通过 `MODULE_APPS` 字典和 `BKFLOW_MODULE_TYPE` 控制 `INSTALLED_APPS`，某些 app（如 `bkflow.statistics`）仅在特定模块类型下才被加载。
- 如果一段代码只在特定模块下加载的 app 中运行，则不需要考虑该代码在其他模块下的行为（因为根本不会执行）。
- **单模块部署**（`BKFLOW_MODULE_TYPE == ""`）有独立的 app 列表，不一定包含所有 app。

## 五、通用原则

| 维度 | 要求 |
|------|------|
| **可读性** | 变量/函数/常量命名准确反映含义；索引访问 `instance[0]` 改用具名 dict |
| **单一职责** | 函数只做一件事；`is_valid()` 只做校验不做转换 |
| **批量操作** | 循环内的单条 DB 操作必须改为批量 |
| **配置化** | 所有阈值（超时、并发数、清理周期、实例数）通过环境变量注入，不硬编码 |
| **安全** | 敏感字段脱敏；权限校验完整且与鉴权 scope 一致 |
| **向后兼容** | 协议版本变更需同时兼容旧格式，消费点统一通过 Handler 处理多版本 |
| **文档** | 接口变更必须同步文档；新增文件包含开源协议头 |

---

## 六、Review 严重级别判断标准

### Critical（必须修复）

- 权限泄露（鉴权 scope 与过滤 scope 不一致）——仅针对面向外部消费方的接口
- 敏感信息明文写入日志
- 缺少迁移文件但新增了 Model 字段
- N+1 查询在高频 API 接口上

### Important（应当修复）

- 魔法数字未抽常量（影响维护性）
- 校验逻辑散落在 View 而非 Serializer
- 缺少关键操作日志（异步任务）
- API 文档未同步（对接方会依赖）
- 高频接口中循环内单条 DB 操作未使用 `bulk_create` / `bulk_update`

### Minor（建议优化）

- Vue watch 使用 handler 对象语法
- 图标类名条件分支可简化
- 注释冗余或过时
- 函数可用 lambda 简化
- 日志信息缺乏上下文前缀
- 低频批量任务中的 `update_or_create` 循环（数据量可控时无需强制优化）
