# TAPD MCP 工具参考

本 skill 依赖 **user-TAPD** MCP 服务器。调用前需确认 TAPD MCP 已配置并可用。

## 工具清单

| 工具 | 用途 |
|------|------|
| get_user_participant_projects | 获取用户参与的项目列表，用于解析 workspace_id |
| get_stories_or_tasks | 查询需求或任务，支持 name 模糊匹配 |
| get_bug | 查询缺陷，支持 title 模糊匹配 |
| get_iterations | 获取迭代列表，用于取最新迭代 |
| create_story_or_task | 创建需求或任务 |
| create_bug | 创建缺陷 |

## 调用示例

### 查询需求（模糊匹配）

```json
{
  "workspace_id": 70120217,
  "options": {
    "entity_type": "stories",
    "name": "%构建研发skills%",
    "limit": 10
  }
}
```

### 查询缺陷

```json
{
  "workspace_id": 70120217,
  "options": {
    "title": "%关键词%",
    "limit": 10
  }
}
```

### 获取最新迭代

```json
{
  "workspace_id": 70120217,
  "options": {
    "status": "open",
    "order": "enddate desc",
    "limit": 5
  }
}
```

### 创建需求

```json
{
  "workspace_id": 70120217,
  "name": "构建研发skills",
  "options": {
    "entity_type": "stories",
    "iteration_id": "1070120217002215331",
    "description": "可选：需求详细描述"
  }
}
```

### 创建缺陷

```json
{
  "workspace_id": 70120217,
  "title": "缺陷标题",
  "options": {
    "iteration_id": "1070120217002215331",
    "description": "复现步骤、预期/实际结果"
  }
}
```

## ID 格式说明

- **完整 ID**：如 `1070120217131972327`，前 10 位为 workspace 前缀
- **短 ID**：后 9 位 `131972327`，用户常用格式
- **提取方式**：`full_id.slice(-9)` 或取 `id` 字段末尾 9 位

## 链接格式

- 需求：`https://tapd.woa.com/{workspace_id}/prong/stories/view/{短ID}`
- 缺陷：`https://tapd.woa.com/{workspace_id}/bugtrace/bugs/view/{短ID}`
