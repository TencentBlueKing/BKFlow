# 02 Django 模型与接口清单

[返回总览](2026-10-30-space-plugin-catalog-v2-review-design.md) · [后台任务与迁移](2026-10-30-space-plugin-catalog-v2-jobs-migration.md)

## 拟新增 9 个 Django model

均放在 bkflow/plugin_catalog/models.py，归 Interface。以下是现有 spec 已列出的模型和主要字段，不是已生成的 DDL。空间唯一性、跨对象归属及最终索引在实现时核对。

| 模型 | 每条记录代表什么 | 主要字段 / 关系 |
| --- | --- | --- |
| SpaceCatalogConfig | 一个空间的管理配置 | space_id 唯一；policy、policy_revision、directory_revision、revision、initialization_status |
| PluginInventory | 一个空间中的一个插件身份 | 唯一(space_id, plugin_key)；kind、source_key、来源 ID、name/code、来源分类、版本摘要、source_valid、失效原因 |
| SpacePluginSetting | 一个插件的人工管理设置 | 关联 inventory；management_state、ever_enabled、directory、pending_target、recommended、停用原因、替换对象 |
| PluginDirectory | 一个目录 | space_id、parent_id、name、order、system；最多两级，根/子目录都检查同级名称唯一 |
| TemplatePluginReference | 当前流程内容中的一个引用节点 | space_id、template_id、role、snapshot_id、content_digest、plugin_key、node_path/name、plugin_version |
| UnresolvedApiReference | 一个无法识别身份的老 API 节点 | 流程、role、snapshot、node_path、reason；不伪造 plugin_key，不混入插件统计 |
| CatalogInitialization | 一次空间初始化记录 | space_id、batch、旧配置快照、校验摘要、进度与错误；用于失败重跑和核对 |
| SourceSyncState | 一份来源/请求范围的同步状态 | space_id、source_key、request_scope、config_revision、generation、故障轮次、attempts、next_run、last_error |
| CatalogChangeRecord | 一次目录或管理变更 | space_id、object_key、actor、action、before/after、method/reason、request_id；用于追查分类来源 |

**关系：** Space → 空间配置 / 插件清单 / 目录；PluginInventory → 管理设置；管理设置 → 当前目录与审核目标；引用记录 → 流程快照及插件身份。源端是否有效与管理决定分别保存，推荐独立于失效状态。

**保留的旧数据：** OpenPluginCatalogIndex 继续承担 V4 来源版本信息；SpaceOpenPluginAvailability 的旧管理值用于迁移/兼容，已初始化空间不得双写成两套管理依据。Space、Template、TemplateSnapshot、TaskInstance 继续复用。

**需技术评审：** SpaceCatalogConfig 与 CatalogInitialization 都含初始化进度，尚需明确哪一处是判断就绪的权威值；9 个是当前模型方案数量，不能当作最终建表验收数。不增加 LegacyScopeVisibility 表或独立 AI 审核模型。

## 新增 13 个 HTTP 操作，11 条路径

统一前缀：`/api/plugin_catalog/spaces/{space_id}/`。GET 参数在 query，POST/PUT 参数在 JSON body。下列是参数草案，名称和嵌套方式未由 serializer 固化；关键必填用“必”标注，其他筛选可选。身份、租户和操作者从服务端认证上下文取得。

| 编号 / 方法与路径 | 大概传什么 | 主要返回 |
| --- | --- | --- |
| A01 GET plugins/ | state、directory_id、kind、source_key、query、sort_by、direction、offset、limit | rows、total、Tab 数量、effective_state、allowed_actions、推荐和当前引用数 |
| A02 POST statuses/ | 必 plugin_keys:string[] | 各插件状态、来源原因、停用原因、替换建议；仅授权存量场景使用 |
| A03 GET directories/ | 无业务 body；space_id 在路径 | DirectoryDocument、revision |
| A04 PUT directories/ | 必 document:DirectoryDocument、expected_revision:int | 保存后的目录与 revision；冲突明确返回 |
| A05 POST directories/preview/ | 必 document、changes:操作数组 | 删除/移动后的目录、归属与冲突预览；不写正式数据 |
| A06 GET policy/ | 无业务 body | PolicyDocument、policy_revision |
| A07 PUT policy/ | 必 policy:PolicyDocument、expected_revision:int | 保存后的策略及修订号 |
| A08 POST management/ | 必 action、items[]、expected_revision；每项含 plugin_key，按动作带 target_directory、reason、replacement_key | 更新结果与 revision；action 枚举拼写待统一 |
| A09 POST recommendation/ | 必 plugin_keys:string[]、recommended:bool、expected_revision:int | occupied、remaining、revision；超限整批拒绝 |
| A10 GET references/ | 必 plugin_key；query、role(all/published/draft_only)、offset、limit | overview、rows、total、readiness；节点保留版本归属 |
| A11 GET references/export/ | 必 plugin_key；query、role；不传分页限制 | 当前搜索/筛选的全部 CSV 结果 |
| A12 GET unresolved-api/ | 空间由路径取得；流程筛选与分页参数**待定** | 无法识别的流程、快照、节点及原因 |
| A13 POST ai/classify/ | 必 document、selected_keys:string[]、ai_scope、request_id；prompt | patch / empty / error；人工调用不保存正式目录 |

**统计方式：** directories/ 和 policy/ 各有 GET、PUT 两个操作，其余路径各一个；12 个基础管理操作＋1 个 AI 操作＝13。使用侧列表、流程保存和对外网关沿用旧路径改行为，不在这里再造接口。

### 两种主要请求对象

| 对象 | 组成 | 需要保留的约束 |
| --- | --- | --- |
| DirectoryDocument | revision；directories:{id → parent_id/name/order/system}；assignments:{plugin_key → directory_id}；pending_targets:{plugin_key → directory_id} | 编辑副本含完整目录与归属；不接收启停/推荐字段；目录修订号独立 |
| PolicyDocument | revision、mode、groups、classification、ai_scope | 三策略、来源组互斥、分类方式、AI 增量/自由范围；只影响后续发现插件 |

字段标必是本轮接口草案的技术建议；空选中范围代表“全部”还是非法请求、分页默认值、单次批量上限、action 的完整枚举及 A12 筛选参数尚未在原 plan 定义，**不在本轮补成产品规则**。revision 冲突按原 plan 返回 409；项目业务错误码仍按现有方式注册。

## 现有接口改造与内部 HTTP

| 现有入口 | 现有关键输入 | 本次改动 / 回归重点 |
| --- | --- | --- |
| list_plugins / get_plugin_schema，以及画布列表/详情 | space_id、既有插件类型、来源和查询字段 | 列表只返回已启用且有效项；详情/版本保留存量访问；旧包络兼容 |
| update_template 及画布保存 | 流程标识、pipeline_tree、既有版本/范围字段 | 服务端重建 ID 前检查新增节点；返回具体 node_path 与原因 |
| create/release/rollback/delete 等流程入口 | 各入口现有参数 | 最终写入事务更新当前引用；保留整流程创建/回滚例外 |
| 旧 V4 list/toggle/enable_all/disable_source | 原调用包络 | 委托新管理服务，兼容原调用，不保留第二套人工管理数据 |
| create_space / renew_space_config | 原空间配置参数 | 新空间初始化；已初始化空间拒绝继续写旧插件配置 |
| POST api/plugin/internal/build_open_plugin_snapshots/ | space_id、pipeline_tree、username、scope_type、scope_value、mode(prepare/backfill)、可选的两种已有 snapshot | 返回 reference_snapshot、schema_snapshot、changed；校验含义调整，保持运行版本证据 |
| POST api/plugin/internal/validate_open_plugins_for_start/ | space_id；snapshot 或 pipeline_tree | 返回 validated 或错误；不能因管理停用/同步超时再次阻断存量运行 |
| POST api/template/internal/prepare_task_extra_info/ | space_id、pipeline_tree、extra_info、username、scope_type、scope_id | 返回 extra_info，回归 Engine 发起的子任务准备链路；注意此处是 scope_id，上一入口是 scope_value |

以上三个内部 HTTP 入口已存在，**新增 Engine 内部接口为 0**。保存/创建/启动/调试的 purpose 如何由各入口传给共用校验服务，需要在实现中统一；不要求调用方提交一个可绕过权限的自由参数。
