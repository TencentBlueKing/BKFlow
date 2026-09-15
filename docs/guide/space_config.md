# 空间配置说明

## 使用配置中心

在空间管理的“空间配置”页，左侧选择配置项，右侧查看用途、影响和编辑表单。可搜索配置显示名称或字段名。

| 分组 | 配置项 |
| --- | --- |
| 权限与安全 | 空间管理员、Token 过期时间、Token 自动续期、网关凭证 |
| 流程与画布行为 | 流程版本控制、是否允许配置多个触发器、网关表达式、画布模式 |
| API 与插件集成 | API 插件、空间插件配置 |

- **保存**：修改表单或开关后，点击“保存”才提交当前配置。切换到其他配置前请先保存，当前页面没有未保存内容的离开确认。
- **默认 / 已配置**：未保存过配置记录时显示“默认”；已有记录时显示“已配置”，即使保存值与默认值相同。
- **恢复默认**：确认后清除该项已保存的配置，重新使用默认值。空间管理员不提供恢复默认按钮，至少需要保留一位管理员。
- **表单结构 / JSON源码**：网关凭证、API 插件和空间插件配置支持切换编辑方式。高级字段的维护边界见下文各配置说明。
- **异常**：表示当前页面的保存失败状态；API 插件的测试结果显示在对应接入条目中。“已配置”不代表外部接口测试通过。

页面操作需要平台管理员或对应空间管理员权限；多租户环境还需满足当前租户的空间访问约束。引擎配置 `engine_space_config` 和已废弃的 `callback_hooks` 不在配置中心展示。

## superusers

**字段类型：** JSON

**字段含义：** 空间的管理员

**初始值：** 创建空间时写入 `["{空间创建者}"]`；没有配置记录时，配置类的回退值是空列表。

配置方式:
在列表中添加空间管理员用户名。

```json
["admin1","admin2"]
```

**功能表现：** 对应用户获得空间管理员权限。创建空间时写入创建者；修改时至少保留一位管理员。

## token_expiration

**字段类型：** TEXT

**字段含义：** 该空间下访问资源权限的token的过期时间

**默认值：** 1h

**配置方式：**

| 示例值 | 描述 |
| ------ | ----------- |
| [n]m | m->minute |
| [n]h | h->hour |
| [n]d | d->day |

**说明：** 至少为 1h。上限由部署配置 `BKAPP_TOKEN_EXPIRATION_MAX_EXPIRATION` 控制，单位为秒，默认 `2592000`（30 天）。

**功能表现：** 后续签发或成功续期的 token，其到期时间设为“当前时间 + 配置时长”。修改配置不会批量更新已有 token，也不限制持续续期后的累计存活时长。完整机制见 [Token 授权与接入说明](token_authorization.md)。

## token_auto_renewal

**字段类型：** TEXT

**字段含义：** 是否允许复用有效 token 或显式调用续期接口时刷新到期时间。

**默认值：** true

**配置方式：**

| 可选值 | 描述 |
| ------- | -------- |
| true | 开启自动续期 |
| false | 不开启，到期后token过期 |

**功能表现：** 开启后，再次申请已有有效 token 或成功调用续期接口，会将到期时间刷新为“当前时间 + token_expiration”。编辑页和模板调试页为普通用户每 5 分钟发起一次续期请求；普通业务请求校验 token 时不会自动续期，也没有到期后统一续期的后台任务。续期对过期及撤销状态的限制见 [当前实现边界](token_authorization.md#9-当前实现边界)。

配置只影响有效期，不改变授权集合，也不控制 grants 申请开关。发布统一 Token 存储时，历史单项会由数据库迁移原值回填，无需通过修改空间配置或重新申请票据完成转换；维护窗口和回退顺序见 [Token 上线与回退](token_authorization.md#11-上线与回退)。

## callback_hooks

**字段类型：** JSON

**字段含义：** 历史回调 URL 配置，已废弃且不在配置中心展示。请使用 `apply_webhook_configs` 进行回调配置。以下仅说明历史存储格式。

**配置方式：**

``` json
{
    "url": "{callback_url}",
    "callback_types": [
        "template"
    ]
}
```

| 字段 | 类型 | 描述 |
| ---------------- | ---------- | ------------------ |
| callback_url | string | 回调所用的来自apigw的url |
| callback_types | string[] | 资源类型列表 |
**说明：** callback_url必须为来自apigw的url，callback_types为资源类型

**功能表现：** 在对应事件触发时回调该url

## uniform_api

**字段类型：** JSON

**字段含义：** 统一 API 插件配置。每个 `api_key` 对应一条接入信息，可在表单中新增、编辑和删除。

**配置方式：**

``` json
{
    "api": {
        "{api_key}": {
            "meta_apis": "{meta_apis url}",
            "api_categories": "{api_categories url}",
            "display_name": "{display_name}",
            "source_key": "{open plugin execution source key}"
        }
    }
}
```

| 名称 | 类型 | 说明 |
| -------------------- | ---------- | ------------------ |
| api_key | string | API插件的Key值 |
| meta_apis url | string | 获取API接口元数据列表的url |
| api_categories url | string | 获取API接口分类列表的url |
| display_name | string | API插件的展示名称 |
| source_key | string | 可选，开放插件目录与执行的来源标识；不配置时使用 api_key |

当前表单要求填写 `api_key`、展示名称、Meta 列表 URL 和分类 URL。`api_key` 仅允许字母、数字和下划线，URL 需使用部署允许的 APIGW 地址。表单也可添加自定义请求头，key 和 value 需要成对填写。

每个 `api_key` 会生成一个独立的顶层 API 插件入口。多个入口可以使用不同的目录 URL（包括固定查询参数），同时配置相同的 `source_key`，从而共享同一套目录来源、空间插件开关与执行配置。
**说明：** API插件具体开发可参考：[API插件开发](api_plugin.md)

**功能表现：**

```json
{
  "api": {
    "api_key": {
      "meta_apis": "https://xxx.com/xxx/uniform_api_list/",
      "display_name": "API插件",
      "api_categories": "https://xxx.com/xxx/uniform_api_category_list/",
      "source_key": "api_key"
    }
  }
}
```

（配置了展示名称为“API插件”的入口）

![uniform_api_selection](../pics/uniform_api_selection.png)

### 高级字段与旧配置

后端还支持每个 API 条目的 `source_key`、`catalog_mode`，以及顶层 `common` 配置。`catalog_mode` 控制分类和列表的读取方式：

| 值 | 行为 |
| --- | --- |
| `remote`（默认） | 请求配置的远端目录接口 |
| `cache_first` | 目录已初始化时使用本地目录；未初始化时请求远端并触发异步同步 |
| `cache_only` | 仅使用本地目录；未初始化时报错 |

目录模式不改变下方测试按钮直接访问远端接口的行为。

当前表单修改条目时只重新生成展示名称、两个 URL 和请求头等已覆盖字段，**不会完整保留 `source_key`、`catalog_mode` 等高级字段**。含这些字段时，请在“JSON源码”中编辑并保存；不要切回表单修改后直接保存。顶层 `common` 可以保留，但没有专用表单。

历史 V1 顶层 `meta_apis` / `api_categories` 格式仍保留后端读取兼容；修改保存需整理为上方 V2 的 `api` 字典，当前表单不会自动完成 V1 转换。

### 测试 API 接入

1. 在“凭证管理”中准备当前空间的 BK_APP 凭证，再到“网关凭证”配置并保存默认凭证。
2. 填写 API 接入的必填字段，点击该条接入的测试按钮。测试使用当前表单内容，无需先保存 API 配置，也不会替你保存。
3. 查看分类数、接口数及抽样接口详情；失败时根据对应分类、列表或详情请求的错误检查 URL、凭证和响应协议。
4. 确认配置后点击“保存”，使该接入配置生效。

测试使用已保存的默认凭证，并依次请求分类、列表和部分接口详情。默认最多处理 50 个分类、50 次列表请求和 5 个详情样本；接口数是已处理分类返回数量的累计值，可能受抽样、截断和分类重叠影响。

当前测试流程只使用默认 APIGW 鉴权头，没有合并配置中的自定义请求头。测试通过也不等于所有接口或实际插件执行都通过，实际执行效果需要结合对应插件验证。

## flow_versioning

**字段类型：** TEXT，可选 `"true"` / `"false"`。

**字段含义：** 是否启用流程版本控制。启用时流程创建、编辑走草稿及版本管理流程，保存草稿不等于发布新版本。

**默认值：** 未存配置时为 `"false"`；通过当前空间创建接口创建的空间会显式写入 `"true"`。因此恢复默认与新建空间的初始设置可能不同。

## allow_multiple_triggers

**字段类型：** TEXT，可选 `"true"` / `"false"`，默认 `"false"`。

**字段含义：** 是否允许一个流程配置多个定时触发器。当前后端按定时触发器数量校验：关闭时，提交超过一个定时触发器会失败；不能据此推定所有其他触发器类型都受同一数量限制。

## canvas_mode

**字段类型：** TEXT

**字段含义：** 画布的呈现模式，默认为horizontal。

**配置方式：**

| 可选值 | 描述 |
| ------------ | ------ |
| horizontal | 水平模式 |
| vertical | 垂直模式 |
**说明：** 修改画布模式后，新建流程才会生效，不会影响原有流程

**功能表现：**
horizontal:

![水平模式](../pics/horizontal_mode.png)
vertical:

![垂直模式](../pics/vertical_mode.png)

## gateway_expression

**字段类型：** TEXT

**字段含义：** 网关的分支条件中表达式的语法类型。

**默认值：** boolrule

**配置方式：**

| 可选值 | 描述 |
| ---------- | ------------ |
| boolrule | boolrule语法 |
| FEEL | FEEL语法 |
| MAKO | Mako 模板表达式 |
**说明：** 详情参考各语法文档：[boolrule](https://boolrule.readthedocs.io/en/latest/expressions.html#basic-comparison-operators) [FEEL](https://github.com/TencentBlueKing/bkflow-feel/blob/main/docs/grammer.md)

## api_gateway_credential_name

**字段类型：** TEXT 或 JSON。

**字段含义：** 网关调用使用的凭证名称，支持默认凭证及按作用域覆盖。

**配置方式：** 从当前空间的 BK_APP 凭证中选择默认凭证，可追加作用域与凭证的对应关系。没有可用凭证时，点击“前往凭证管理”创建，然后返回配置页选择；当前不提供页内新建侧栏。

历史的单一凭证名以 TEXT 保存；表单兼容读取，并在编辑后使用含 `default` 的 JSON 对象：

```json
{
  "default": "default_app",
  "biz_2": "biz_2_app"
}
```

`biz_2` 表示 `scope_type=biz`、`scope_value=2` 的覆盖项。匹配到作用域时使用对应凭证，否则回退到默认凭证。JSON 配置必须包含 `default`。

这里配置的是凭证选择规则，不会修改凭证管理中的开放范围。当前下拉框按 BK_APP 类型筛选，没有按每条凭证的 scope 自动禁选；API 插件页面的测试使用已保存的默认凭证。

## space_plugin_config

**字段类型：** JSON

**字段含义：** 控制画布插件面板的可见范围，可选择全部显示、仅显示名单内插件或隐藏名单内插件。它不是插件执行权限开关。

**默认值：** `{"default":{"mode":"allow_all","plugin_codes":[]}}`。

**配置方式：**

``` json
{
    "default": {
        "mode": "deny_list",
        "plugin_codes": [
            "plugin_1",
            "plugin_2"
        ]
    }
}
```

| 键名称 | 类型 | 示例值 | 说明 |
| -------------- | ------------ | ---------------------------- | -------------------- |
| mode | string | allow_all / allow_list / deny_list | 全部显示 / 仅显示名单内插件 / 隐藏名单内插件 |
| plugin_codes | string[] | ["display", "bk_example"] | 插件code列表 |

**功能表现：**

选择 `allow_all` 时，页面保存会把 `plugin_codes` 清空。其他模式需要检查名单是否覆盖实际需要的插件。

保存前会弹出确认提示：过滤插件可能让已有流程的节点无法继续打开编辑；使用 `allow_list` 时，未列入的 API / 第三方插件入口也可能消失。已经运行的任务不会因此停止，但后续编辑可能受影响。确认后才提交保存。

①隐藏“消息展示”插件：

```json
{
    "default": {
        "mode": "deny_list",
        "plugin_codes": [
            "display"
        ]
    }
}
```

![hide display plugin](../pics/hide_display.png)
选择插件页面，消息展示消失。

②只显示“消息展示”插件:

```json
{
    "default": {
        "mode": "allow_list",
        "plugin_codes": [
            "display"
        ]
    }
}
```

![hide display plugin](../pics/only_show_display.png)
