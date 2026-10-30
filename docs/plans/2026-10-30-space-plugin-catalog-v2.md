# 空间插件管理 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task, according to the execution method selected by the user. Steps use checkbox (`- [ ]`) syntax for tracking. 本文件供实现前评审；本轮没有执行代码、测试或迁移。

**Goal:** 在所有空间默认提供全类型插件目录、审核、启停、推荐和当前引用，统一管理页、画布及网关行为，并保留存量流程的访问和运行边界。

**Architecture:** 在 Interface 新增 `bkflow.plugin_catalog`，复用现有来源查询、租户鉴权与运行快照，不新建服务。来源有效性与管理员决定分别保存；目录、策略、引用、选择及新增节点检查共享插件身份。存量使用独立命令手动初始化，新空间自动初始化，默认 `migrate` 仅建表。

**Tech Stack:** 仓库现有 Python、Django/DRF、MySQL、Celery、Vue 2.7、Vuex、bk-magic-vue；pytest、现有 Node 行为测试；bkaidev 应用态 Chat Completion。不得为此重构公共 HTTP 客户端或引入新的消息系统。

**Spec:** `docs/specs/2026-10-30-space-plugin-catalog-v2-design.md`。产品依据为该设计链接的企微 V2，及用户 2026-10-30 关于低频恢复检查、独立手动初始化命令、scope 例外单独处理的最新确认；新确认覆盖旧 migrate 文案。

团队评审版：[开发设计智能文档](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=OYB9Sg)。本文保留逐任务执行细节，在线阅读版保留架构、数据、接口、异常和发布说明。

团队实施安排：[开发实施计划（团队阅读版）](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=UhJZjU)，本地稿为 `docs/plans/2026-10-30-space-plugin-catalog-v2-team-plan.md`；按原任务编号说明交付顺序、协作依赖与完成标准，保留暂定项。

## Global Constraints

- 身份是 `builtin:{code}`、`bk_plugin:{plugin_code}`、`uniform_api:{source_key}:{api_id}`，不含版本；本期 V2/V3/V4 API 均逐插件管理。
- 状态为「启用、待审核、未启用、已失效」；来源首次超时/鉴权失败立即失效，恢复保留原管理决定；无整体管理开关、无隐藏、无失效清理。
- 推荐上限 **10**；失效保留推荐并占名额；主动停用取消推荐；批量超限整批拒绝；推荐组始终在前，两组分别按所选字段和方向排序。
- 目录最多 **2 层**，同级唯一；新根目录和新子目录分别追加到对应层末尾。删除提升子目录、直接插件包含未启用项移未分类；不删除插件实体。
- 新空间与默认新插件保持原平台准入范围；默认直接启用、按来源原分类归类；不因切换策略或同步覆盖已有管理决定。
- 存量初始化由独立命令手动触发；**默认 migrate 不调用来源、不回填业务数据、不派发初始化任务**。旧 scope 限制只作为例外兼容，不新增 scope 管理产品能力。
- 首次请求外，快速重试技术默认值为 **3 次、10/20/40 秒、抖动不超过 20%、一轮不超过 5 分钟**；同一持续故障耗尽后只低频检查，不重开快速重试。凭证无效、确认删除、协议错误不盲目快速重试。
- 当前引用仅当前发布/草稿，按流程去重；只有草稿引用才命中草稿筛选；未版本化流程使用唯一 current。数据未就绪不显示 0。
- 已有流程新增不可选插件节点拦截；已有同插件节点不豁免新节点；整流程创建/复制/导入及网关创建/回滚例外保留。空间管理停用不阻断存量编辑、建任务、启动、调试。
- 人工 AI 有结果自动调整编辑副本、无结果不变、失败报错；撤销回到本次 AI 前完整状态、保存后清除撤销。自动 AI 空结果进未分类，AI 不决定审核或推荐。
- AI 使用 BKFlow 自身应用凭证，服务端认证头；不向前端下发密钥，不记录认证头或完整敏感提示；实际模型/环境由部署配置给定，不替用户选供应商或模型。
- **第 6、7 项继续暂定**；T13 联系字段、T17 文案维持建议状态，不能标为最终验收通过。
- Interface 拥有新表；Engine 只走现有内部快照接口，不读取新目录 ORM。租户/空间检查先于管理员权限 OR，不能因管理员身份跳过租户边界。
- 本轮只编制计划；实现前建立隔离工作树并核对测试配置。提交统一关联已核实的 TAPD「插件管理」需求，源码关键词 `--story=139209730`；本轮文档归档按用户后续授权提交。

## Review Focus

1. 来源分页超过 200 项、多个展示配置指向同一 source_key：必须汇总完整请求范围后才判删除；T4/T5 覆盖。
2. 较旧失败任务晚于新成功任务返回：不得把恢复后的插件再次误标失效，也不能覆盖人工停用；T5 覆盖。
3. 删除目录与停用/启用并发：未启用归属、待审核目标与推荐占用必须一致，冲突不部分保存；T2/T3 覆盖。
4. 网关服务端重建全部节点 ID：不能误判所有存量节点新增，也不能放过复制出的同插件节点；T9 覆盖。
5. 初始化在部分空间成功后中断：重跑不覆盖成功空间的人工设置，失败空间不留半套数据；T7 覆盖。

## 执行边界、依赖与文件地图

这是同一个功能的集成计划：共用身份、空间状态、引用及权限契约，不能把管理页或选择过滤单独上线。评审可按四批进行：T1—T5 基础与同步；T6—T10 迁移/引用/接口；T11—T15 AI/前端；T16 联调与发布。

| 文件区域 | 职责 | 任务 |
| --- | --- | --- |
| 新 `bkflow/plugin_catalog/{apps,contracts,identity,state,models,exceptions}.py`、migrations | 公共契约与 Interface 表结构 | T1 |
| 新 `services/{directories,policy,management,recommendation,records}.py` | 目录、策略和管理员命令 | T2/T3 |
| 新 `providers/{base,builtin,bk_plugin,uniform_api}.py`、`services/sync.py`、`retry.py`、`tasks.py` | 完整来源清单、故障轮次和调度 | T4/T5 |
| 新 `services/{references,initialization,legacy_scope,selection,save_guard}.py`、`sorting.py` | 当前引用、初始化、选择、共用排序、新增检查 | T6—T9 |
| 新 `management/commands/initialize_plugin_catalog.py` | 运维手动预览与初始化 | T7 |
| 新 `views/{catalog,directories,policy,references,ai}.py`、`serializers.py`、`urls.py` | 管理 API 与请求鉴权 | T10/T11 |
| 新 `clients/bkaidev_llm.py`、`services/ai_classification.py` | AI 请求、结果校验、自动分类提交 | T11 |
| 新 `frontend/src/views/admin/PluginCatalog/`、store 模块与行为测试 | 目录编辑、管理、策略、引用 | T12—T14 |
| 现有两套 NodeMenu、`TemplateEdit/NodeConfig/NodeConfig.vue` | 使用侧查找与存量参数处理 | T15 |

现有文件只增加本功能入口或委托，不重构全部流程生命周期。计划中的新增 Python 包同时包含 `__init__.py`；新迁移为 `bkflow/plugin_catalog/migrations/0001_initial.py`，不改已发布旧迁移。

共用类型在 T1 的 `contracts.py` 定义；以下是内部接口，不自动注册为开放网关 API：

| 类型 | 固定字段/含义 |
| --- | --- |
| `CatalogContext` | `space_id:int, actor:str, scope:str|None`；只能从已鉴权服务端上下文构造 |
| `PluginIdentity` | `plugin_key:str, kind:str, source_key:str|None, source_id:str` |
| `SourceContext` | `space_id, source_key, request_scope, config_revision, generation`；request_scope 明确覆盖条目范围 |
| `SourceObservation` | `context, items, complete, error_kind, observed_at`；items 含身份、元信息、精确版本及来源分类；失败不能伪造完整空列表 |
| `DirectoryNode` | `id:str, parent_id:str|None, name:str, order:int, system:bool` |
| `DirectoryDocument` | `revision:int, directories:dict[str,DirectoryNode], assignments:dict[str,str], pending_targets:dict[str,str]`；插件归属/审核目标按 plugin_key 指向目录 ID |
| `PolicyDocument` | `revision, mode, groups, classification, ai_scope`；mode 为 all_enabled/all_review/conditional，AI 范围 incremental/free |
| `PluginNode` | `plugin_key, node_path, name, plugin_version`；node_path 含内嵌画布路径 |
| `Violation` | `plugin_key, node_path, reason, replacement_key`；不泄露空间外对象 |
| `ClassificationIntent` | `request_id, space_id, plugin_keys, policy_revision, directory_revision, ai_scope`；只代表分类任务，不改变准入 |
| `ClassificationResult` | `status:patch|empty|error, document_patch, request_id, edit_revision, error`；不含审核/推荐字段 |

其余结果类型由拥有任务定义。面向管理员的 mutation 接受 expected_revision，返回提交后的 revision；来源提交使用 config_revision/generation，初始化使用空间唯一状态；不能强迫这些后台入口使用前端修订号。模块内记录函数 `record_change(ctx, *, object_key, action, before, after, method, reason, request_id)` 返回记录 ID，request_id＋action＋object_key 唯一以支持幂等。不能把技术修订号展示成业务版本。

修订号映射固定为：`DirectoryDocument.revision = SpaceCatalogConfig.directory_revision`；管理命令 expected_revision 对应 `SpaceCatalogConfig.revision`；`PolicyDocument.revision = policy_revision`。来源故障提交与管理命令共用空间锁并更新可选性修订号，但元信息刷新不能改目录/策略修订号。AI intent 同时校验 policy_revision 和 directory_revision。

### 首次执行测试前的准备

- 只在隔离工作树使用 `.github/workflows/unittest.yml` 的测试数据库模式；核对 `tests/interface.env`、`tests/engine.env`、`local_settings.py` 和实际加载后的数据库/缓存目的地。不得覆盖当前工作区 local_settings，不输出密码。
- 使用专用 MySQL 测试库和独立测试缓存；并发与行锁测试不用 SQLite 代替。外部来源、bkaidev、Celery 派发默认替身，不访问真实业务空间。
- Interface 命令的前提是该隔离 shell 已加载 `tests/interface.env`；Engine 测试另开进程加载 `tests/engine.env`。下文 `pytest -o addopts=''` 覆盖仓库默认全覆盖率参数，减少无关输出，不取消断言。
- T1 创建 `tests/interface/plugin_catalog/conftest.py`，提供模拟身份、来源、目录、当前快照及受控时钟；数据库/外部请求目标未核验时不执行测试或 migrate。
- 每项的“提交”只包含该任务文件与配套测试；标题格式 `feat(plugin_catalog): … --story=139209730`；文档提交使用 docs 类型。已复用现有需求，不新建工单；推送按用户授权范围执行。

---

### Task 1：统一身份、状态模型与表约束

**Files:** 新建 `bkflow/plugin_catalog/{__init__,apps,contracts,identity,state,models,exceptions}.py`、`migrations/0001_initial.py`；修改 `module_settings.py` 的 Interface 应用清单；测试 `tests/interface/plugin_catalog/{conftest,test_identity,test_models}.py`、`tests/project_settings/test_module_settings.py`。

**Consumes / Dependencies:** Spec §4；本任务产出所有共用类型与模型。

**Interfaces:** `resolve_identity(kind, code=None, source_key=None, api_id=None) -> PluginIdentity`；`effective_state(management_state, source_valid) -> str`。模型按 spec §4；空间配置新增目录/管理 revision，来源状态保存故障原因；不创建 LegacyScopeVisibility 表。

- [ ] 写失败测试：`test_identity_excludes_version` 断言同插件两个版本身份相等；`test_source_is_part_of_api_identity` 断言两来源同 ID 不相等；`test_invalid_preserves_decision` 参数化 enabled/pending/disabled，断言失效不修改管理决定；`test_unique_root_name` 验证根目录同名也被拒绝；`test_interface_only` 验证 Engine 不安装新 app。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_identity.py tests/interface/plugin_catalog/test_models.py -q`，预期因新模块/约束缺失失败，不能将环境连接错误当成 RED。
- [ ] 实现类型、状态纯函数、表和索引；记录分类方式与原因。根目录唯一性采用非空规范化父级键＋唯一约束；执行已有目录应用层校验之外的数据库兜底。新 migration 仅 schema 操作，无 RunPython 初始化、无 post_migrate 任务。
- [ ] 重跑上述命令并运行 `pytest -o addopts='' tests/project_settings/test_module_settings.py -q`，预期全部 PASS；在隔离测试库检查迁移往返和重复应用，不调用外部来源。
- [ ] 按已核实工单提交本任务，建议标题「建立插件目录身份与状态模型」。

### Task 2：目录整页保存、移动与删除转换

**Files:** 新建 `services/directories.py`、`services/records.py`；测试 `tests/interface/plugin_catalog/test_directories.py`。

**Consumes / Dependencies:** T1 的 DirectoryDocument/模型；产出 preview_directory_change、save_directory_document、record_change。

**Interfaces:** `preview_directory_change(document:DirectoryDocument, changes:list[dict]) -> DirectoryDocument`；`save_directory_document(ctx, document, expected_revision:int) -> DirectoryDocument`；`read_directory_document(ctx) -> DirectoryDocument`。输入 changes 只允许创建/重命名/移动/删除目录及变更插件归属，不能改变插件状态。

- [ ] 写失败测试：`test_append_root_and_child` 断言追加末尾；`test_delete_parent` 断言子目录提升、直接启用/未启用插件和审核目标移未分类、子目录内插件不动；`test_move_multiple_children` 断言多选跨父目录后仍两级；`test_conflicting_promotion` 断言重名时整次失败；`test_stale_revision` 断言并发编辑不覆盖；`test_system_directory_protected` 断言系统未分类不可删改移。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_directories.py -q`，预期新服务缺失导致失败。
- [ ] 实现纯转换及事务提交；同一转换用于预览和保存；检查目录/插件都属于 ctx 空间。祖先与子目录同时被选中时根据最终树计算结果，不依赖遍历顺序；混选插件执行目录删除请求直接拒绝。记录每次实际归类的 method/reason。
- [ ] 重跑该测试文件，预期 PASS；使用 `django_db(transaction=True)` 覆盖删除与另一个移动请求并发，验证无悬空目录和半保存。
- [ ] 提交本任务，建议标题「实现目录批量调整与删除保护」。

### Task 3：新插件策略、审核启停与推荐

**Files:** 新建 `services/{policy,management,recommendation}.py`；测试 `tests/interface/plugin_catalog/{test_policy,test_management,test_recommendation}.py`。

**Consumes / Dependencies:** T1 状态模型、T2 的目录校验和 record_change；产出准入、管理和推荐命令。

**Interfaces:** `decide_new_plugin(policy:PolicyDocument, plugin:dict) -> dict` 返回 management_state、classification、target_directory；`save_policy(ctx, policy, expected_revision) -> PolicyDocument`；`change_management(ctx, action:str, items:list[dict], expected_revision:int) -> int`；`set_recommendation(ctx, plugin_keys:list[str], recommended:bool, expected_revision:int) -> dict` 返回 revision/occupied/remaining。items 为 plugin_key/target_directory/reason/replacement_key。

- [ ] 写失败测试：`test_three_policies` 覆盖默认直接启用＋来源分类、全审核、条件命中/未命中；`test_duplicate_source_groups` 拒绝重复来源；`test_policy_change_does_not_reprocess_stock` 保持所有存量状态；`test_disable_clears_recommendation`、`test_invalid_keeps_recommendation_slot`、`test_batch_limit_atomic` 验证 10 名额及整批拒绝；`test_never_enabled_has_no_disable_config` 验证审核不启用不获得停用配置；`test_reenable_uses_retained_directory` 验证删除后回填未分类。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_policy.py tests/interface/plugin_catalog/test_management.py tests/interface/plugin_catalog/test_recommendation.py -q`，预期服务缺失失败。
- [ ] 实现命令与策略纯判断，事务内锁 SpaceCatalogConfig 后按稳定 ID 锁对象。停用原因最多 200 字，替换不能为自己且必须满足平台准入、原有兼容范围、enabled 和有效条件；T8 接通后共用查询，不另留口径。未填原因保持统一文案。来源恢复不调用 enable，直接保留原 management_state；状态在确认时变化须再次校验。
- [ ] 重跑该组，预期 PASS；增加两管理员同时推荐最后一个名额、同步恢复与主动停用并发测试，断言最终占用不超过 10 且人工决定不丢失。
- [ ] 提交本任务，建议标题「实现新插件策略与审核推荐命令」。第 6/7 项仅设计数据载荷，不据此关闭交互暂定项。

### Task 4：所有来源的完整逐插件清单

**Files:** 新建 `providers/{base,builtin,bk_plugin,uniform_api}.py`；复用 `bkflow/plugin/services/uniform_api_meta.py`、`bkflow/pipeline_plugins/query/uniform_api/uniform_api.py`、`bkflow/bk_plugin/models.py` 的公开能力；测试 `tests/interface/plugin_catalog/test_providers.py`。

**Consumes / Dependencies:** T1 SourceContext/SourceObservation/resolve_identity；复用现有来源协议。

**Interfaces:** `Provider.collect(context:SourceContext) -> SourceObservation`；`list_source_contexts(space_id:int) -> list[SourceContext]`；统一 API provider 接收可注入客户端，返回全量 entries，保留业务版本与 wrapper_version。

- [ ] 写失败测试：`test_all_plugin_kinds` 含内置/蓝鲸/V2/V3/V4；`test_401_items_all_pages` 确认 401 条不会截成 200；`test_same_source_multiple_views` 确认同 source_key 多展示配置合并范围；`test_non_default_source` 覆盖非 default；`test_remote_cache_hybrid` 覆盖三种模式；`test_partial_page_not_complete` 断言第二页失败时 complete=false；`test_missing_identity_not_fabricated` 拒绝用 URL 哈希伪造身份。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_providers.py -q`，预期 provider 缺失失败。
- [ ] 实现适配器，只取元信息，不调用业务执行接口；分页按各来源返回协议停止并防止重复游标/不收敛。蓝鲸平台授权被拒绝与来源删除分开；保留 last known 元信息。来源分类先按 spec 平面根分类映射，遇不可可靠映射项在预览报告，不自行裁剪合并。
- [ ] 重跑该文件，预期 PASS；同时跑 `pytest -o addopts='' tests/interface/plugin/services/test_uniform_api_meta.py tests/interface/plugin/services/test_plugin_schema_service.py -q`，证明复用不改变原查询协议。
- [ ] 提交本任务，建议标题「统一全类型插件来源采集」。

### Task 5：来源同步、有限重试与低频恢复检查

**Files:** 新建 `services/sync.py`、`retry.py`、`tasks.py`；按现有配置入口修改 `env.py`、`config/default.py`、`bkflow/plugin/tasks.py` 的调度接入及 `bkflow/plugin/services/open_plugin_catalog.py` 的旧来源快照适配；测试 `tests/interface/plugin_catalog/{test_sync,test_retry}.py`。

**Consumes / Dependencies:** T3 decide_new_plugin、T4 Provider.collect、T2 record_change；产生 ClassificationIntent 供 T11 消费。

**Interfaces:** `apply_observation(observation:SourceObservation) -> list[ClassificationIntent]`；`plan_retry(error_kind:str, attempts:int, elapsed_seconds:float, jitter:float) -> float|None`；`sync_source(context:SourceContext, trigger:str) -> None`，trigger 为 discovery/retry/poll/config_change。SourceSyncState 分开持有故障轮次、attempts、轮次开始时间、配置代次和采集代次。部署配置 `PLUGIN_CATALOG_SYNC_MAX_RETRIES=3`、`PLUGIN_CATALOG_RETRY_BASE_SECONDS=10`、`PLUGIN_CATALOG_RETRY_MAX_ELAPSED_SECONDS=300`、`PLUGIN_CATALOG_RETRY_JITTER_RATIO=0.2`，环境变量沿用 `BKAPP_` 前缀。

- [ ] 写失败测试：`test_first_timeout_invalidates_covered_only`、`test_auth_failure_no_fast_retry`；`test_deleted_pending_and_disabled`；`test_retry_budget` 断言等待 10/20/40、最多 3 次、300 秒截止、抖动边界；`test_poll_after_exhaustion_no_new_burst`；`test_recovery_restores_each_decision`；`test_late_failure_discarded`；`test_incomplete_not_deleted`；`test_duplicate_discovery_does_not_reapply_policy`；`test_unready_not_discovered_by_policy`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_sync.py tests/interface/plugin_catalog/test_retry.py -q`，预期新服务失败。
- [ ] 实现网络事务外、提交时校验 config_revision/generation；首次入库仅执行一次 T3 准入，产生分类 intent。未 ready 空间不由新周期同步创建准入/目录记录，仍走原读取/旧同步路径，业务初始化由 T7 唯一负责。超时/鉴权失败按请求实际范围失效，失败无新证据不恢复；其他错误只按来源明确协议映射，不把未知错误当删除。同一持续故障中的正常巡检不补发快速重试；成功后结束故障轮次。AI 调度在 T11 接入，不让 AI 失败污染来源状态。
- [ ] 维护仍被 remote/cache_only/hybrid 和运行快照读取的 V4 `OpenPluginCatalogIndex` 元信息投影，保留精确版本信息；ready 空间不再由旧同步创建/覆盖 `SpaceOpenPluginAvailability.enabled`。T9 按新来源原因区分同步失败与真实版本失效。补 `test_v4_source_projection_fresh_without_management_dual_write` 断言版本更新可读、人工状态不双写。
- [ ] 重跑该组及 `pytest -o addopts='' tests/interface/plugin/test_tasks.py -q`，预期 PASS；用受控时钟和 Celery 替身测试，不真实等待 30 分钟或发网络请求。
- [ ] 提交本任务，建议标题「实现来源失效与有限恢复调度」。

### Task 6：当前引用索引与流程生命周期

**Files:** 新建 `services/references.py`；修改 `bkflow/template/models.py`、`bkflow/template/serializers/template.py`、`bkflow/template/views/template.py`；按调用链接入 `bkflow/apigw/views/{create_template,update_template,delete_template,release_template,rollback_template,create_template_with_a2flow}.py`；测试 `tests/interface/plugin_catalog/{test_references,test_reference_lifecycle}.py`。

**Consumes / Dependencies:** T1 PluginIdentity/PluginNode/引用模型；产出 replace_current_references、query_references。

**Interfaces:** `collect_direct_plugin_nodes(tree:dict) -> tuple[list[PluginNode],list[dict]]`；`replace_current_references(template_id:int) -> None` 从数据库当前角色重建、参与调用方事务；`query_references(ctx, plugin_key:str, query:str, role:str, offset:int, limit:int) -> dict`；`export_references(ctx, plugin_key, query, role) -> Iterator[dict]`。返回 overview、rows、total、readiness；row 含各角色存在性、snapshot_id/version、节点清单及内容摘要。

- [ ] 写失败测试：`test_published_draft_union` 断言 6 个发布引用＋2 个仅草稿＝8；`test_draft_only_excludes_both`；`test_same_name_nodes_not_merged`；`test_history_excluded`；`test_no_draft_not_unreferenced`；`test_nonversioned_current`；`test_nested_owned_nodes_only`；`test_unknown_api_separate`；`test_csv_all_filtered_rows` 超过一页仍完整。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_references.py tests/interface/plugin_catalog/test_reference_lifecycle.py -q`，预期索引服务缺失失败。
- [ ] 实现当前角色原子替换，保留历史快照；对保存、发布角色切换、回滚草稿、删除、新建、复制、导入逐个定位最终事务，避免 API 和模型两次重建。没有插件引用与角色不存在分开；概览不随列表搜索缩小。未就绪返回明确错误/状态，不伪造 0；CSV 使用同一筛选无分页，单元格按文本安全导出。
- [ ] 重跑上述两文件并运行 `pytest -o addopts='' tests/interface/template/test_template_models.py tests/interface/apigw/test_rollback_template.py tests/interface/apigw/test_delete_template.py -q`，预期 PASS。每个入口至少一条集成断言在数据库中核对当前角色。
- [ ] 提交本任务；同次附带所改 APIGW 的 YAML、中文文档和重生成 zip，遵守末尾 APIGW 配套约定，建议标题「建立当前插件引用与生命周期更新」。

### Task 7：手动存量初始化与新空间默认初始化

**Files:** 新建 `services/{initialization,legacy_scope}.py`、`management/commands/initialize_plugin_catalog.py`；修改 `bkflow/space/views.py`、`bkflow/apigw/views/create_space.py` 的成功创建入口；测试 `tests/interface/plugin_catalog/{test_initialization,test_legacy_scope}.py`、`tests/interface/apigw/test_create_space.py`。

**Consumes / Dependencies:** T4 完整采集、T2 目录提交、T6 replace_current_references；不通过 T5 将存量当新插件。

**Interfaces:** `preview_initialization(space_id:int) -> dict`；`initialize_space(space_id:int, *, dry_run:bool=False) -> dict` 返回 status/changed/errors/scope_exceptions；`check_legacy_scope(space_id:int, scope:str|None, plugin_keys:list[str]) -> set[str]` 仅处理已发现例外。命令为 `python manage.py initialize_plugin_catalog (--space-id ID [--space-id ID ...] | --all-spaces) [--dry-run]`。

- [ ] 写失败测试：`test_default_migrate_has_no_initialization` 断言来源/任务派发零调用、无存量数据回填；`test_dry_run_no_business_writes`；`test_command_requires_explicit_target`；`test_rerun_keeps_manual_decisions`；`test_failure_rolls_back_one_space`；`test_partial_success_resume`；`test_default_range_and_v4_disabled_preserved`；`test_new_space_auto_initializes`；`test_scope_exception_isolated`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_initialization.py tests/interface/plugin_catalog/test_legacy_scope.py -q`，预期新入口缺失失败。
- [ ] 实现 T4 全量预采集、旧配置快照、T2 来源目录生成、T6 引用回填；每空间原子提交 readiness，网络不放事务内。命令逐空间执行、失败汇总后非零退出，已 ready 跳过，不提供静默覆盖人工设置的 force。无旧限制空间直接主路径；真实例外复用 SpacePluginConfigParser 保留旧限制并单列结果，不建立普遍 scope 功能。新空间通过创建成功后的可恢复初始化入口自动调用同一服务。
- [ ] 重跑上述文件及 `pytest -o addopts='' tests/interface/apigw/test_create_space.py -q`，预期 PASS。隔离库用 command 测试验证 dry-run→执行→人为改目录→重跑三阶段；模拟第二空间失败，确认第一空间及其人工变更不回滚/不重置。
- [ ] 提交本任务并更新 create_space 的 APIGW 配套文件，建议标题「增加独立存量初始化命令」。不在任何真实环境执行该命令。

### Task 8：统一可选列表、排序与存量详情

**Files:** 新建 `services/selection.py`、`sorting.py`；修改 `requirements.txt`、`bkflow/plugin/services/{plugin_schema_service,plugin_detail}.py`、`bkflow/plugin/views/plugin.py`、`bkflow/pipeline_plugins/query/uniform_api/uniform_api.py`、`bkflow/apigw/views/{list_plugins,get_plugin_schema}.py`；测试 `tests/interface/plugin_catalog/test_selection.py`，扩展现有 list_plugins/get_plugin_schema/detail 测试。

**Consumes / Dependencies:** T5 来源状态、T6 引用计数、T7 check_legacy_scope/readiness；产出统一选择与排序。

**Interfaces:** `list_selectable(ctx, *, query:str, directory_id, kind, sort_by:str, direction:str, offset:int, limit:int) -> dict`；`get_plugin_statuses(ctx, plugin_keys:list[str]) -> dict`；`sort_catalog_items(items:list[dict], sort_by:str, direction:str) -> list[dict]` 供管理和使用侧共用；详情沿用现有 schema/detail 接口，不套用 selectable 过滤。排序键 recommendation/name/published_at/reference_count；名称为拼音，时间为最新版本真实发布时间，同值 plugin_key 升序、空值后置；默认 recommendation 组内名称拼音升序。

- [ ] 写失败测试：`test_only_enabled_valid`；`test_sort_two_groups_each_direction`；`test_pinyin_and_latest_version_date`；`test_filter_before_pagination`；`test_usage_search_name_code_only`；`test_disabled_detail_and_versions_accessible`；`test_cross_tenant_denied_even_admin`；`test_preinitialization_legacy_read` 保持迁移前读取且无虚假空列表；`test_ready_never_falls_back`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_selection.py -q`，预期统一查询缺失失败。
- [ ] 实现先准入/租户/空间和例外兼容、再管理状态、再排序分页；推荐组不随方向反转。当前依赖未发现拼音库，采用 `pypinyin==0.55.0` 的 `lazy_pinyin` 无声调拼音＋casefold 生成统一键，不增加前端另一套排序；库版本和能力已在 [PyPI 项目页](https://pypi.org/project/pypinyin/0.55.0/) 核验，安装留待实施。历史详情保留原授权与精确版本；未初始化回退只用于原读取入口，管理写入明确未就绪。
- [ ] 重跑该文件和 `pytest -o addopts='' tests/interface/apigw/test_list_plugins.py tests/interface/apigw/test_get_plugin_schema.py tests/interface/plugin/test_plugin_detail_view.py -q`，预期 PASS；对旧接口包络、分页 total 和字段兼容作断言。
- [ ] 提交本任务及 APIGW 配套，建议标题「统一空间插件选择与详情边界」。

### Task 9：新增节点检查与存量运行边界

**Files:** 新建 `services/save_guard.py`；修改 `bkflow/template/serializers/template.py`、`bkflow/apigw/views/update_template.py`、`bkflow/plugin/services/open_plugin_snapshot.py`、必要的 `bkflow/plugin/views/internal.py` 委托；测试 `tests/interface/plugin_catalog/test_save_guard.py`，扩展 `tests/interface/apigw/test_update_template.py`、`tests/interface/plugin/services/test_open_plugin_snapshot.py`、`tests/engine/task/test_open_plugin_snapshots.py`。

**Consumes / Dependencies:** T6 collect_direct_plugin_nodes、T8 可选判断、T3 空间锁顺序；产出逐节点 Violation。

**Interfaces:** `validate_plugin_node_additions(baselines:list[dict], incoming_tree:dict, ctx:CatalogContext) -> list[Violation]`；基线由服务端读当前草稿/发布，T6 解析节点。现有 snapshot 校验增加显式 purpose（save_existing/create_task/start/debug），将管理状态与真实精确版本/授权检查分开，不另建 Engine 目录入口。

- [ ] 写失败测试：`test_old_node_allowed_new_same_plugin_rejected`；`test_copied_node_rejected`；`test_same_id_new_plugin_checked`；`test_same_plugin_version_change_allowed`；`test_server_id_rewrite_after_validation`；`test_create_copy_import_rollback_exempt`；`test_disable_between_check_and_save`；`test_stock_runtime_ignores_management_disable_and_sync_timeout`；`test_real_missing_version_and_tenant_still_rejected`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_save_guard.py -q`，预期新规则未实现失败。
- [ ] 在服务端重建 ID 前校验原始树，按完整节点路径＋plugin_key 匹配；通过后才保留原 ID 转换流程。与 T3 同锁顺序并在事务中复查状态；来源同步改变有效性也遵守该锁/修订契约。不得按插件集合/数量放行。保留整流程例外、结构、平台和租户检查；仅管理停用及同步超时/鉴权不阻断存量运行，真实来源调用或版本错误仍反馈。
- [ ] 重跑该文件及上述 Interface 受影响测试；另开 Engine 测试进程运行 `pytest -o addopts='' tests/engine/task/test_open_plugin_snapshots.py -q`，预期 PASS。SDK 转发入口已有静态证据；真实第三方若提交前自行重建 ID，先单列兼容证据，不凭猜测放宽规则。
- [ ] 提交本任务及 update_template APIGW 配套，建议标题「按新增节点校验插件并保留存量运行」。

### Task 10：管理接口、引用导出和旧入口兼容

**Files:** 新建 `views/{catalog,directories,policy,references}.py`、`serializers.py`、`urls.py`；修改 `bkflow/urls.py`、`bkflow/space/views.py`、`bkflow/apigw/views/{create_space,renew_space_config}.py`；测试 `tests/interface/plugin_catalog/test_api.py`、`tests/interface/apigw/test_create_space_config.py`。

**Consumes / Dependencies:** T2/T3 命令、T6 引用/CSV、T8 选择/状态/排序、T9 Violation；仅做协议与鉴权适配。

**Interfaces:** `/api/plugin_catalog/spaces/{space_id}/` 下的 `plugins/` GET、`statuses/` POST、`directories/` GET/PUT、`directories/preview/` POST、`policy/` GET/PUT、`management/` POST、`recommendation/` POST、`references/` GET、`references/export/` GET、`unresolved-api/` GET。引用/身份用 query/body，不把带冒号的 plugin_key 拼入层级路径。包络复用项目标准，409 表示 revision 冲突。

- [ ] 写失败测试：`test_admin_actions_require_space_and_tenant`；`test_batch_foreign_object_rejected`；`test_management_search_fields_and_tab_counts`；`test_reference_overview_unfiltered`；`test_unresolved_api_not_inventory_count`；`test_legacy_writes_rejected_after_ready`；`test_legacy_v4_actions_delegate`；`test_pending_initialization_not_zero`；`test_replacement_target_revalidated`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_api.py -q`，预期路由缺失失败。
- [ ] 使用 TenantScopeMixin 和既有管理员权限；管理搜索支持名称/描述/修改人模糊与类型/来源/目录组合筛选，Tab 数量随筛选、目录总数包含失效，排序共用 T8。首次来源请求失败以 source_errors 返回，不能呈现为已确认成功的零插件。旧 V4 list/toggle/enable_all/disable_source 统一委托新服务，不能双写旧管理真源；已 ready 后旧 space_plugin_config 写入明确拒绝。状态查询仅供授权存量流程，不向普通可选搜索泄露不可选项。
- [ ] 重跑该文件及受影响 create/renew space config 测试，预期 PASS。逐 endpoint 对跨租户、跨空间、普通用户权限与 CSV 全匹配范围作验证。
- [ ] 提交本任务及 APIGW 配套，建议标题「提供插件管理接口并兼容旧入口」。

### Task 11：bkaidev AI 分类与自动策略接入

**Files:** 新建 `clients/bkaidev_llm.py`、`services/ai_classification.py`、`views/ai.py`；修改新模块 `tasks.py`、`urls.py` 与 `env.py`、`config/default.py` 配置；测试 `tests/interface/plugin_catalog/{test_llm_client,test_ai_classification}.py`。

**Consumes / Dependencies:** T5 ClassificationIntent、T2 目录校验/提交、T3 准入结果；人工结果供 T12 消费。

**Interfaces:** `BkaidevLLMClient.complete(*, model:str, messages:list[dict]) -> str`；`classify(ctx, document:DirectoryDocument, selected_keys:list[str], ai_scope:str, prompt:str, request_id:str) -> ClassificationResult`；`apply_automatic_classification(intent:ClassificationIntent) -> None`；HTTP `POST .../ai/classify/` 返回 patch/empty/error。配置名 `PLUGIN_CATALOG_LLM_BASE_URL`、`PLUGIN_CATALOG_LLM_MODEL`、`PLUGIN_CATALOG_LLM_TIMEOUT`，凭证只取 APP_CODE/SECRET_KEY；环境变量沿用 `BKAPP_` 前缀，连接超时 5 秒、读取超时默认 60 秒可配置。BASE_URL/MODEL 未配置时仅 AI 入口报配置错误，不影响默认来源分类或基础插件管理。

- [ ] 写失败测试：`test_app_auth_header_not_business_body`；`test_no_secret_in_errors`；`test_non_json_truncated_refused_response`；`test_empty_manual_no_change`；`test_empty_automatic_uncategorized_not_pending`；`test_ai_cannot_change_state_or_recommendation`；`test_incremental_cannot_modify_stock`；`test_free_changes_stock_in_scope_only`；`test_stale_policy_or_directory_revision_rejected`；`test_duplicate_intent_applied_once`。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_llm_client.py tests/interface/plugin_catalog/test_ai_classification.py -q`，预期模块缺失失败。
- [ ] 实现非流式 OpenAI 兼容基础 body，显式 TLS 校验与超时，按公开 Chat Completion 文档解析；不假定 json_schema 支持。AI 输入仅必要摘要，输出采用白名单 JSON 后经 T2 验证；人工请求不写正式目录。自动 intent 在来源提交后触发，合法结果经 T2 独立目录命令原子提交；空结果归未分类，失败记录且不改变审核/推荐。请求错误不无条件重发；实际失败分类与超时配置在联调记录，不复用来源重试状态。
- [ ] 重跑上述文件，预期 PASS。真实 bkaidev 联调单列证据：部署环境/指定模型、BKFlow 应用权限、正常/空/错误样本；没有获准可用测试配置时，不调用生产 LLM、不宣称 E2E 已完成。
- [ ] 提交本任务，建议标题「接入应用态 AI 分类并约束结果范围」。

### Task 12：目录前端编辑状态、AI 撤销与整页保存

**Files:** 新建 `frontend/src/views/admin/PluginCatalog/{DirectoryEditor.vue,DirectoryDialog.vue,MoveDialog.vue,DeletePreview.vue,editorState.js}`、`frontend/src/store/modules/pluginCatalog.js` 的目录/AI 部分；新建 `frontend/tests/pluginCatalogEditor.test.js`；修改 `frontend/src/store/index.js` 注册模块、`frontend/package.json` 添加本模块测试命令。

**Consumes / Dependencies:** T10 目录 API、T11 classify；产出 editorState 与目录/AI store 动作。

**Interfaces:** `createEditorState(document)`；`reduceEditor(state,event)`，event 为 EDIT/AI_START/AI_RESULT/AI_EMPTY/AI_ERROR/UNDO_AI/SAVE_SUCCESS/RELOAD；返回 document、dirty、revision、pendingRequest、beforeAi、error。编辑状态完整保存目录与插件归属，不直接引用 Vuex 原对象。

- [ ] 写失败测试：`testUndoRestoresManualAndPreviousAiState`、`testEmptyAiIsIdentity`、`testSaveClearsUndo`、`testLateAiCannotOverwriteSavedState`、`testDeletePreviewMatchesSubmittedDocument`、`testMultiselectChildrenMove`；用深相等验证完整状态，不能只断言按钮存在。
- [ ] 在 frontend 执行 `node tests/pluginCatalogEditor.test.js`，预期 reducer 缺失失败。
- [ ] 实现 reducer 和组件：根/子末尾、父目录选择、目录排序、多选移动、插件不可删除的禁用提示、删除后改动预览；通过 T10 接口一次提交，409 显示冲突并允许刷新，不静默覆盖。AI 使用 T11：有结果应用、空不动、失败报错、保存成功清撤销；用户编辑后到达的旧结果按请求 revision 丢弃。
- [ ] 重跑 Node 测试预期 PASS；在本地 mock 页面实际操作创建/删除/AI/撤销/保存，检查树与提交内容一致、弹窗取消不产生保存；记录截图与请求断言。
- [ ] 提交本任务，建议标题「实现目录编辑与 AI 撤销」。

### Task 13：空间管理列表、策略与启停界面

**Files:** 新建 `frontend/src/views/admin/PluginCatalog/{index.vue,PluginTable.vue,PolicyDrawer.vue,EnableDialog.vue,DisableDialog.vue,actionState.js}`、`frontend/tests/pluginCatalogActions.test.js`；扩展 `frontend/src/store/modules/pluginCatalog.js` 的管理/策略部分；修改 `frontend/src/views/admin/Space/index.vue`、`frontend/src/views/admin/Space/SpaceConfig/index.vue`、`frontend/src/config/i18n/{cn,en}.js`；路由仅在现有空间入口需要时接入 `frontend/src/router/index.js`。

**Consumes / Dependencies:** T10 管理/策略 API、T12 目录组件和 store；扩展管理动作。

**Interfaces:** store actions 对应 T10/T11 明确 API；`buildManagementRequest(action, selectedItems, expectedRevision)`。暂定项只在任务及验收记录标记，不向产品增加技术标志或开关。

- [ ] 写失败测试：`testCombinedSearchSelectsFirstNonemptyTab`、`testRecommendationCapacityIncludesInvalid`、`testPolicyCancelDoesNotSubmit`、`testDuplicateSourceChoiceDisabled`、`testNeverEnabledNoDisableSettings`、`testEnableCancelledNoMutation`。暂定测试独立命名 `tentative6QuickDirectorySave`、`tentative7PerItemEnableTargets`，不能计入最终产品验收。
- [ ] 在 frontend 执行 `node tests/pluginCatalogActions.test.js`，预期请求构造/状态缺失失败。
- [ ] 按当前稿四状态两组、目录入口、组合筛选、推荐分组、批量操作实现；策略默认为直接启用＋来源分类，条件组来源互斥，AI 两模式可选，保存才提交。旧空间配置标记已迁移并只读引导。第 6 项快捷保存、第 7 项逐项确认放独立组件/动作，不与核心服务耦合；按暂定方案可演示但保留暂定标签在验收清单。
- [ ] 重跑 Node 测试，预期 PASS；在本地 mock 页面检查推荐满额、权限不足、来源失效、未初始化、搜索无结果及批量状态变化；核对 i18n 和 Figma 文案。无新空间总开关、无隐藏、无手工插件排序。
- [ ] 提交本任务，建议标题「接入空间插件管理和新插件策略」。

### Task 14：引用详情、版本定位与导出

**Files:** 新建 `frontend/src/views/admin/PluginCatalog/{ReferencePanel.vue,referenceState.js}`、`frontend/tests/pluginCatalogReferences.test.js`；修改 `frontend/src/views/template/TemplateEdit/index.vue` 的 `getTemplateData`/画布就绪后定位逻辑、`frontend/src/router/index.js` 的 templatePanel 参数接入；扩展 `frontend/src/store/modules/pluginCatalog.js`。不依赖 NodeConfig 面板加载来决定流程版本。

**Consumes / Dependencies:** T6/T10 当前引用和角色存在性、T13 插件详情入口；产出精确跳转契约。

**Interfaces:** `buildReferenceTarget(row, role) -> {templateId,snapshotId,version,nodePaths,contentDigest}|null`；`validateReferenceTarget(expected, actual) -> {valid,message}`。使用既有 templatePanel 路由的 view/edit 类型，新增 query `reference_role/reference_snapshot/reference_digest/reference_nodes`，节点路径数组以 JSON 编码并做结构校验。published 查看指定发布快照，draft 编辑当前草稿；改变后提示刷新。现有 `getTemplateData` 会优先加载草稿，引用入口必须按显式 role 选择，不能先跳入草稿再只高亮同 ID。

- [ ] 写失败测试：`testNoDraftNoEditLink`、`testUnreferencedNotNoDraft`、`testPublishedAndDraftTargetsSeparate`、`testChangedSnapshotRequiresRefresh`、`testOverviewDoesNotFollowSearch`、`testCsvUsesCurrentFiltersWithoutPage`；断言同名不同节点均可定位。
- [ ] 在 frontend 执行 `node tests/pluginCatalogReferences.test.js`，预期定位转换缺失失败。
- [ ] 实现三个统计、发布/草稿各自计数、悬浮节点名称/入口、仅草稿筛选和全部匹配 CSV；未版本化流程明确 current，不伪造草稿。无法识别旧 API 在失效页独立提示、定位流程节点，不计插件清单或单插件引用。T13 联系字段按建议保留真实创建人/修改人称谓，T17 文案维持建议状态。
- [ ] 重跑 Node 测试，预期 PASS；用同一流程发布/草稿不同节点、仅历史引用、无草稿/未发布三个样本实际检查跳转及导出；目标消失不能跳到相邻版本。
- [ ] 提交本任务，建议标题「实现当前引用详情和准确版本定位」。

### Task 15：两套画布选择与参数保留

**Files:** 修改 `frontend/src/components/common/TemplateCanvas/PalettePanel/NodeMenu/{NodeMenu,BuiltInPluginList,ThirdPartyPluginList,ApiPluginList}.vue`、`frontend/src/components/canvas/ProcessCanvas/components/dnd/NodeMenu/` 下对应四文件、`frontend/src/store/modules/plugin.js`、`frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue`；新建 `frontend/src/views/template/TemplateEdit/NodeConfig/pluginParameterTransfer.js`、`frontend/tests/{pluginCatalogSelection,pluginParameterTransfer}.test.js`。

**Consumes / Dependencies:** T8 可选/详情接口、T9 Violation、T14 编辑页角色/定位；产出两画布一致行为。

**Interfaces:** `transferParameters({mode,oldValues,oldSchema,newSchema,variableBindings}) -> {values,bindings,retained,needsConfirmation,dropped,oldInputs}`，mode 为 replace/version；`buildSelectionQuery({directory,kind,query,sortBy,direction,page}) -> dict`。两个画布共用 query/store 能力，不各算推荐和状态。

- [ ] 写失败测试：`testBothCanvasesUseSameSelectionContract`、`testNameCodeSearchExcludesDescription`、`testReplacementMatchesNameOnly`、`testVersionSameKeySameTypeRetainsBinding`、`testVersionTypeChangeNeedsConfirmation`、`testNewDefaultOldRemoved`、`testOldValueCanBeCopied`；所有插件类型参数化；现有节点仍可打开停用插件详情/版本。
- [ ] 在 frontend 执行 `node tests/pluginCatalogSelection.test.js`、`node tests/pluginParameterTransfer.test.js`，预期新公共函数缺失失败。
- [ ] 接入目录/类型/排序字段＋方向，推荐始终优先；详情版本不从可选列表推导。跨插件按同名保留原值，不做不同名称映射；同插件换版本须同 key 同表单类型保留值和变量关联。展示保留/待确认/丢弃数量、旧输入查看复制、新参数标记；保存拦截使用 T9 的具体节点原因与替换建议。
- [ ] 重跑两个 Node 文件和 `npm run test:plugin-form`，预期 PASS；两套画布分别实际检查停用节点移动/参数编辑/版本切换、复制新增节点拦截、普通新插件选择及所有排序方向。
- [ ] 提交本任务，建议标题「统一画布选择并保留替换参数」。

### Task 16：联调、发布手册与需求覆盖验收

**Files:** 新建 `docs/guide/plugin_catalog_operations.md`、`tests/interface/plugin_catalog/test_acceptance.py`；更新本计划证据清单、必要的 `.github/workflows/unittest.yml` 测试入口和 `frontend/package.json` 模块测试汇总。新增管理接口不默认开放 APIGW。

**Consumes / Dependencies:** T1—T15 的模块和接口；逐项归档测试、联调与发布证据。

**Interfaces:** 运维手册给出 T7 命令原样参数、状态字段、输出/非零退出含义；发布顺序固定为 schema→dry-run→手动初始化→核对→使用入口接入。测试 fixture 提供隔离空间和可控模拟来源，不依赖生产数据。

- [ ] 写失败验收测试：完整链路「新插件发现→按策略启用/待审核→审核→推荐→来源超时失效仍占名额→低频成功恢复→主动停用释放名额→存量编辑运行/新增拦截→删除目录移未分类→重新启用回填」。断言每步管理状态、来源状态、目录、可选列表与引用分别正确；另测跨租户批量请求全拒绝。
- [ ] 运行 `pytest -o addopts='' tests/interface/plugin_catalog/test_acceptance.py -q`，预期在尚未接通的入口出现行为失败；环境错误先修环境，不放宽业务断言。
- [ ] 补齐集成遗漏，撰写手册：初始化前后集合对比、快照、失败空间重跑、旧 scope 例外报告、故障原因与恢复、bkaidev 模型配置、部署回退。旧配置恢复不得覆盖上线后的新管理决定；未经目标环境授权不执行回退/初始化/真实业务调用。
- [ ] 运行目录模块全组与受影响 Interface/Engine/前端测试；适用 CI 再分别运行 `sh scripts/run_interface_unit_test.sh`、`sh scripts/run_engine_unit_test.sh`，修复本次引入失败。浏览器验收覆盖两套画布与管理页，记录环境、代码 revision、空间、预期/实际；真实 bkaidev 联调和目标环境业务验收单列，不以 mock 测试替代。
- [ ] 提交交付文档及必要修复，建议标题「补齐插件管理联调与初始化说明」。未确认项保持待确认/暂定，不能将整体标为最终验收通过。

## APIGW 配套约定

T6—T10 任何修改 `bkflow/apigw/` 视图的提交，同时核对并更新 `bkflow/apigw/management/commands/data/api-resources.yml` 对应 operation、`bkflow/apigw/docs/zh/{operation}.md`，执行 `bash scripts/apigw_docs.sh` 重建 `bkflow/apigw/docs/apigw-docs.zip`。调用 api-doc-sync 技能核对格式；资源无新增也要更新行为/错误说明，不能编造开放管理端点。检查生成包包含改动正文且未丢失其余条目。

## 覆盖映射与交付记录

下表把每项关键测试的结果断言固定下来；`before/after/result` 为该任务实际调用输出或数据库回读，`fake_*` 为 conftest 的可控替身，不是生产接口。测试方法仍需按各任务完整场景建夹具。

| 任务/关键测试 | 必须包含的断言示例 |
| --- | --- |
| T1 `test_invalid_preserves_decision` | `assert effective_state("pending", False) == "invalid"`；`assert after.management_state == "pending"` |
| T2 `test_delete_parent` | `assert after.directories[child_id].parent_id is None`；`assert after.assignments[disabled_key] == uncategorized_id` |
| T3 `test_batch_limit_atomic` | 在 `pytest.raises(CatalogConflict) as exc` 中调用，随后 `assert exc.value.reason == "RECOMMENDATION_LIMIT_EXCEEDED"`；`assert after.recommended_keys == before.recommended_keys` |
| T4 `test_401_items_all_pages` | `assert len(observation.items) == 401`；`assert observation.complete is True` |
| T5 `test_retry_budget` | `assert [plan_retry("timeout", n, 0, 0) for n in range(4)] == [10, 20, 40, None]`；`assert plan_retry("timeout", 0, 300, 0) is None` |
| T6 `test_published_draft_union` | `assert result["overview"] == {"current": 8, "published": 6, "draft_only": 2}` |
| T7 `test_default_migrate_has_no_initialization` | `assert fake_provider.call_count == 0`；`assert fake_dispatch.call_count == 0`；`assert catalog_rows_after == catalog_rows_before` |
| T8 `test_sort_two_groups_each_direction` | `assert [row["recommended"] for row in result] == [True, True, False, False]`，升/降两方向都成立 |
| T9 `test_old_node_allowed_new_same_plugin_rejected` | `assert [v.node_path for v in violations] == [new_node_path]` |
| T10 `test_batch_foreign_object_rejected` | `assert response.status_code == 403`；`assert state_after == state_before` |
| T11 `test_empty_automatic_uncategorized_not_pending` | `assert after.directory_id == uncategorized_id`；`assert after.management_state == "enabled"` |
| T12 `testSaveClearsUndo` | `assert.equal(saved.beforeAi, null)`；`assert.deepEqual(reduceEditor(saved, {type: 'UNDO_AI'}).document, saved.document)` |
| T13 `testPolicyCancelDoesNotSubmit` | `assert.equal(mockSavePolicy.callCount, 0)` |
| T14 `testNoDraftNoEditLink` | `assert.equal(buildReferenceTarget(noDraftRow, 'draft'), null)` |
| T15 `testVersionSameKeySameTypeRetainsBinding` | `assert.deepEqual(result.bindings, oldBindings)`；`assert.equal(result.values.sameKey, oldValues.sameKey)` |
| T16 故障恢复链路 | `assert recovered.management_state == "enabled"`；`assert recovered.recommended is True`；主动停用后 `assert disabled.recommended is False` |

`CatalogConflict` 在 T1 的 exceptions.py 定义，携带 reason/details；错误示例中的名字是模块业务原因，HTTP 对外 code 仍按项目注册方式转换。服务层用 raises 检查，接口层单独断言状态码和业务原因，不增加仅为测试存在的转换层。

| 设计范围 | 实现任务 | 验证证据 |
| --- | --- | --- |
| 身份、模型、权限与部署边界 | T1/T8/T10 | 身份隔离、Interface/Engine、租户/空间拒绝 |
| 两级目录与删除后去向 | T2/T12 | 转换与并发、完整编辑状态、实际页面 |
| 四状态、推荐、三策略 | T3/T5/T13 | 状态/推荐并发、所有新插件分支、Tab/策略页面 |
| 全来源、V2/V3、有限重试/恢复 | T4/T5 | 全分页、非 default、多展示同来源、时钟与晚到结果 |
| 独立手动初始化、新空间、旧 scope 例外 | T7 | migrate 无副作用、dry-run、断点重跑、集合对比 |
| 当前引用、CSV、旧 API 提示 | T6/T10/T14 | 全生命周期、仅草稿、未就绪、版本准确定位 |
| 新增保存、详情及运行例外 | T8/T9/T15 | 画布/网关、ID 重建、启动/调试、精确版本与权限 |
| AI 范围、撤销、分类来源 | T11/T12/T13 | 空/错/晚到、增量/自由、无审核副作用、bkaidev 独立联调 |
| 参数保留、替换与版本切换 | T15 | 同名/同 key 同类型、变量关联、旧值查看复制 |
| 发布与接口文档 | T6—T10/T16 | 同提交 APIGW 三项、初始化/回退手册、目标环境验收 |

实现交付时每项记录实际提交、测试命令/结果、未覆盖点；当前以上复选框均未执行。本轮完成的是计划与静态自查，不是实现验证。

### 保留的暂定、建议及联调依赖

| 项目 | 当前状态 | 影响范围 |
| --- | --- | --- |
| 第 6 项快捷目录/目标目录保存时机 | **暂定**，不自行改为最终规则 | T13 的快捷动作；T2/T12 整页保存不受影响 |
| 第 7 项批量启用逐项目录确认 | **暂定** | T13 EnableDialog 的交互验收；T3 数据载荷可先实现 |
| T13 联系字段、T17 替换字段文案 | 建议状态保留 | T14 展示/CSV、T13 文案 |
| bkaidev 实际环境、模型权限/协议样本 | 用户已选供应商及凭证，真实调用尚未验证 | T11 联调与 T16 E2E；不阻塞模拟客户端开发 |
| 第三方调用者主动重建节点 ID | SDK 入口未发现该行为，实际样本待查 | T9 兼容核验；发现实例再评审，不降低新增节点约束 |
| 企微 V2 旧 migrate 文案 | 最新确认已纳入本地设计/计划，本轮未回写在线文档 | 下次同步需改初始化、接口说明和验收中的相关表述 |
| TAPD 关联与执行方式 | 已核实「插件管理」需求 `--story=139209730`；尚未选择代码执行模式 | 文档可按本轮授权归档；代码实现仍需完成执行交接 |

自查记录：已逐项检查设计覆盖、上下游签名、任务顺序、五项重点风险、默认 migrate 无业务副作用以及第 6/7 项暂定状态。计划评审后再按选定方式执行，不自动创建实现线程或运行真实迁移。
