# 插件管理 V2 设计交付材料

日期：2026年10月30日。状态：目标设计，尚未实现或验收。

## 阅读入口

- [01 开发改动总览](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=OYB9Sg)，对应[本地评审稿](../../specs/2026-10-30-space-plugin-catalog-v2-review-design.md)。
- [02 模型与接口清单](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=LlIaHY)，对应[本地清单](../../specs/2026-10-30-space-plugin-catalog-v2-contracts.md)。
- [03 后台任务与迁移清单](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=QJpt5P)，对应[本地清单](../../specs/2026-10-30-space-plugin-catalog-v2-jobs-migration.md)。
- [开发 spec](../../specs/2026-10-30-space-plugin-catalog-v2-design.md)。
- [16 项实现 plan](../../plans/2026-10-30-space-plugin-catalog-v2.md)。
- [04 实施计划与验收](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=UhJZjU)，对应[本地阅读稿](../../plans/2026-10-30-space-plugin-catalog-v2-team-plan.md)。
- [05 调用时序与一致性](https://doc.weixin.qq.com/smartpage/a1_AIoAtXhKAM4CN9oEFNWhJRAWP7sB0_a?p=VW1Hn3)，对应[本地阅读稿](../../specs/2026-10-30-space-plugin-catalog-v2-interactions-design.md)。
- [TAPD 插件管理需求](https://tapd.woa.com/70120217/prong/stories/view/139209730)。

## 图源与成图

- `draw_delivery_map.py`：当前开发改动与模块交互图的可编辑源，Python + Pillow。
- `delivery-map.png`：2880 × 2340 高清成图，用于当前智能文档总览。
- `delivery-map-preview.png`：1200 px 宽的阅读检查预览。
- `draw_sequences.py`：三条关键调用时序的可编辑源，Python + Pillow。
- `sequence-save.png`、`sequence-sync.png`、`sequence-engine.png`：流程保存、来源同步与自动 AI、Interface/Engine 建任务与启动的高清图；对应 `-preview.png` 为阅读检查预览。
- `draw_architecture.py`、`architecture.png`、`architecture-preview.png`：保留前版总体职责图，当前交互与数量以 delivery-map 和清单为准。

默认字体为 macOS STHeiti；其他平台通过 `DIAGRAM_FONT` 指定中文字体。仓库根目录运行 `python3 docs/pics/plugin-catalog-v2/draw_delivery_map.py` 或 `python3 docs/pics/plugin-catalog-v2/draw_sequences.py` 可重新生成对应图片。不修改项目生产依赖，不访问运行环境。

当前图示明确 Interface Web、Worker/Beat、管理数据、手动初始化及 Engine 的任务/快照边界；实线表示请求/写入，虚线表示返回。数据库可共享或隔离，管理数据仍归 Interface。模型 4 新增＋3 复用/扩展、11 个 HTTP 操作/9 路径、Celery 2 新增＋3 改造及复用 2 个周期入口为用户已确认的收敛方向。图未声明线上部署结果；事务后的任务补投等未定细节标注 E 编号，视觉风格沿用 architecture-flow-diagrams 规范。

## 分支范围

主仓文档分支为 [ai/space-plugin-catalog-v2-docs](https://github.com/TencentBlueKing/BKFlow/tree/ai/space-plugin-catalog-v2-docs)，初版源码基线为 `6098d9d0`，本轮核查文档分支 `70b2d0fa` 并与 upstream/master `19de2149` 对照。本次保留现有工作区和分支基线；实施前需在隔离开发分支重新核对最新源码。

本次只归档当前 spec、plan、团队评审稿及这组图源/成图。旧引用详情修订稿、历史原型、操作回执和临时截图不作为本期设计基线；原企微需求文档未在本轮改写。第 6、7 项继续标注暂定。
