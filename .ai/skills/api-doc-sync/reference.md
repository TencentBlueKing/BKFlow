# API 文档模板与参考

## 文档结构模板

```markdown
### 资源描述

[接口功能的一句话描述，如：创建任务、获取空间配置]

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段     | 类型     | 必选 | 描述     |
|--------|--------|----|--------|
| [field] | [type] | 是/否 | [从 help_text 提取] |


### [特殊参数名] 参数说明

[当存在复杂字段如 credentials、config、custom_span_attributes 时，单独说明]

**参数格式要求：**
- [格式说明]

**示例：**
```json
{
    "key": "value"
}
```

**注意事项：**
- [重要说明]


### 请求参数示例

```json
{
    "field1": "value1",
    "field2": 123
}
```


### 返回结果示例

```json
{
    "result": true,
    "data": { ... },
    "code": "0",
    "message": ""
}
```


### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int/string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data[item]

| 字段   | 类型   | 描述   |
|------|------|------|
| [field] | [type] | [描述] |
```

## 视图与文档映射

| 视图函数 | 文档文件 |
|---------|---------|
| create_space | create_space.md |
| create_task | create_task.md |
| create_credential | create_credential.md |
| update_credential | update_credential.md（若为独立接口） |
| renew_space_config | renew_space_config.md |
| get_space_configs | get_space_configs.md |
| create_template | create_template.md |
| get_template_list | get_template_list.md |
| get_template_detail | get_template_detail.md |
| update_template | update_template.md |
| delete_template | delete_template.md |
| release_template | release_template.md |
| rollback_template | rollback_template.md |
| create_task_without_template | create_task_without_template.md |
| create_mock_task | create_mock_task.md |
| get_task_list | get_task_list.md |
| get_task_detail | get_task_detail.md |
| get_task_states | get_task_states.md |
| get_tasks_states | get_tasks_states.md |
| operate_task | operate_task.md |
| operate_task_node | operate_task_node.md |
| get_task_node_detail | get_task_node_detail.md |
| delete_task | delete_task.md |
| apply_token | apply_token.md |
| revoke_token | revoke_token.md |
| apply_webhook_configs | apply_webhook_configs.md |
| validate_pipeline_tree | validate_pipeline_tree.md |

## 从 Serializer 提取文档

```python
# 示例：CreateTaskSerializer
class CreateTaskSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模版ID"))  # 必选（无 required=False）
    name = serializers.CharField(help_text=_("任务名"), required=False)  # 可选
    creator = serializers.CharField(help_text=_("创建者"), required=True)  # 必选
    credentials = serializers.DictField(help_text=_("凭证字典..."), required=False)  # 可选，需单独说明
```

提取规则：
- **字段**：Serializer 的 field 名
- **类型**：IntegerField→int, CharField→string, JSONField→json, DictField→dict, BooleanField→bool
- **必选**：required=True 为「是」，required=False 或 default 为「否」
- **描述**：优先使用 help_text，否则根据字段名推断

## swagger_auto_schema 补充示例

```python
from drf_yasg.utils import swagger_auto_schema

@swagger_auto_schema(
    method="POST",
    operation_summary="创建任务",
    operation_description="在指定空间下根据模板创建任务实例",
    request_body=CreateTaskSerializer,
    responses={200: "成功返回任务信息"}
)
def create_task(request, space_id):
    ...
```
