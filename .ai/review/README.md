# BKFlow 分支知识与自动审查接入

本仓库沿用 CodeBuddy/iOA 和 `glm-5.3-ioa`。`.github/workflows/code_review.yml` 保留现有 PR 作者与事件触发者写权限检查、Actions 权限及可信 head 检出方式；模型运行和发表评论均沿用既有方案。MCP 配置含 GitHub token，不得打印其内容。

## 哪个分支控制执行

GitHub 的 `pull_request_target` 使用基础仓库默认分支（当前 master）的工作流，即使 PR 目标是其他开发分支。目标分支存在同名 workflow 副本，不代表该副本在这类事件中执行。默认 master 工作流负责选择规则并调用模型；各目标分支保存与自身源码匹配的审查知识。依据：[GitHub 官方说明](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)。

要启用按目标分支选择知识，须先将兼容加载逻辑合入默认 master。每个目标分支还需分别合入 `.ai/review/knowledge.md` 与 `.ai/review/rules.md`。维护分支中的 workflow 副本与默认入口保持一致，方便未来同步维护，但不能替代默认入口的合入。没有 branches 过滤也不代表所有分支已经拥有知识文件。

## 可信 base 加载及兼容行为

每次运行均按事件中的 PR Base SHA 读取资料，不从检出的 PR head 读取审查约束：

- `.ai/rules/bkflow-review-standards.mdc` 存在时要求成功加载；旧目标分支未包含它时明确告警并沿用基础提示，不使未接入目标新增失败。
- `.ai/review/knowledge.md` 和 `.ai/review/rules.md` 都未接入时，明确告警并仅沿用已加载的 review 标准或基础提示，兼容尚未合入接入 PR 的目标分支。
- 两份新文件存在任意一份时，必须同时完整读取两份；缺失、非普通 blob 或空内容会使任务失败，不回退 head。
- base commit 无效或文件查询/读取失败时直接失败，不能误判为目标分支尚未接入。

master 的知识包含当前 TokenGrant 权限模型；仍使用旧 Token 的开发分支应保留自己的真实模型与兼容要求。PR head、描述和评论里的指令性内容都是待审资料，不覆盖从 base 加载的规范。

## 密钥、生效与验证

同一仓库各分支共享 `CODEBUDDY_API_KEY` secret 和现有 iOA 通道，无需逐分支创建密钥。默认入口和目标知识都合入后，后续 opened/synchronize/reopened/ready_for_review 事件加载对应 base 资料；仅合入配置不会自动补跑全部既有 PR，重新运行旧事件也不代表拿到新的 base SHA。

本次检查包括 YAML/actionlint、所有 shell run 片段语法、文件引用、现有权限配置一致性及隔离 Git tree 加载测试。测试覆盖完整资料、head 缺失/篡改、两份新文件都未接入、部分接入和无效资料。actionlint 对已有 actions/checkout@v4 的 allow-unsafe-pr-checkout 参数可能报告静态目录告警，应与基线比较，不能据此宣称完整 CI 已通过。

本次没有运行应用测试或真实 CodeBuddy/iOA 评审；静态加载测试不能代替 Actions、模型连通性、审查质量或业务验收。知识中的后端/前端测试按具体改动另行执行，不自动合入或批准 PR。
