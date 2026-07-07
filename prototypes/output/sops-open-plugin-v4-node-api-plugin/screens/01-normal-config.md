# V4.0.0 API 插件节点 · 正常配置态

[[ 首页 > 流程 > 模板编辑 > 节点配置 ]]

::: card
#### 场景
模板作者在节点配置抽屉中选择标准运维开放插件来源，并确认业务插件版本。

((可保存)){success}
:::

::: row
::: card
#### 画布节点
云作业执行脚本

((uniform_api)){primary}
((wrapper v4.0.0)){primary}
((plugin_version 1.4.2)){success}

> 节点仍是普通 API 插件节点，不新增标准运维专属节点类型。
:::

::: card
#### 插件选择
来源
[标准运维开放插件___]

分类
[作业执行___]

插件
[云作业执行脚本___]

业务版本
[1.4.2 默认版本___]

<!-- ❶ 业务版本是前端新增显式控件。默认选目录返回的 default_version，用户看到的是开放插件业务版本，不是 uniform_api wrapper 版本。 -->

#### 参数配置
业务 ID
[200145___]

执行账号
[root___]

脚本内容
[echo deploy bkflow open plugin___]

超时时间
[600___]

<!-- ❷ 参数表单由所选 plugin_version 的 detail_meta/get_plugin_schema 渲染；版本不变时按现有节点配置逻辑保存。 -->
:::

::: card
#### 运行摘要
调度模式
((轮询 polling)){primary}

回调地址
((运行时生成)){primary}

#### 节点隐藏字段
- component.version = v4.0.0
- uniform_api_plugin_id = job_execute_script
- uniform_api_plugin_version = 1.4.2
- uniform_api_plugin_url
- uniform_api_plugin_method
- uniform_api_plugin_polling

<!-- ❸ polling/callback 只做只读摘要，不暴露给用户编辑；保存节点时仍写入隐藏字段供 runtime fallback 使用。 -->

#### context
((运行时注入)){primary}

space / scope / operator / task / node 不进入表单。

<!-- ❹ context 由 BKFlow runtime execute 时构造并透传，前端不提供输入控件，也不保存到节点。 -->
:::
:::

::: row {right}
[取消] [保存节点配置]*
:::

<!-- ❺ 保存时手动触发。前端提交节点配置，服务端仍会在保存模板时校验 source grant、空间插件开关和 plugin_version 可用性。 -->
