# 高级 Diff · JSON 与非执行变更

[[ 流程模板 > 订单发布编排 > 发布确认 > 高级 ]]

面包屑
[[ 发布确认 / 版本差异总览 / 高级 Diff ]]

> 前级可点击返回语义总览。

::: card
#### 高级视图

模式
- (*) 语义 Diff
- ( ) JSON Diff

范围
- (*) engine_pipeline_tree
- ( ) canvas_pipeline_tree（非执行变更）

<!-- ❶ JSON Diff 默认不展示给普通用户，需要用户主动打开高级；语义 diff 仍是默认入口。 -->
:::

::: row
::: card
#### pipeline_tree JSON Diff

`activities.act_gray_release_8f12.component.data.inputs.gray_ratio`

- 20
+ 30

`activities.act_gray_release_8f12.component.data.inputs.timeout`

- 600
+ 900

`flows.flow_approval_to_gray`

+ 审批确认 -> 灰度发布

> 仅面向排障和高级用户，保留原始 path，方便开发定位。
:::

::: card
#### 非执行变更

((默认收起)){secondary}

canvas_pipeline_tree
- 灰度发布节点坐标：x 420 -> 470
- 画布缩放比例：100% -> 90%
- 备注位置：发布说明便签向右移动 32px

> 这些变更不影响执行，默认折叠，不进入主变更计数。
:::
:::

<!-- ❷ engine_pipeline_tree 与 canvas_pipeline_tree 分层展示；非执行变更不干扰发布前核心判断。 -->

::: row {right}
[返回语义视图]{secondary} [复制 JSON 片段]{secondary} [确认发布]*
:::

<!-- ❸ 复制 JSON 片段用于排障；复制内容包含基线版本、当前草稿标识和原始字段 path。 -->
