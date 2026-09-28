# a2flow P0–P4 同步 master 验证记录

日期：2026-09-28。结论：代码已在新分支集成，本地 P4 门禁通过；不是生产发布批准。

## 分支与范围

- 新分支：`ai/a2flow-harness-master-sync`。
- 基线：`upstream/master`，`81c33bb099e25d7a9e4da6780ff6fb63c057fa80`；收尾时重新查询远端，仍为此提交。
- 功能来源：脱敏累计快照 `f7d895710a57ed1514813eeaa92737f6ba320254`，包含原 P0–P4 实现。
- 使用独立、原本干净的 worktree，不覆盖主工作区的用户改动。
- 原 P0–P4 分支、发布快照和远端 PR 未重写。本次仅生成本地集成提交，不推送、不发布、不启用任何 Harness 开关。

## 必要适配

1. **统一 Token 模型**：保留 master 的 `Token + TokenGrant` 和组合授权 API。旧 Harness 的 `permission/services/` 会遮蔽 master 的 `permission/services.py`，故将专用签发器移动为 `permission/token_issuer.py`。签发、复用与 Broker 回读使用完整授权集合摘要和明细一致性校验，不能复用权限更宽或明细损坏的票据。生命周期写入沿用主票据主键加锁顺序。
2. **租户边界**：Harness 自定义权限在应用归属、管理员和开关之外，校验认证应用选择的租户、认证用户租户与空间租户一致；鉴权豁免不能绕过租户约束。
3. **任务创建**：提取后的 TaskCreator 保留 master 的空间 `tenant_id` 下传，并在下发 Engine 前校验所选快照的子流程空间归属。旧 API 与 Harness 发布快照入口都覆盖此路径。
4. **传输层兼容**：合并 Harness 的敏感日志脱敏与 master 的错误分类、可重试标记和状态码，保留两侧调用者需要的返回字段。
5. **迁移图**：通过 Django 自动生成 Space 双分支合并迁移及最终字段状态迁移；没有手工改写历史迁移。
6. **网关与文档**：结构化比较确认 master 的 104 个操作定义原样保留，仅增加 15 个 Harness 操作。新操作补充租户请求头，中文文档同步，文档压缩包由仓库脚本重建。
7. **测试兼容**：修正旧 mock 路径、测试包同名冲突、跨模块 fixture 的收集顺序依赖、TokenGrant 测试夹具及新校验器下的子流程夹具。Golden provider 在进入失败时释放 mock，避免污染后续测试。

## 已完成验证

测试使用显式构造的临时配置，没有加载个人开发 `.env`，没有连接现有数据库或线上服务。数据库、缓存和消息配置均隔离；依赖覆盖安装在临时目录，未升级共享虚拟环境。

| 检查 | 结果及边界 |
| --- | --- |
| `make harness-p4-gate` | **2146 passed, 8 skipped**；SQLite，45.57 秒。8 项为真实双连接行锁验证，不代表 MySQL 验收 |
| 新增及受影响的兼容回归 | **245 passed**；覆盖租户引用、Token 签发、任务创建、权限、网关契约、HTTP 分类和 fixture 隔离 |
| Engine / plugin_service 回归 | **680 passed**；排除了需要实际 Celery worker 的 `tests/engine/pipeline_execution` |
| MySQL 8 Token 生命周期与迁移专项 | **21 passed**；使用临时 **utf8** 测试库，只用于补充诊断，不替代 utf8mb4 发布验证 |
| 发布/项目设置测试 | 探索性整套测试中的 **44 项全部通过**；master 发布脚本及依赖声明原样保留 |
| `makemigrations harness space --check --dry-run` | 无模型迁移漂移 |
| 网关结构与压缩包 | 104 个既有操作不变 + 15 个新操作；203 个中英文文档文件与压缩包内容逐一一致，归档完整性通过 |
| 静态检查 | 变更 Python 文件通过 Black 22.3.0、isort 5.13.2、flake8；`git diff --check` 通过 |

`manage.py check` 仍提示 master 已有的 `Label.label_scope` JSONField 默认值警告。
全项目迁移漂移检查还提示 `TemplateOperationRecord.operate_type` 的 choices 迁移；该模型字段、枚举和对应历史迁移在 master 已存在同样状态，本次未将其混入 Harness 迁移。

## 发布阻塞与未完成项

### P0：utf8mb4 首次迁移失败

在独立 MySQL 8.0.46、utf8mb4 测试库上执行真实迁移，停在 Harness 初始迁移：

```text
OperationalError 1071: Specified key was too long; max key length is 3072 bytes
```

`harness/0001_initial.py` 中 `uniq_harness_idempotency_scope` 将平台应用、用户、空间、Tool、运行范围和幂等键合为一个唯一索引。文本字段总长度为 894 个字符，utf8mb4 下仅文本部分就达到 3576 字节，超过 InnoDB 上限。

此问题来自累计 P4 原始实现，不是本次冲突解决新增。**不得通过把生产字符集降为 utf8 来规避**：这会丢失四字节 Unicode 能力。后续需单独确定有界摘要唯一键等方案，并覆盖新安装、已有数据升级、冲突检测与真实并发；本次未擅自改变幂等协议或历史迁移。

### 整套真实数据库与环境验证仍未完成

- 探索性 utf8 MySQL 大集合曾得到 3614 passed / 42 failed，不能视为整套通过。失败包括旧 P4 夹具超过真实列长、固定自增 ID 假设、仅针对 SQLite 的测试、utf8 四字节字符限制，以及本地缺少完整 SM4 依赖。发现的租户测试夹具和 provider mock 泄漏已修复并通过定向复验，但没有重新宣称该大集合全绿。
- 探索性 SQLite 全仓测试还暴露了 JSON contains 不支持、SM4 依赖缺失和本机 Python 执行器的 macOS selector 错误；不以此修改无关存量模块，也不将这些失败隐藏为通过。
- 必须在修复 utf8mb4 迁移后，以完整依赖、生产对应数据库字符集完成全仓回归及 Harness 并发门禁。已有 P4 数据库的升级路径也需专门验证，不能只凭迁移图无冲突推断安全。
- 本地通过不等于 BKAIDev、MCP 网关、知识 Provider、签名审批、真实单步/全局调试和正式执行验收；这些外部链路本轮均未操作。
- 原 P4 对共享流程校验和草稿/发布路径的行为调整仍需存量流程样本回归；本轮没有把这些变更改成开关隔离。

建议下一步先解决 utf8mb4 索引及真实数据库测试问题，再更新 PR 与安排隔离环境验收。
