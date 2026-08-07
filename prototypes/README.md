# BKFlow 原型目录

本目录存放 BKFlow 的原型产物。原型统一用 **wiremd 线框 + Mermaid 流程图 + 全页截图**产出（低保真、可 diff、可导 Figma），交给设计师出高保真设计稿。

- 流程规范：`.ai/skills/prototype-wireframe/SKILL.md`
- 操作指南（工具链 / 语法 / 渲染 / 截图 / Figma / 提设计需求）：`.ai/docs/guides/prototyping-workflow.md`

> 旧的纯 HTML 工具包（`base.html` + `bkflow-prototype.css/js` + `serve.py` + `examples/`）与「代码即原型」方式已废弃、不再使用，相关文件已从仓库移除并在本地归档。

## 目录约定

每个原型一个子目录：

```
output/<feature-name>/
├── README.md          # 概览 + Mermaid 流程图 + 每屏截图 + 编号交互说明表
├── screens/*.md       # wiremd 线框源文件（唯一真源，可 diff / 迭代 / 导 Figma）
└── shots/*.png        # 各屏全页截图（README 内嵌）
```

- `screens/*.md` 是唯一真源，改一行重渲染即可。
- HTML 为临时产物，**不提交进仓库**，需要交互查看时按指南命令现渲染。

## 快速开始

```bash
cd output/<feature-name>

# 热更预览
npx -y @eclectic-ai/wiremd screens/ --serve 3000 --watch --show-comments
```

更多命令与语法见 `.ai/docs/guides/prototyping-workflow.md`。

## 产物存放

- 每个原型放在 `output/<feature-name>/`，随对应特性分支入库。
- 完整样例参考「空间配置改版」原型（5 屏线框 + Mermaid 流程 + 截图 + 交互表），随其特性分支提交。
