# Project Rules

本仓库不再通过 `AGENTS.md` 约束 `.ai/skills/` 的加载与使用；相关能力是否启用、如何启用，改由各自 IDE 或本地 Agent 配置决定。

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
