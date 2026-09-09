# BKFlow master 源码审查知识

整理基线：`27be93f8569cde84586360ca401972aedee57696`，目标分支：`master`。此文件描述该基线的真实路径与行为；审查时应结合当前 PR base/head 重新核对，不能将其他分支后来新增的能力直接当成本分支契约。

依赖基线来自 `requirements.txt`：`Django==3.2.25`；`celery==5.2.3`；`blueapps==4.15.8`；`bamboo-pipeline==3.29.10`；`bamboo-engine==2.11.4`。前端 Vue/画布 SDK 版本与锁文件以 `frontend/package.json` 为准。本分支另外提供 `npm run test:plugin-form`，具体覆盖范围按 package.json 中实际脚本判断。

## master 的实际功能边界

本分支包含子画布插件、Uniform API V4 和已有的插件表单兼容测试。子画布执行入口是 `bkflow/pipeline_plugins/components/collections/subcanvas_plugin/v1_0_0.py`：从父任务当前节点的 `pipeline` 取得子树，创建子任务，复制上下文并启动 `TaskOperation`；关联行为还需要阅读 `bkflow/pipeline_plugins/components/collections/subprocess_plugin/v1_0_0.py`。审查输入渲染、输出回填、父子任务归属、失败后重试时，应沿继承关系确认实际执行和调度行为。

`bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py` 与旧版本插件并存。修改空间配置、插件查询、凭据或表单时，同时检查 `bkflow/plugin/space_plugin_config_parser.py`、`bkflow/pipeline_plugins/query/uniform_api/uniform_api.py` 和 `frontend/package.json` 中的插件兼容测试，不能把已有流程统一解释成最新版本的输入结构。

## 服务边界与部署

BKFlow 提供流程模板管理、API 接入、画布交互及任务执行服务，和 bkflow-sdk 客户端、bamboo-engine 底层引擎分别维护。`module_settings.py` 按 BKFLOW_MODULE_TYPE 选择 interface/engine 的应用、鉴权、中间件、队列和定时任务。interface 管理模板、空间、权限、网关等，engine 加载任务、pipeline 运行时和插件；资源隔离还区分 only_calculation 与 all_resource，后者可为 engine 配置独立数据库。分析 import、信号、ORM 和迁移时，先判断应用在哪个模块加载。

`bkflow/contrib/api/collections/task.py` 的 TaskComponentClient 根据 space_id 查 ModuleInfo，并可回退默认模块配置；发送内部 token、空间和 from_superuser 请求头。`bkflow/contrib/api/collections/interface.py` 的 InterfaceModuleClient 承接 engine 到 interface 的内部 API，使用独立内部 token。`bkflow/contrib/api/client.py` 与 `bkflow/contrib/api/http.py` 是传输基础。涉及跨模块数据时，沿客户端、URL、服务端视图和异常/返回值处理核对，不要假定两侧 ORM 共用同一数据库。

## 身份、空间与权限

网关入口主要在 `bkflow/apigw/urls.py` 和 `bkflow/apigw/decorators.py`，模板/空间 API 的权限分别在 `bkflow/template/permissions.py` 与 `bkflow/space/permissions.py`。`bkflow/permission/middleware.py` 将 BKFLOW-TOKEN 请求头放入 request.token，具体校验在 `bkflow/permission/permissions.py`、`bkflow/permission/models.py`。本分支已使用 Token 主票据和 TokenGrant 授权明细。主票据存储 space_id、user、expired_time、grant_set_hash；单项与组合授权统一从 TokenGrant 读取，主表已移除 resource_type/resource_id/permission_type 旧列。不能将其他开发分支的旧 Token ORM 字段当作当前接口。

权限审查需要分别核对外层网关/登录身份、DRF 权限类及其 OR 组合、对象权限、空间/scope 过滤、下游任务归属。OR 组合仅代表该处权限类的组合语义，不代表整个调用链任意一层成功即可放行。内部管理/模块接口可以使用 AdminPermission | AppInternalPermission；是否需要 ScopePermission 取决于实际消费方与接口契约，不能对所有内部接口强行增加 scope token。

Token 的用户名、空间、有效期与完整授权集合先行校验，再由同一条明细的资源类型/ID、permission_type 及资源关系满足授权；不能跨明细拼接资源和操作。模板、scope、任务和 mock 相关权限应阅读具体分支实现。新增 action 必须核对 action 分类、get_queryset、has_permission/has_object_permission 的真实执行关系，不能仅因为详情接口有对象校验就推断列表或自定义 action 已覆盖。

## 当前 TokenGrant 与兼容边界

`bkflow/permission/grants.py` 规范化完整授权三元组并计算单项/集合摘要，`bkflow/permission/models.py` 的 get_grants 校验全部明细的字段、唯一性、单项摘要和集合摘要，异常时拒绝整张票据。TokenPermissionType 的 VIEW/EDIT/OPERATE/MOCK 与 TaskAuthCode 的 FLOW_* 展示标记分别定义，展示标记不能作为新增可签发权限。

`bkflow/permission/services.py` 的 issue_token、renew_token、revoke_tokens 通过事务和主票据行锁处理签发复用、续期、撤销；get_valid_token 绑定用户/空间/有效期，并只在同一 request 对象内缓存。审查并发时必须结合实际锁顺序、持锁后重查和查询过滤，不因存在事务就断言所有并发情况已验证。`bkflow/permission/resource_matching.py` 沿任务父链匹配祖先并对重复节点终止，scope 匹配区分实际 TEMPLATE/TASK 目标类型；组合票据省略目标类型时拒绝，部分旧单项内部调用保留回退。

`bkflow/apigw/serializers/token.py` 和 `bkflow/apigw/views/apply_token.py` 保留旧单项请求及新的 grants 请求分流，签发前验证资源。`bkflow/permission/migrations/0006_backfill_token_grants.py` 回填旧单项并验证集合，`bkflow/permission/migrations/0007_auto_20260909_1521.py` 移除旧资源三列；审查迁移必须考虑旧行、损坏明细、前置依赖和正反迁移，不能建议直接把旧 ORM 三元组写回主表。

相关测试在 `tests/interface/permission/test_grants.py`、`tests/interface/permission/test_composite_permissions.py`、`tests/interface/permission/test_lifecycle.py`、`tests/interface/permission/test_unified_migrations.py` 和 `tests/interface/apigw/test_composite_token.py`。`tests/interface/permission/test_mysql_lifecycle.py` 使用真实 MySQL 两连接/行锁，非 MySQL 会跳过；跳过不是并发验证通过。本文件记录源码契约，不宣称已经执行这些应用测试。

## 模板、流程协议与任务运行

`bkflow/template/views/template.py`、`bkflow/template/serializers/template.py` 和 `bkflow/template/models.py` 处理模板、流程树与快照；`bkflow/task/serializers.py`、`bkflow/task/models.py`、`bkflow/task/operations.py`、`bkflow/task/views.py` 处理任务输入、持久化、运行操作与查询。模板编辑树、快照、任务保存的树以及引擎上下文处于不同阶段，不能把某个阶段的字段校验或权限校验自动推及其他阶段。

`bkflow/apigw/views/validate_a2flow.py` 与 `bkflow/apigw/views/create_template_with_a2flow.py` 提供校验/导入入口，`bkflow/apigw/serializers/a2flow.py` 处理请求结构；`bkflow/utils/a2flow.py` 与 `bkflow/pipeline_converter/converters/a2flow_v2/converter.py` 负责对应转换实现。判断转换行为须核对 v1/v2 的版本路由、插件解析、变量和网关生成以及最后实际保存/提交的树，不能只根据 serializer 或转换器单测判断 API 全链路。

任务操作应结合 TaskOperation 与运行时返回值分析。启动、重试、回调、跳过、撤销具有不同前置状态和副作用；注意重复请求、父子任务关系、节点 ID 与引擎 ID、输出数据和结束时间。发生失败时，需区分接口失败、业务 result=False、引擎状态、异步调度/回调，不能将 HTTP 成功或一个本地对象更新等同于任务完成。

## API、数据与兼容性

网关资源定义位于 `bkflow/apigw/management/commands/data/api-resources.yml`，中文接口文档在 `bkflow/apigw/docs/zh`，发布文档包为 `bkflow/apigw/docs/apigw-docs.zip`，打包脚本为 `scripts/apigw_docs.sh`。新增或改变路径、参数、返回码/结构、认证要求时核对相关同步项；内部实现重构不当然需要新增网关资源。

空间配置与凭据由 `bkflow/space/configs.py`、`bkflow/space/models.py`、`bkflow/space/serializers.py` 等管理。审查默认值、空值、密文回显、配置合并、scope 选择及执行端取值时，区分管理展示与任务运行真正消费的数据。数据模型变化需考虑本分支迁移依赖、既有行、回滚以及 interface/engine 是否分别安装该应用，不能默认所有分支都已经完成同一轮迁移。

插件 code/version、模板快照及已创建任务是兼容性边界。修复新版本插件或新表单时，需要确认旧组件版本、旧存量 JSON、旧调用方参数和错误格式的影响；不要为了统一格式静默更改已有流程运行语义。

## 测试与证据范围

后端环境和依赖以 `requirements.txt`、`tests/requirements_test.txt`、`tests/interface.env`、`tests/engine.env` 为准。常规入口是 `bash scripts/run_interface_unit_test.sh` 与 `bash scripts/run_engine_unit_test.sh`，它们选择不同模块和测试目录，需要相应数据库/服务环境。可按改动聚焦 `tests/interface/template/test_template_views.py`、`tests/interface/task/test_task_views.py`、`tests/interface/space/test_space_views.py`、`tests/interface/utils/test_a2flow_converter.py`、`tests/engine/task/test_task_views.py`；测试名称存在不代表覆盖每个入口或外部行为。

前端在 frontend 目录按锁文件准备依赖，可执行 `npm run lint` 和 `npm run build`。是否有额外专项测试、具体测试文件及版本，以该分支 `frontend/package.json` 为准。依赖安装受内部包源约束时应记录限制，不能通过删除生产依赖来宣称完整安装通过。

本知识文件是源码导航和审查背景，不是现存缺陷清单，也不构成测试通过或发布验收结论。报告应区分静态分析、本地测试、GitHub Actions、部署 SHA、网关同步、外部依赖/浏览器真实操作及业务验收；无运行证据时明确需要什么验证，不能把历史事故当成本次回归。

## 只读源码快照的阅读边界

本轮可信背景仅来自 Base SHA 的本知识文件和审查规则；旧项目规范的安全、查询、职责分离、异步任务和兼容性要求已整理进规则，不要求加载 head 的 AGENTS 或其他 Agent 配置。`module_settings.py` 的实际 interface/engine 分支是部署依据，旧标准中的 pipeline 模块、MODULE_APPS 或空模块示例不能代替源码。

模型可用 Read/Glob/Grep 阅读 head 的普通文件快照及完整 diff，不能执行本文列出的测试/构建命令。快照会排除 Agent 控制文件、符号链接和超出单文件大小上限的资料；本分支的 `frontend/src/assets/js/flow.js` 与 `frontend/package-lock.json` 会被过滤。即使 diff 包含相关改动，也不能据此声称已阅读完整文件或验证依赖解析；需要完整前后文时在 limitations 中明确。压缩包、图片及 wheel 的存在不证明已验证内部实现，特别是 `bkflow/apigw/docs/apigw-docs.zip` 应结合保留的 Markdown 文档和打包脚本判断，不能宣称已运行发布验收。
