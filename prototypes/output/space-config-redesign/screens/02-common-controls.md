# 通用控件形态（右详情栏渲染示例）

[[ 空间配置 > 权限与安全 ]]

> 同一套元数据驱动，右详情栏按 `ui.control` 自动渲染出不同控件。下面并列展示三种典型形态。

::: card
### 🔁 Token 自动续期

当前状态：((默认))

Token 临近过期时自动延长有效期，减少调用中断。开：临期自动续期；关：到期即失效需重新获取。

启用自动续期
[Token 自动续期]{switch}

:::

<!-- ❶ switch：onChange 即时生效并 toast；状态徽标随之从「默认」变「已配置」。 -->

::: card
### ⏱ Token 过期时间

当前状态：((已配置)){success}

访问 Token 有效期，最短 1h，格式 `[n]m` / `[n]h` / `[n]d`。

有效期
[7d____________]{error}

> **校验失败态**：格式非法或小于 1h 时，输入框标红 + 下方红字「请输入不小于 1h 的时长，如 24h、7d」

:::

<!-- ❷ input：失焦即校验（必填 / 格式 / 最小 1h）；保存时后端 SpaceConfigHandler.validate 兜底，失败回显 detail。 -->

::: card
### 👥 空间管理员

当前状态：((已配置)){success}

拥有本空间全部管理权限；加入后可管理配置、凭证与全部流程/任务。

成员
[输入用户名搜索...]{type:search}

((admin ×)){primary} ((devops ×)){primary} ((sre-oncall ×)){primary}

:::

<!-- ❸ member_selector：复用 MemberSelect 组件，搜索下拉多选；已选成员以可删除 tag 呈现，存 json_value(list)。 -->

::: row {right}
[恢复默认值]{secondary} [取消] [保存]*
:::
