# 插件管理 V2 设计交付材料

日期：2026年10月30日。状态：目标设计，尚未实现或验收。

## 阅读入口

- [团队阅读用智能文档](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=OYB9Sg)。
- [本地团队评审稿](../../specs/2026-10-30-space-plugin-catalog-v2-review-design.md)。
- [开发 spec](../../specs/2026-10-30-space-plugin-catalog-v2-design.md)。
- [16 项实现 plan](../../plans/2026-10-30-space-plugin-catalog-v2.md)。
- [TAPD 插件管理需求](https://tapd.woa.com/70120217/prong/stories/view/139209730)。

## 图源与成图

- `draw_architecture.py`：可编辑、可重复生成的结构化绘图源，Python + Pillow。
- `architecture.png`：2880 × 2220 高清成图，已上传智能文档。
- `architecture-preview.png`：1000 px 宽的阅读检查预览。

默认字体为 macOS STHeiti；其他平台通过 `DIAGRAM_FONT` 指定中文字体。仓库根目录运行 `python3 docs/pics/plugin-catalog-v2/draw_architecture.py` 可重新生成图片。不修改项目生产依赖，不访问运行环境。

图示明确 Interface Web、Worker/Beat、管理数据库、Engine 和外部来源/bkaidev 的边界；实线表示请求/提交，虚线表示返回。图未声明任何线上部署结果。依据为本次 spec 与用户已确认规则，视觉风格沿用 architecture-flow-diagrams 规范。

## 分支范围

主仓文档分支为 [ai/space-plugin-catalog-v2-docs](https://github.com/TencentBlueKing/bkflow/tree/ai/space-plugin-catalog-v2-docs)，基于本次源码核验提交 `6098d9d0`。本地主仓已有两份未跟踪文件与最新上游同名，切换上游基线被 Git 安全拒绝；本次保留工作区，未覆盖/删除它们。实施前需在隔离开发分支重新核对最新源码。

本次只归档当前 spec、plan、团队评审稿及这组图源/成图。旧引用详情修订稿、历史原型、操作回执和临时截图不作为本期设计基线；原企微需求文档未在本轮改写。第 6、7 项继续标注暂定。
