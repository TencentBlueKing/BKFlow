---
name: tapd-test-request-generator
description: Use when creating a TAPD test request from PRs or requirement changes and needing a standardized, reusable template for BKFlow.
---

# TAPD 提测单生成

将 PR 或需求变更整理为结构化提测单，确保测试同学可直接按范围执行验证，避免「只有链接、没有可测标准」的问题。

## 触发场景

- 用户要求「创建提测单」「补充提测内容」「按模板生成 TAPD 提测」
- 已有 PR/需求，需要转测或提测验收
- 需要统一提测单格式，沉淀可复用模板

## 固定约束

- BKFlow TAPD 空间：`workspace_id=70120217`
- 默认实体类型：`stories`
- 优先使用模板：`docs/guide/tapd_test_request_template.md`
- 输出需覆盖：背景、版本说明、影响范围、测试范围（P0）、回归范围（P1）、风险点、验收标准、测试执行信息

## 执行流程

1. 收集输入信息：
   - PR 链接/分支、关联 story/bug、版本信息
   - 影响模块（前端/后端/依赖）
2. 解析变更并归纳：
   - 先归纳「新增/增强/修复/优化」四类版本说明
   - 再归纳 P0 主链路、异常边界、兼容回归
3. 套用模板生成描述：
   - 严格按模板章节顺序填充
   - 缺失信息用「待补充」占位，不留空白章节
4. 调用 TAPD 创建或更新：
   - 创建：`create_story_or_task`
   - 更新：`update_story_or_task`
5. 返回结果：
   - TAPD 链接
   - 已填充章节清单
   - 待补充字段（环境、版本、负责人、计划时间）

## 推荐字段

- `priority_label`: `High`（可按变更风险调整）
- `category_id`: 新功能优先 `1070120217002300909`，优化需求可用 `1070120217002300911`
- `iteration_id`: 当前开放迭代
- `owner`: 默认测试负责人

## 常见问题

- 只贴 PR 链接不写测试范围：必须补齐 P0/P1
- 只写功能描述不写验收标准：必须给出可验证标准
- 漏写依赖变更（例如 RC 包）：必须在风险点和影响范围体现
