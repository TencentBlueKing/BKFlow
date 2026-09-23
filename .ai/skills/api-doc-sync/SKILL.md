---
name: api-doc-sync
description: After implementing or modifying API code in bkflow/apigw, automatically updates or generates apidoc markdown files in bkflow/apigw/docs/zh/. Use when API views, serializers, or routes are changed, or when the user asks to sync API docs or generate apidoc.
---

# API 文档同步与生成

在实现或修改 API 代码后，自动完善 API 文档并生成 apidoc 文件。

## 触发场景

- 修改了 `bkflow/apigw/views/` 下的视图
- 修改了 `bkflow/apigw/serializers/` 下的序列化器
- 修改了 `bkflow/apigw/urls.py` 路由
- 用户明确要求「同步 API 文档」「生成 apidoc」「更新接口文档」

## 工作流程

### 1. 识别变更的 API

- 从用户修改的文件或对话中识别涉及的 API
- 视图与文档映射：`create_task` → `create_task.md`，`get_space_configs` → `get_space_configs.md`
- 文档路径：`bkflow/apigw/docs/zh/{api_name}.md`

### 2. 分析 API 实现

读取以下内容以提取参数和返回结构：

- **视图**：`bkflow/apigw/views/{api_name}.py`，关注使用的 Serializer 和业务逻辑
- **序列化器**：`bkflow/apigw/serializers/` 下的相关类，从 `help_text`、`required`、`default` 提取字段说明
- **路由**：`bkflow/apigw/urls.py` 中的 URL 路径和 path 参数

### 3. 生成/更新文档

遵循项目既有格式，参考 [reference.md](reference.md) 中的模板。

**必须包含的章节：**

1. **资源描述**：简要说明接口功能
2. **输入通用参数说明**：bk_app_code、bk_app_secret（表格）
3. **接口参数**：请求体字段（表格：字段、类型、必选、描述）
4. **特殊参数说明**：复杂字段（如 credentials、config）单独说明，含示例
5. **请求参数示例**：JSON 示例
6. **返回结果示例**：成功/失败 JSON 示例
7. **返回结果参数说明**：data 字段结构（表格）

### 4. 可选：完善 swagger_auto_schema

若视图使用 `@swagger_auto_schema`，补充：

- `operation_summary`：接口摘要
- `operation_description`：详细说明
- `request_body` / `query_serializer`：对应 Serializer
- `responses`：主要响应结构

## 文档格式规范

- 表格使用 Markdown 表格语法
- 类型：string、int、bool、json、dict、list 等
- 必选：是/否
- 描述：从 Serializer 的 `help_text` 提取，或根据业务逻辑补充

## 示例：create_task 文档结构

```markdown
### 资源描述
创建任务

### 输入通用参数说明
| 参数名称 | 参数类型 | 必须 | 参数说明 |
| ... | ... | ... | ... |

#### 接口参数
| 字段 | 类型 | 必选 | 描述 |
| ... | ... | ... | ... |

### 特殊参数说明（如有）
[credentials、config 等]

### 请求参数示例
```json
{ ... }
```

### 返回结果示例
```json
{ ... }
```

### 返回结果参数说明
| 字段 | 类型 | 描述 |
| ... | ... | ... |
```

## 注意事项

- 仅更新与本次变更相关的 API 文档，避免大范围修改
- 保持与现有文档风格一致（如 create_space.md、create_task.md）
- 复杂字段（如 credentials）需补充格式、示例和注意事项
- 若文档已存在，在原有基础上增量更新，而非全量重写

## 参考

- 完整模板与示例：见 [reference.md](reference.md)
- 现有文档示例：`bkflow/apigw/docs/zh/create_task.md`、`create_space.md`
