# 02 Django 模型与接口清单

[返回总览](2026-10-30-space-plugin-catalog-v2-review-design.md) · [后台任务与迁移](2026-10-30-space-plugin-catalog-v2-jobs-migration.md)

## Django model：4 新增＋3 复用/扩展

用户已确认收敛方向。4 个新模型放在 Interface 的 plugin_catalog 模块；两张旧插件表扩展字段，SpaceConfig 复用现有 JSON 存储，不再复制出第二套清单和管理设置。最终字段/唯一键与兼容迁移仍需按 E01/E02 核定。

| 落地对象 | 新增 / 复用 | 主要内容与约束 |
| --- | --- | --- |
| SpaceConfig | **复用现有表**，替代 SpaceCatalogConfig | 内部专用配置保存 policy、policy_revision、directory_revision、管理 revision、初始化状态/最近进度/错误；沿用 (space_id,name) 唯一。内部键名和 JSON schema 待确认 E02 |
| OpenPluginCatalogIndex | **扩展现有表**，替代 PluginInventory | 全类型插件身份、来源元信息、版本摘要、来源有效性和原因；补类型、唯一键及观测代次。旧 V4 消费者需限定类型/来源，唯一键迁移见 E01 |
| SpaceOpenPluginAvailability | **扩展现有表**，替代 SpacePluginSetting | management_state、ever_enabled、目录、审核目标、recommended、停用原因/替换对象、归类方式。enabled 只作兼容表达，不能成为另一份管理决定；具体写入方式见 E01 |
| PluginDirectory | **新增 1** | 空间、父目录、名称、兄弟顺序、系统标记；最多两级、根/子同级唯一、系统未分类受保护；不复用流程/任务 Label |
| TemplatePluginReference | **新增 1**，吸收 UnresolvedApiReference | 当前流程角色、snapshot、内容摘要、节点路径/名称/版本；增加解析状态/原因。未识别节点身份为空，不伪造 plugin_key；引用统计仅包含已解析记录，旧 API 仍独立展示 |
| SourceSyncState | **新增 1** | 来源及实际请求范围、配置/采集代次、故障轮次、重试次数、下次时间、错误；持久化有限重试与过期结果判断，不以缓存锁或队列消息代替 |
| CatalogChangeRecord | **新增 1**，继承 BaseOperateRecord | 复用操作人、动作、来源、时间、extra_info 等基础结构；补空间、对象、前后值、method/reason/request_id。保存初始化所需旧管理配置快照和执行结果；不新增审计页面 |

初始化状态并入 SpaceConfig，初始化旧管理配置快照与结果并入 CatalogChangeRecord；不再新增 CatalogInitialization。未识别 API 合并存储但继续独立展示，不混入引用计数。来源信息与人工决定仍分别保存，来源同步不能覆盖人工决定。

BaseOperateRecord 是抽象基类，继承仍新增一张表。现有 Label 与目录语义不同；TemplateNodeStatistics 异步且可跨库，不能代替与流程同事务更新的当前引用表。

## 新增 11 个 HTTP 操作，9 条路径

统一前缀：`/api/plugin_catalog/spaces/{space_id}/`。GET 参数在 query，POST/PUT 参数在 JSON body。下列是参数草案，名称和嵌套方式未由 serializer 固化；关键必填用“必”标注，其他筛选可选。身份、租户和操作者从服务端认证上下文取得。

| 编号 / 方法与路径 | 大概传什么 | 主要返回 |
| --- | --- | --- |
| A01 GET plugins/ | state、directory_id、kind、source_key、query、sort_by、direction、offset、limit | rows、total、Tab 数量、effective_state、allowed_actions、推荐和当前引用数 |
| A02 POST statuses/ | plugin_keys:string[]＋获授权的存量流程/任务上下文；上下文字段待确认 E03 | 各插件状态、来源原因、停用原因、替换建议；仅授权存量场景使用 |
| A03 GET directories/ | 无业务 body；space_id 在路径 | DirectoryDocument、revision |
| A04 PUT directories/ | 必 document:DirectoryDocument、expected_revision:int | 保存后的目录与 revision；冲突明确返回 |
| A05 POST directories/preview/ | 必 document、changes:操作数组 | 删除/移动后的目录、归属与冲突预览；不写正式数据 |
| A06 GET policy/ | 无业务 body | PolicyDocument、policy_revision |
| A07 PUT policy/ | 必 policy:PolicyDocument、expected_revision:int | 保存后的策略及修订号 |
| A08 POST management/ | 必 action、items[]、expected_revision；每项含 plugin_key，按动作带 target_directory、reason、replacement_key；推荐动作带 recommended:bool | 更新结果与 revision；推荐返回 occupied/remaining，超限整批拒绝；action 枚举待 E07 |
| A09 GET references/ | 必 plugin_key；format=json/csv；query、role(all/published/draft_only)；JSON 另有 offset、limit | JSON 返回 overview/rows/total/readiness；CSV 返回全部匹配结果，不按分页截断；两者同权限和筛选 |
| A10 GET unresolved-api/ | 空间由路径取得；流程筛选与分页参数**待定** | 无法识别的流程、快照、节点及原因 |
| A11 POST ai/classify/ | 必 document、selected_keys:string[]、ai_scope、request_id；prompt | patch / empty / error；人工调用不保存正式目录 |

**统计方式：** directories/ 和 policy/ 各有 GET、PUT 两个操作，其余路径各一个；10 个基础操作＋1 个 AI 操作＝11。使用侧列表、流程保存和对外网关沿用旧路径改行为，不在这里再造接口。statuses 属于使用侧查询，其余管理能力按管理员权限；不能共用一个过宽或过严的 permission。

### 两种主要请求对象

| 对象 | 组成 | 需要保留的约束 |
| --- | --- | --- |
| DirectoryDocument | revision；directories:{id → parent_id/name/order/system}；assignments:{plugin_key → directory_id}；pending_targets:{plugin_key → directory_id} | 编辑副本含完整目录与归属；不接收启停/推荐字段；目录修订号独立 |
| PolicyDocument | revision、mode、groups、classification、ai_scope | 三策略、来源组互斥、分类方式、AI 增量/自由范围；只影响后续发现插件 |

字段标必是本轮接口草案的技术建议；空选中范围代表“全部”还是非法请求、分页默认值、单次批量上限、action 的完整枚举及 A10 筛选参数尚未在原 plan 定义，**不在本轮补成产品规则**。revision 冲突按原 plan 返回 409；项目业务错误码仍按现有方式注册。

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


## 权限矩阵

所有入口先确定租户和空间，再执行对应权限；“允许”均仅限已授权范围。内部 Token、空间 Token、网页登录身份不能互相代替。

| 能力 / 调用者 | 平台管理员、当前空间管理员 | 编排者 / 空间 Token | 内部模块身份 | 必须执行的校验 |
| --- | --- | --- | --- | --- |
| 管理列表、目录读写/预览、策略、启停/推荐、人工 AI | 按现有管理员规则允许 | 不能仅凭编排/Token 权限执行管理动作 | 不因内部 Token 自动获得管理权限 | 租户/空间、全部批量对象、目标目录及替换对象均属本空间 |
| 引用 JSON/CSV、未识别 API 诊断 | 按管理查询权限允许 | 不新增普通用户管理查询授权 | 不开放新的内部管理入口 | JSON 与 CSV 共用范围校验；未识别记录不计入插件统计 |
| 现有可选列表 / schema / detail | 沿用已有授权 | 沿用现有授权组合和 scope 限制 | 仅沿用已有内部能力 | 列表要求 enabled＋valid；存量详情独立，不从列表有无推断权限 |
| 新 statuses 批量状态查询 | 可查本空间授权对象 | 仅限获授权的存量流程/任务上下文；字段与 token scope 待确认 E03 | 不直接暴露为 Engine 管理接口 | 不允许仅凭任意 plugin_keys 枚举不可选插件；管理与使用侧 serializer/permission 分开 |
| 保存流程 / 发起任务 | 沿用对应流程/任务权限 | 沿用对应流程/任务权限 | 各内部调用沿用已有认证 | 新增节点校验不替代流程权限；客户端不能传 purpose 跳过服务端规则 |
| 既有快照准备 / 启动预检 / 子任务 extra_info | 网页身份不是调用凭证 | 空间 Token 不是内部调用凭证 | 既有内部 Token 与空间/租户上下文 | Engine 不查目录 ORM；具体版本/来源授权仍检查 |
| 同步 / 自动 AI / 初始化 | 由受控后台或运维入口执行 | 不新增面向编排者的触发入口 | 任务只接收已校验的身份和范围 | 执行时重读配置/代次；不携带浏览器凭证或任意跨空间对象 |

复用 SpaceConfig 时，is_public=False 仅影响部分配置展示，不能视为写入隔离。现有配置 CRUD、批量应用、create_space/renew_space_config 需要对内部键拒绝直接覆盖；已初始化空间的旧插件配置继续只读。具体内部键见 E02，拒绝边界已经确定。

工程待确认项统一见 [04 实施与验收](../plans/2026-10-30-space-plugin-catalog-v2-team-plan.md)，调用先后见 [05 调用时序](2026-10-30-space-plugin-catalog-v2-interactions-design.md)。
