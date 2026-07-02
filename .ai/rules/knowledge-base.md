# BKFlow Long-Term Knowledge Base

BKFlow 的长期知识库用于沉淀产品方向、架构思考、ADR、复盘、历史调研和跨迭代上下文。

当前本地入口：

- `.knowledge-base/`

优先阅读：

- current-focus.md
- README.md
- 01-Projects/Active/
- 02-Brainstorming/
- 03-Specs/
- 04-Source-Code/
- 07-Debugging/
- 08-Ops/

使用原则：

- 源码级文档仍以本仓库 `.ai/docs/` 和代码为准
- 产品方向、架构思考、ADR、复盘、调研沉淀到长期知识库
- 不要把长期知识库内容批量复制进源码仓库
- 如需新增长期知识，优先写入知识库对应目录
- 涉及历史调研、产品方向、架构思考、ADR、复盘、跨迭代上下文、Agent Runtime、动态流程、CMMN/ACMN 等问题时，先查 `.knowledge-base/`
- 当前入口 `.knowledge-base/` 是隐藏 symlink，普通 `find` 默认不会跟随；建议显式检索该路径，或使用 `rg -L`

推荐检索：

```bash
rg -n -i "<keyword>" .knowledge-base
rg -L -n -i "<keyword>" .knowledge-base
```
