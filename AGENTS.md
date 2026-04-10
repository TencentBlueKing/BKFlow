# Agent Skills

本项目在 `.ai/skills/` 目录下维护了一套 Agent Skills，覆盖完整的软件开发流程。
所有 AI 编码代理（Claude Code、Codex CLI 等）在处理任务时必须遵循本规则。

## 核心规则

**收到任务时，只要有 1% 的可能性存在适用的 skill，就必须读取并遵循它。**

在处理任何任务前：
1. 读取 `.ai/skills/using-superpowers/SKILL.md`，了解完整的技能使用规范
2. 根据其中的技能列表判断当前任务适用哪些技能
3. 读取对应技能的 `SKILL.md` 并严格遵循

## 可用技能

| 技能 | 路径 | 触发条件 |
|------|------|----------|
| brainstorming | `.ai/skills/brainstorming/SKILL.md` | 创建新功能、组件、模块前，探索需求和设计 |
| writing-plans | `.ai/skills/writing-plans/SKILL.md` | 有 spec 或需求后，开始实现前，拆分任务 |
| executing-plans | `.ai/skills/executing-plans/SKILL.md` | 有实现计划后，分批执行并设置检查点 |
| subagent-driven-development | `.ai/skills/subagent-driven-development/SKILL.md` | 执行有独立任务的实现计划 |
| test-driven-development | `.ai/skills/test-driven-development/SKILL.md` | 实现任何功能或修复 bug 前，先写测试 |
| systematic-debugging | `.ai/skills/systematic-debugging/SKILL.md` | 遇到 bug、测试失败、异常行为时，系统化排查 |
| requesting-code-review | `.ai/skills/requesting-code-review/SKILL.md` | 完成任务、实现重大功能后，提交前审查 |
| receiving-code-review | `.ai/skills/receiving-code-review/SKILL.md` | 收到 code review 反馈后，实施建议前 |
| verification-before-completion | `.ai/skills/verification-before-completion/SKILL.md` | 声称工作完成前，必须运行验证命令 |
| dispatching-parallel-agents | `.ai/skills/dispatching-parallel-agents/SKILL.md` | 面对 2+ 个无依赖的独立任务时 |
| using-git-worktrees | `.ai/skills/using-git-worktrees/SKILL.md` | 需要隔离工作空间的功能开发 |
| finishing-a-development-branch | `.ai/skills/finishing-a-development-branch/SKILL.md` | 实现完成后，决定如何集成工作 |
| writing-skills | `.ai/skills/writing-skills/SKILL.md` | 创建或编辑技能文件时 |
| ui-prototype | `.ai/skills/ui-prototype/SKILL.md` | 设计新页面、修改页面布局、UI 原型迭代时 |
| prototype-generator | `.ai/skills/prototype-generator/SKILL.md` | 需要快速出产品原型时，如"做个原型"、"设计页面" |
| api-doc-sync | `.ai/skills/api-doc-sync/SKILL.md` | 修改 bkflow/apigw/ 下的 API 代码时 |
| tapd-workitem-sync | `.ai/skills/tapd-workitem-sync/SKILL.md` | 开发需求确认后、开始实现前，需确保 TAPD 有对应单据 |
| tapd-test-request-generator | `.ai/skills/tapd-test-request-generator/SKILL.md` | 需要根据 PR 或需求变更按模板创建/补全 TAPD 提测单时 |

## 项目编码规范

本项目的规范文件位于 `.ai/rules/` 目录下，所有 AI 代理必须遵循：

| 规范 | 路径 | 内容 |
|------|------|------|
| 编码规范 | `.ai/rules/bkflow-coding-convention.mdc` | Python 代码风格、Django/DRF 约定、测试、前端 |
| 权限体系 | `.ai/rules/bkflow-permission.mdc` | 四层鉴权架构、permission_classes 配置指南 |
| Git 提交规范 | `.ai/rules/git-commit-convention.mdc` | commit message 格式、type 枚举、TAPD 关联 |
| Git 工作流 | `.ai/rules/git-workflow.mdc` | 功能分支、PR 提交流程、remote 约定 |
| 文档管理 | `.ai/rules/docs-management.mdc` | 文档目录规范、命名规则、归属判断 |
| APIGW 资源同步 | `.ai/rules/apigw-resource-sync.mdc` | 新增/修改网关接口时必须同步 api-resources.yml 和 apigw-docs.zip |
