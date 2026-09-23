# 流程模板版本差异可视化对比 · 设计稿方案同步

- 日期：2026-07-09
- 类型：设计稿评审后的方案修订记录（非完整实现 plan）
- 分支：`feat/template-version-diff-design`
- 关联原型（GitHub）：[prototypes/output/template-version-diff](https://github.com/dengyh/BKFlow/tree/feat/template-version-diff-design/prototypes/output/template-version-diff)
- 关联 README：[README.md](https://github.com/dengyh/BKFlow/blob/feat/template-version-diff-design/prototypes/output/template-version-diff/README.md)
- 关联 TAPD：
  - 父需求 [135668437](https://tapd.woa.com/tapd_fe/70120217/story/detail/1070120217135668437)
  - 设计子需求 [135883392](https://tapd.woa.com/tapd_fe/70120217/story/detail/1070120217135883392)

> 知识库完整 Spec / Spike 仍维护在 Obsidian（`.knowledge-base/...`）；仓库内以本文件 + 原型目录为可分享真源。

## 本次修订要点

1. **删除「版本控制未开启」弹窗方案（原屏 6）**  
   `FlowVersioning=false` 时不存在本系列「发布确认 + 版本 Diff」弹窗，不做置灰 Diff 态设计稿。

2. **全屏发布确认 Dialog 增加面包屑**  
   - 总览 / 基线切换 / 无变更：`发布确认`  
   - 字段级 Diff：`发布确认 / 版本差异总览 / {节点名}`（前级可点击返回）  
   - 高级 JSON：`发布确认 / 版本差异总览 / 高级 Diff`

3. **发布表单**  
   发布确认面板顶部保留可编辑「版本号 / 版本描述」（与现网发布弹窗一致），Diff 区嵌在同一弹窗内。

4. **设计稿交付范围**  
   `designs/01`–`05`；无 `06`。

## 文档索引（GitHub 分支）

| 文档 | 链接 |
|------|------|
| 方案同步（本文件） | https://github.com/dengyh/BKFlow/blob/feat/template-version-diff-design/docs/specs/2026-07-09-template-version-diff-design-sync.md |
| 原型 README | https://github.com/dengyh/BKFlow/blob/feat/template-version-diff-design/prototypes/output/template-version-diff/README.md |
| 线框 screens | https://github.com/dengyh/BKFlow/tree/feat/template-version-diff-design/prototypes/output/template-version-diff/screens |
| 线框截图 shots | https://github.com/dengyh/BKFlow/tree/feat/template-version-diff-design/prototypes/output/template-version-diff/shots |
| 设计稿 designs | https://github.com/dengyh/BKFlow/tree/feat/template-version-diff-design/prototypes/output/template-version-diff/designs |
| 设计稿 skill | https://github.com/dengyh/BKFlow/tree/feat/template-version-diff-design/.ai/skills/prototype-design-mockup |

## 说明

仓库内尚无独立 `docs/plans/*version-diff*` 实现计划；若后续 writing-plans，须以上述修订为前提，勿再纳入屏 6。
