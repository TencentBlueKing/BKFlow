# 组合 Token Implementation Plan（历史实施记录）

> 本计划中的 HTTP、错误、鉴权和生命周期任务已经完成；原双存储与免回填步骤已废止，不应重新执行。当前存储、迁移、回退及最终交付以[统一存储计划](2026-09-09-unified-token-storage.md)为准。

**Goal:** 在现有 apply_token 中提供组合申请，保持旧客户端协议，并对完整票据执行鉴权、续期与撤销。

**Architecture:** 单项与多项授权统一存入 TokenGrant；纯授权值对象负责规范化，模型负责存储读取，服务负责签发与生命周期，资源匹配器保留模板/任务/scope 语义。所有 Token 消费入口统一使用主票据有效性与授权读取能力。

**Tech Stack:** Python 3.9、Django 3.2、DRF、pytest-django、MySQL 8.0、SQLite 快速回归。

**Spec:** [组合 Token 协议设计](../specs/2026-09-09-composite-token-design.md)；存储以[统一存储设计](../specs/2026-09-09-unified-token-storage-design.md)为准。

**进度（2026-09-09）：** Tasks 1–5 的原协议与组合能力已实现并完成当时的本地验证；随后统一存储实现追加 `permission.0006`/`0007`，当前验证结果记录在统一存储计划。外部审查、推送、TAPD 和新提交 CI 状态以 [PR #913](https://github.com/TencentBlueKing/BKFlow/pull/913) 的实时结果为准；本计划不表示已部署或启用。

## Global Constraints

- 不新增接口，兼容旧版单项申请以及所有已有接口协议。
- 第一版按整张票据撤销：撤销条件命中一项授权，就使该票据的全部授权失效。
- `grants` 必须为非空列表，原始条目数最多 32，先检查条目数再去重。
- 所有单项和多项票据都从 `TokenGrant` 读取授权；主表 `grant_set_hash` 非空并校验完整集合。
- `Token` 不再保存 `resource_type`、`resource_id`、`permission_type`，也不提供生产 ORM 兼容写入。
- 单项摘要输入为 `['v1', resource_type, resource_id, permission_type]`，集合摘要输入为 `['v1', 排序后的三元组数组]`；统一采用无额外空白、ASCII 转义的 JSON，再按 UTF-8 编码计算摘要。
- 新增服务配置 `TOKEN_COMPOSITE_ENABLED`，默认关闭，只控制 grants 格式的申请入口。
- 旧响应不增加 grants、permission_type、grant_set_hash；请求出现任意旧字段时仍按旧序列化器处理并忽略额外 grants。
- `permission.0006` 自动回填旧记录，`permission.0007` 清理旧字段；结构迁移必须通过 Django makemigrations 生成，不手写或修改已有 migration。
- 沿用隔离工作区 `.worktrees/docs-token-authorization` 和分支 `ai/docs-token-authorization`，不修改主工作区用户文件。
- 同任务提交使用 `--story=138057563`；精确暂存任务文件，不使用 git add .；不推 upstream，不合并 PR。
- 原 origin URL 含认证信息，不输出 remote URL；push 输出必须脱敏。
- 本计划保留当时的 RED/GREEN 和 MySQL 证据；当前结果以统一存储计划和任务报告为准。

## 文件责任与测试命令

| 文件 | 职责 |
| --- | --- |
| `bkflow/permission/grants.py` | 不依赖 Django 的不可变授权值、排序去重与摘要 |
| `bkflow/permission/models.py` | TokenGrant、主表摘要、权威授权读取与已有模型接口适配 |
| `bkflow/permission/services.py` | 原子签发/复用、续期、撤销与请求票据读取 |
| `bkflow/permission/resource_matching.py` | 完整授权与模板、任务祖先、scope 的匹配 |
| `bkflow/apigw/serializers/token.py`、`views/apply_token.py`、`views/revoke_token.py` | 原协议包装及新输入适配 |
| `bkflow/permission/permissions.py`、各资源权限类与 auth 汇总 | 消费上述能力，保留动作语义 |
| `tests/interface/permission/` | 授权读取、生命周期、资源匹配、辅助入口和 MySQL 并发测试 |
| `tests/interface/apigw/test_composite_token.py` | 旧/新申请、撤销协议及端到端行为 |
| `bkflow/apigw/docs/`、网关资源 YAML、Token 指南 | 接入说明与 Schema 一致性 |

以下命令是历史实施时使用的快速测试入口；当前交付请使用统一存储计划中的独立迁移/MySQL入口和完整 interface 脚本：

```bash
direnv exec /Users/dengyh/Projects/bk-flow env PYTHONPATH=/tmp:$PWD PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 BKFLOW_MODULE_TYPE=interface BKFLOW_MODULE_CODE=interface python -m pytest -p django -p no:warnings -o addopts='' --ds=bkflow_token_refactor_test_settings --nomigrations -q --tb=short
```

MySQL 证据来自控制者准备的专用本地实例，未连接业务库；迁移与并发测试不能加 `--nomigrations`。

### Task 1: 授权存储与完整性

**Files:**
- Create: `bkflow/permission/grants.py`, `tests/interface/permission/__init__.py`, `tests/interface/permission/test_grants.py`
- Modify: `bkflow/permission/models.py`
- Generate: permission 应用的下一份迁移

**Interfaces:**
- Produces: `Grant(resource_type: str, resource_id: str, permission_type: str)`，frozen/order dataclass，`as_dict() -> dict`。
- Produces: `canonical_grants(grants: Iterable[Grant]) -> tuple[Grant, ...]`, `grant_hash(grant: Grant) -> str`, `grant_set_hash(grants: Iterable[Grant]) -> str`。
- Produces: `Token.is_composite` property、`Token.get_grants() -> tuple[Grant, ...]`；完整性错误返回空 tuple，不抛出开放权限的回退异常。
- Produces: `TokenGrant`，外键 related_name=`grants`，字段与唯一约束按 spec §3；新增主表可空 grant_set_hash 和两个查询索引。

- [x] Step 1：写出运行时失败的历史票据读取、去重/顺序复用、组合明细完整性测试。使用函数内 import 避免模块不存在导致收集失败。关键用例：

```python
def test_legacy_grant_keeps_resource_identity(db):
    from bkflow.permission.models import Token
    token = Token.objects.create(token='legacy', space_id=1, user='alice', resource_type='TEMPLATE',
                                 resource_id='001', permission_type='MOCK', expired_time=timezone.now())
    assert [g.as_dict() for g in token.get_grants()] == [
        {'resource_type': 'TEMPLATE', 'resource_id': '001', 'permission_type': 'MOCK'}]
```

补齐组合缺明细、只有一条、错误单项摘要、错误集合摘要、原字段填有值不作为额外授权、级联删除与重复摘要约束。预期文字与列表用手写值，不用待测函数生成 expected。

- [x] Step 2：运行 `tests/interface/permission/test_grants.py`，记录缺少方法/行为的失败。
- [x] Step 3：实现纯值对象及摘要，再实现新增模型与读取规则：

```python
@dataclass(frozen=True, order=True)
class Grant:
    resource_type: str
    resource_id: str
    permission_type: str

def canonical_grants(grants):
    return tuple(sorted(set(grants)))

def grant_hash(grant):
    payload = ['v1', grant.resource_type, grant.resource_id, grant.permission_type]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()
```

`get_grants()` 对单项直接构造一项；组合检查至少两条、合法字段/枚举、每项摘要、集合摘要和去重数量，任何不一致返回空集合。不要实现签发 API 或改动消费者。

- [x] Step 4：以项目环境运行 `manage.py makemigrations permission --settings=bkflow_token_refactor_test_settings` 自动生成迁移；运行本任务测试与既有 94 个回归，确认旧协议仍通过。
- [x] Step 5：运行变更文件 Black/isort/Flake8 与 diff check，精确暂存并提交 `feat(permission): 增加组合票据授权存储 --story=138057563`。

### Task 2: 签发、撤销和续期服务

**Files:**
- Create: `bkflow/permission/services.py`, `tests/interface/permission/test_lifecycle.py`
- Modify: `bkflow/permission/models.py`, `bkflow/permission/views.py`

**Interfaces:**
- Consumes: Task 1 的 Grant、摘要及 get_grants。
- Produces: `issue_token(space_id, user, grants, expiration_seconds, auto_renewal) -> Token`，grants 为已校验的 Grant 序列。
- Produces: `renew_token(token_id, user=None) -> tuple[bool, str, Token|None]`，锁定主表，检查当前有效期与空间配置，再更新。
- Produces: `revoke_tokens(space_id, filters: dict) -> int`，返回不同主票据的匹配更新数。
- Produces: `get_valid_token(token_id, user, space_id=None, request=None) -> Token|None`，绑定身份/空间，验证有效期与授权完整性；request 存在时仅在该请求内缓存读取结果。

- [x] Step 1：先写服务签发/复用/事务回滚测试与撤销后模型 renewal 不能恢复的失败测试。资源三元组不要模拟；数据库事务、模型和真实 queryset 必须参与测试。

```python
def test_revoke_by_one_grant_expires_whole_token(db):
    from bkflow.permission.grants import Grant
    from bkflow.permission.services import issue_token, revoke_tokens
    token = issue_token(1, 'alice', [Grant('TEMPLATE', '100', 'MOCK'), Grant('TASK', '200', 'OPERATE')], 3600, False)
    assert revoke_tokens(1, {'resource_type': 'TEMPLATE', 'resource_id': '100'}) == 1
    token.refresh_from_db()
    assert token.has_expired()
```

补齐所有过滤条件命中同一明细、空过滤、token/user/space AND、重复明细匹配只计一张、过期记录计数、单项不复用组合、摘要候选需比较完整集合、缺明细票据不能续期、撤销/续期两种先后顺序。

- [x] Step 2：运行 `tests/interface/permission/test_lifecycle.py`，记录预期失败。
- [x] Step 3：实现服务。旧单项按旧三元组复用；组合按同用户同空间摘要候选，再比较完整集合。新建主票据与 bulk_create 明细置于同一 atomic 事务中，不在此服务做外部资源查询。

```python
with transaction.atomic():
    token = Token.objects.select_for_update().filter(pk=token_id).first()
    now = timezone.now()
    if token is None or token.expired_time <= now:
        return False, 'Token 已过期或不存在', token
    # 在持锁状态继续检查用户、授权完整性与配置，成功时保存 expired_time。
```

候选发现采用普通查询，签发复用与撤销统一使用仅含 `pk__in` 条件、按 `pk` 排序的批量主行锁查询，避免有效期二级索引与主行锁反序；持锁后重新核对条件，复用仍按最新过期时间优先。撤销使用主票据行锁或等价原子更新；资源条件必须在同一条明细上求 AND；只含主字段的撤销不依赖明细完整性，以便清除损坏票据。缓存不得跨请求或让先前缓存的到期时间绕过续期持锁重检。`Token.renewal()` 保持返回二元组并同步 self.expired_time；TokenViewSet 改为每次查询使用当前时间，正常响应包装不变。

- [x] Step 4：运行 lifecycle + grants + 原 apply_token 测试。迁移文件不能被手动改写。
- [x] Step 5：格式检查并提交 `feat(permission): 实现组合票据生命周期 --story=138057563`。

### Task 3: 同一路由的组合申请与旧协议

**Files:**
- Create: `tests/interface/apigw/test_composite_token.py`
- Modify: `bkflow/apigw/serializers/token.py`, `bkflow/apigw/views/apply_token.py`, `bkflow/apigw/views/revoke_token.py`, `env.py`, `config/default.py`

**Interfaces:**
- Consumes: issue_token、revoke_tokens 和 Grant。
- Produces: 同一个 apply_token 根据旧字段优先规则分派；grants 格式有独立序列化器，TOKEN_COMPOSITE_ENABLED 默认 false，环境变量 `BKAPP_TOKEN_COMPOSITE_ENABLED` 控制。
- Produces: 旧成功数据字段集合不变；新格式返回公共字段和 grants；revoke 输入和输出不变。

- [x] Step 1：先写 Django client 层测试。创建真实 Space/Template；任务不存在性在 engine 客户端边界提供具体返回；不 mock TokenResourceValidator.validate。沿用现有测试的网关认证替身。

```python
payload = {'resource_type': 'TEMPLATE', 'resource_id': str(template.id), 'permission_type': 'MOCK',
           'grants': [{'resource_type': 'TASK', 'resource_id': '200', 'permission_type': 'OPERATE'}]}
response = client.post(f'/apigw/space/{space.id}/apply_token/', data=json.dumps(payload), content_type='application/json')
assert set(response.json()['data']) == {'token', 'space_id', 'user', 'resource_type', 'resource_id', 'expired_time'}
```

覆盖旧额外字段/缺参/数字 ID/旧 choices、grants 开关、空/null/33 项、非法 FLOW_*/LABEL、资源失败无写入/无续期、顺序去重复用、单项新响应、多项一个 token、事务回滚及整票据撤销协议。

- [x] Step 2：先运行现有旧协议断言建立基线，再启用新增组合测试得到预期失败。
- [x] Step 3：输入分派保持如下语义，旧序列化器自身不改必填规则：

```python
legacy_keys = {'resource_type', 'resource_id', 'permission_type'}
is_composite_request = isinstance(data, dict) and not (legacy_keys & data.keys()) and 'grants' in data
serializer = CompositeTokenSerializer(data=data) if is_composite_request else ApiGwTokenSerializer(data=data)
serializer.is_valid(raise_exception=True)
```

非 object 的 JSON 继续交给旧序列化器返回原参数错误，不能在分派时触发属性异常。列表先验证长度再逐项；外部资源校验先全部完成，再调用 issue_token。新格式失败在错误中标明索引。返回格式取决于请求形式，不取决于去重后的存储模式。关闭开关只禁 grants 申请，不限制已签发票据的消费。

- [x] Step 4：运行 `test_composite_token.py`、`test_apply_token.py`、`test_token_permission_types.py`、`test_token_resource_validator.py` 及 lifecycle。旧路由与装饰器、HTTP 包装、空 revoke 的空间范围必须保留。
- [x] Step 5：提交 `feat(apigw): 在原接口支持组合票据申请 --story=138057563`；网关文档同步由 Task 5 在整 PR 交付前完成。

### Task 4: 资源鉴权与全部消费入口

**Files:**
- Create: `bkflow/permission/resource_matching.py`, `tests/interface/permission/test_composite_permissions.py`
- Modify: `bkflow/permission/models.py`, `bkflow/permission/permissions.py`, `bkflow/interface/task/permissions.py`, `bkflow/template/permissions.py`, `bkflow/interface/task/view.py`, `bkflow/template/serializers/template.py`, `bkflow/decision_table/permissions.py`, `bkflow/plugin/permissions.py`, `bkflow/pipeline_plugins/query/uniform_api/utils.py`, `bkflow/permission/admin.py`, `tests/interface/plugin/test_plugin_detail_view.py`, `tests/interface/task/test_task_permissions.py`

**Interfaces:**
- Consumes: get_valid_token、get_grants、Grant。
- Produces: `matches_resource(grant, space_id, resource_id, target_resource_type=None, is_composite=False) -> bool`。
- Produces: `Token.verify` 保持旧参数，新增可选 target_resource_type/request；BaseTokenPermission 各操作方法可增加可选 request，仓库调用方明确传递。
- Produces: `Token.objects.get_resource_tokens(token_id, resource_params, user=None, space_id=None) -> QuerySet`；HTTP 调用者必须传入身份与可信空间。
- Produces: `iter_user_grants(space_id, user, resource_selectors) -> Iterator[Grant]`，放入 services，资源 selectors 为一组 `(resource_type, resource_id)`。

- [x] Step 1：写相同 token 在模板和任务上分别允许、交叉组合拒绝的测试，断言 permission class 的真实返回结果。仅在 engine API 边界设置按 task_id 区分的具体返回。

```python
assert Token.verify(1, 'alice', 'TEMPLATE', '100', 'MOCK', token.token)
assert Token.verify(1, 'alice', 'TASK', '200', 'OPERATE', token.token)
assert not Token.verify(1, 'alice', 'TEMPLATE', '100', 'OPERATE', token.token)
assert not Token.verify(1, 'alice', 'TASK', '200', 'MOCK', token.token)
```

覆盖 task/template 同 ID 的 scope 匹配、父子任务方向与循环失败、MOCK 任务限定、用户/空间/有效期/摘要损坏、决策表与 Uniform API 全路径、主字段不能泄漏额外授权、旧与组合 auth 去重、管理员固定数组。

- [x] Step 2：运行新增测试记录拒绝新组合或旧辅助路径错误放行的失败。
- [x] Step 3：模型 verify 先 get_valid_token，再 any 一条完整授权匹配；不能独立取三个字段的集合。scope 明确目标资源类型，新组合缺目标类型时拒绝该分支。保持旧单项无目标类型内部调用的原回退顺序。

```python
return any(
    g.resource_type == resource_type and g.permission_type == permission_type
    and matches_resource(g, token.space_id, resource_id, target_resource_type, token.is_composite)
    for g in token.get_grants()
)
```

辅助消费者统一验证主票据身份与空间；资源动作规则保留。auth 对有效完整授权汇总，FLOW_* 映射和非标准历史前缀不变。PluginTokenPermissions 仍提供空间级能力；Uniform API 保持 template_id 优先，返回 QuerySet 且不重复票据。管理界面展示只读明细，禁止通过新增 inline 绕过不可追加授权的约定。

- [x] Step 4：运行 composite_permissions、现有 task/template/debug/plugin/decision_table 相关测试；检查所有直接 Token.objects/resource 字段消费者均已按用途适配。
- [x] Step 5：提交 `feat(permission): 接入组合票据鉴权与权限展示 --story=138057563`。

### Task 5: MySQL 验收、协议文档与发布检查

**Files:**
- Create: `tests/interface/permission/test_mysql_lifecycle.py`
- Modify: `bkflow/permission/services.py`（真实 MySQL 死锁修复）、`tests/interface/permission/test_grants.py`（Unicode 摘要黄金值）、`bkflow/apigw/docs/zh/apply_token.md`, `bkflow/apigw/docs/zh/revoke_token.md`, `docs/guide/token_authorization.md`, `bkflow/apigw/management/commands/data/api-resources.yml`, 本计划与设计的进度状态
- Generate: `bkflow/apigw/docs/apigw-docs.zip`

**Interfaces:**
- Consumes: 前四项全部已实现接口；MySQL 配置由控制者在 /tmp 准备，专用本地数据库。
- Produces: 真实 MySQL 两连接撤销/续期测试、迁移验证证据、文档/Schema 与实现一致。

- [x] Step 1：编写只在 connection.vendor == 'mysql' 下执行的 transaction 测试，用两条真实连接、threading.Event 和有限超时安排锁竞争。先持有主行锁，让另一连接开始续期，持锁连接撤销后提交，断言另一连接续期失败且最终 expiry 不在未来；反向顺序验证后发生的撤销覆盖续期。

```python
with transaction.atomic():
    locked = Token.objects.select_for_update().get(pk=token.pk)
    worker.start()
    assert started.wait(5)
    locked.expired_time = timezone.now()
    locked.save(update_fields=['expired_time'])
worker.join(10)
assert not worker.is_alive()
token.refresh_from_db()
assert token.has_expired()
```

线程入口单独创建/关闭数据库连接并回传异常；不得吞掉线程错误。完整用例通过 `performance_schema.data_lock_waits/data_locks` 验证 worker 在最小主键 PRIMARY 上等待本连接，等待前未持有其他主行/二级记录锁，并断言未完成；不以固定 sleep 假装竞争。另覆盖旧/组合、单/多等价候选、token/资源过滤、申请复用与撤销两个顺序及并发同集合票据各自完整。

- [x] Step 2：运行 MySQL 测试与真实迁移；验证旧记录在 schema upgrade 后可读，新增摘要/明细约束、case-distinct 三元组、事务回滚和级联。证据必须来自 MySQL，不把 SQLite 跳过当通过。
- [x] Step 3：文档新增两种请求/响应、混合旧字段优先、32 项限制、开关默认关闭、单项复用、整票据撤销计数、时序修正与上线回退。网关只修改现有两个 operation 的 Schema，不新增 path、operationId 或认证设置。

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        additionalProperties: true
```

在此 object 下完整表达两种合法输入分支与旧字段优先，响应旧字段与 grants 分支分开。不安装/启用网关请求校验插件。

- [x] Step 4：运行 `bash scripts/apigw_docs.sh`，检查 zip 内容逐项与源文件一致；解析 Markdown 相对链接和 JSON 示例；完整相关 Python 回归、Django check、migration drift、Black/isort/Flake8、git diff --check。
- [x] Step 5：提交 `fix(permission): 修复票据并发死锁并完善接入说明 --story=138057563`，记录实际命令和结果。本地提交只包含精确任务文件。

外部交付记录：独立审查、推送、PR/CI 结果及 TAPD 关联状态以 [PR #913](https://github.com/TencentBlueKing/BKFlow/pull/913) 的实时记录为准；部署版本与启用状态需由对应环境验收确认。

## 最终覆盖检查

本表保留原组合能力的覆盖关系：Spec §1/4/5 → Task 3；§3 → Task 1；§7/8 → Task 2、5；§2/6/9 → Task 4；§10 → Task 3、4、5；§11/12/13 → Task 5。统一迁移及最终交付状态见[统一存储计划](2026-09-09-unified-token-storage.md)和 [PR #913](https://github.com/TencentBlueKing/BKFlow/pull/913)。


## 本地验证台账（2026-09-09）

- Tasks 1–4 的 RED/GREEN 与独立审查记录由任务报告保留；Task 4 MySQL 消费/Token 回归 693 通过，额外 Label 回归 52 通过；续期默认时区 JSON 修正已单独验证。
- Task 5 初次真实竞争 4 通过、1 失败，暴露申请复用与撤销的 MySQL 1213 死锁。InnoDB 等待图确认二级有效期索引与 PRIMARY 锁反序；在批准范围内修正候选发现与批量主行锁方式。修正后锁专项/生命周期/摘要 68 通过。
- Task 5 首轮相关 MySQL 8.0.46 门禁 **760 通过，88.97 秒**，包含新旧存储、12 个 MySQL 专项（真实等待图、两个顺序、多候选、并发重复票据完整、case-distinct）、约束/回滚/级联、Unicode 黄金摘要和续期 JSON 兼容；启用完整迁移，非 SQLite 跳过。
- 最终审查统一修复轮：恢复整数空间 ID 的前导零兼容（缓存、鉴权及复用），资源 ID 字符串身份不变；新增 8 例先得到 6 失败/2 通过，修复后 8 通过。更新 scope 说明、HTTP 200 原错误包装 Schema 及撤销 ID 过滤说明后，一次完整相关 MySQL 门禁 **768 通过，89.14 秒**；实际 apply/revoke 的 HTTP 200/code 400 和 500 错误响应均通过 Schema 校验。
- 本段记录的是统一存储前的历史门禁；当前 `0004/0005` 旧记录由 `permission.0006` 自动回填，再由 `permission.0007` 清理主表旧字段，实际结果以统一存储迁移测试为准。
- Django check 退出 0，保留已有 `label.Label.label_scope` JSONField 默认值警告。permission migration drift 检查通过；全项目 drift 检查退出 1，报告无关 space/template 枚举字段漂移（控制者分别独立导出 Task 5 基线 cafd0df0 和原 PR 基线 032d59aa 实跑，两段漂移与当前逐字相同），未生成迁移。
- 102 个网关 operation 的 path/method/backend/auth/plugin 设置均与基线一致，只改已有 apply/revoke 的请求/响应 Schema。92 个文档包文件逐字节匹配源码，规范化内容只改变两份 Token 文档。Markdown 相对链接、JSON 示例、Schema 分支及格式检查完成。

这些结果仅为本地证据；外部交付状态以 [PR #913](https://github.com/TencentBlueKing/BKFlow/pull/913) 的实时结果为准，不据提交时快照推断 CI、发布或启用状态。
