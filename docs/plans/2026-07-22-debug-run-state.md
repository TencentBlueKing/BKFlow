# 调试运行状态修复实施计划

1. 为任务状态查询增加可选调度类型，并覆盖回调、轮询和无调度记录场景。
2. 扩展 DebugContext 与 DebugNodeState 状态模型，生成迁移。
3. 将 real 单步改为异步启动，由 context 统一同步 running、waiting、paused 和结束态。
4. 在 context 中保留最近任务 ID、结果和任务级失败详情，覆盖网关失败。
5. 更新 SDK 调试接口文档，运行调试模块、任务状态模块和迁移检查。
