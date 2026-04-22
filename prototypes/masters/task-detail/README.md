# task-detail

## Purpose

`prototypes/masters/task-detail/` is the reusable master for the audited BKFlow execution detail route. It represents a read-only execution canvas with single-click node detail opening, a right-side audit surface, and configuration snapshot captured at execution time.

## What it covers

- An execution detail route header with `任务执行`, task name, status, and source-template backlink.
- A read-only execution canvas that stays distinct from `flow-editor/`.
- Single-click node detail opening for analysis instead of double-click editing.
- Observation tabs for `执行记录 / 配置快照 / 操作历史 / 调用日志`.
- A code-style log viewer and empty states for audit trails.
- Explicit separation from editing semantics: no save / publish / debug header actions.
