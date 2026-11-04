/**
 * 插件管理 Mock 静态数据
 */
import { createDefaultStrategy } from '../shared';


// 插件分类目录（默认结构，最多 2 级）
// desc：分类描述；bindings：绑定的来源分类 id（该来源下未单独指定分类的插件都归到本分类）
export const DEFAULT_CATEGORIES = [
  {
    id: 'common',
    name: '通用能力',
    desc: '流程编排常用的通用插件',
    bindings: [],
    children: [
      { id: 'flow_control', name: '流程控制', desc: '', bindings: [] },
      { id: 'message', name: '消息通知', desc: '', bindings: ['bk_message'] },
      { id: 'script_api', name: '脚本与接口', desc: '', bindings: [] },
    ],
  },
  {
    id: 'host',
    name: '主机与作业',
    desc: '',
    bindings: [],
    children: [
      { id: 'job_exec', name: '作业执行', desc: '执行脚本、分发文件等作业类插件', bindings: ['api_job'] },
      { id: 'config_mgr', name: '配置管理', desc: '', bindings: ['api_cmdb'] },
    ],
  },
  { id: 'release', name: '发布与变更', desc: '', bindings: ['remote_bk_unified'], children: [] },
  { id: 'monitor', name: '监控告警', desc: '', bindings: ['api_monitor'], children: [] },
];

// 来源分类（新建/编辑分类抽屉的「来源绑定」）：按插件类型分组
// whole 为 true 表示远端模式的 API 来源，以「整个来源」为选项
export const MOCK_BINDING_SOURCE_GROUPS = [
  {
    id: 'api',
    name: 'API 插件（标准运维开放插件）',
    icon: 'commonicon-icon common-icon-plugin-chajian',
    children: [
      { id: 'api_job', name: '作业平台(JOB)' },
      { id: 'api_cmdb', name: '配置平台(CMDB)' },
      { id: 'api_monitor', name: '蓝鲸监控' },
    ],
  },
  {
    id: 'bk_plugin',
    name: '蓝鲸插件',
    icon: 'bk-icon icon-tree-application-shape',
    children: [
      { id: 'bk_job', name: '作业平台(JOB)' },
      { id: 'bk_message', name: '消息通知' },
      { id: 'bk_db', name: '数据库' },
    ],
  },
  {
    id: 'remote_api',
    name: '远端 API',
    icon: 'bk-icon icon-monitors-cog',
    children: [
      { id: 'remote_bk_unified', name: '蓝鲸统一 API （整个来源）', whole: true },
    ],
  },
];

// 插件状态：visible-启用 / review-待审核 / invalid-已失效 / rejected-未启用（停用携带 offlineReason / replacePluginId / offlineBy / offlineTime）
// recommendOrder：空间推荐中的顺序（仅 recommended 插件有值）
export const MOCK_PLUGINS = [
  { id: 1, name: '快速执行脚本', code: 'job_fast_execute_script', desc: '在目标主机上执行 Shell / Bat / Python 脚本', tag: 'plugin', type: 'api', source: 'job', category: 'job_exec', refCount: 46, nodeCount: 128, updatedBy: 'system', updateTime: '2024-10-10 09:12:36', status: 'visible', recommended: true, recommendOrder: 1 },
  { id: 2, name: '企业微信群机器人', code: 'bk_im_group_robot', desc: '通过企业微信群机器人推送消息通知', tag: 'recommend', type: 'bk_plugin', source: 'message', category: 'message', refCount: 31, nodeCount: 86, updatedBy: 'zhangsan', updateTime: '2024-10-09 17:45:08', status: 'visible', recommended: true, recommendOrder: 2 },
  { id: 3, name: 'HTTP 请求', code: 'http_request', desc: '向指定地址发起 HTTP 请求并解析响应结果', tag: '', type: 'builtin', source: 'bk', category: 'script_api', refCount: 128, nodeCount: 342, updatedBy: 'lisa', updateTime: '2024-10-08 14:03:51', status: 'visible', recommended: true, recommendOrder: 3 },
  { id: 4, name: '发送通知', code: 'send_notify', desc: '向指定人员发送站内信与邮件通知', tag: '', type: 'builtin', source: 'message', category: 'message', refCount: 57, nodeCount: 173, updatedBy: 'system', updateTime: '2024-10-08 02:00:00', status: 'visible', recommended: true, recommendOrder: 4 },
  { id: 5, name: '快速分发文件', code: 'job_fast_transfer_file', desc: '向目标主机分发文件并校验结果', tag: '', type: 'api', source: 'job', category: 'job_exec', refCount: 0, nodeCount: 0, updatedBy: 'system', updateTime: '2024-10-07 23:30:15', status: 'review' },
  { id: 6, name: '旧版工单同步', code: 'legacy_ticket_sync ', desc: '同步旧版工单系统的数据', tag: '', type: 'bk_plugin', source: 'ticket', category: 'release', refCount: 4, nodeCount: 12, updatedBy: 'kevin', updateTime: '2024-10-06 11:27:44', status: 'rejected', offlineBy: 'admin', offlineTime: '2024-10-06 11:27:44', offlineReason: '已由新版工单插件替代，请改用「工单（新版）」插件', replacePluginId: '' },
  { id: 7, name: '蓝盾统一 API', code: 'devops_unified_api', desc: '调用蓝盾统一网关的接口能力', tag: '', type: 'remote_api', source: '', category: 'release', refCount: 12, nodeCount: 30, updatedBy: 'system', updateTime: '2024-10-05 08:16:02', status: 'visible', recommended: true, recommendOrder: 5 },
  { id: 8, name: 'Python 代码', code: 'python_code', desc: '在标准运维执行机上运行 Python 代码片段', tag: '', type: 'builtin', source: 'bk', category: 'script_api', refCount: 9, nodeCount: 21, updatedBy: 'amy', updateTime: '2024-10-03 16:52:39', status: 'visible', recommended: true, recommendOrder: 6 },
  { id: 9, name: '告警屏蔽', code: 'monitor_alarm_shield', desc: '对指定告警策略设置生效期内屏蔽', tag: '', type: 'api', source: 'monitor', category: 'monitor', refCount: 22, nodeCount: 58, updatedBy: 'system', updateTime: '2024-09-30 04:05:21', status: 'visible', recommended: true, recommendOrder: 7 },
  { id: 10, name: '审批', code: 'approval', desc: '人工审批节点，审批通过后流程继续', tag: '', type: 'builtin', source: 'bk', category: 'flow_control', refCount: 64, nodeCount: 152, updatedBy: 'jason', updateTime: '2024-09-28 10:38:57', status: 'visible', recommended: true, recommendOrder: 8 },
  { id: 11, name: '旧版 CMDB 同步', code: 'legacy_cmdb_sync', desc: '同步旧版 CMDB 的主机与业务信息', tag: '', type: 'bk_plugin', source: 'bk', category: 'config_mgr', refCount: 0, nodeCount: 0, updatedBy: 'system', updateTime: '2024-09-25 15:20:11', status: 'invalid', invalidReason: 'PaaS 上已删除该插件', foundTime: '2024-09-26 10:00:00' },
  { id: 12, name: '蓝盾流水线触发', code: 'devops_pipeline_trigger', desc: '触发蓝盾流水线构建', tag: '', type: 'remote_api', source: '', category: 'release', refCount: 2, nodeCount: 3, updatedBy: 'kevin', updateTime: '2024-09-22 10:41:30', status: 'invalid', invalidReason: 'PaaS 上已删除该插件', foundTime: '2024-09-23 09:30:00' },
  { id: 13, name: '标准运维 V2 兼容包', code: 'sops_v2_compat', desc: '兼容标准运维 V2 的插件包', tag: '', type: 'builtin', source: 'bk', category: 'script_api', refCount: 0, nodeCount: 0, updatedBy: 'system', updateTime: '2024-09-18 09:05:44', status: 'invalid', invalidReason: 'PaaS 上已删除该插件', foundTime: '2024-09-19 14:12:36' },
  { id: 14, name: '邮件发送（旧）', code: 'legacy_send_mail', desc: '通过旧邮件网关发送邮件', tag: '', type: 'api', source: 'message', category: 'message', refCount: 1, nodeCount: 2, updatedBy: 'lisa', updateTime: '2024-09-12 18:33:07', status: 'invalid', invalidReason: 'PaaS 上已删除该插件', foundTime: '2024-09-13 11:47:20' },
  { id: 15, name: '旧版告警自愈', code: 'legacy_alarm_auto_heal', desc: '旧版告警自愈处理方案', tag: '', type: 'api', source: 'monitor', category: 'monitor', refCount: 0, nodeCount: 0, updatedBy: 'amy', updateTime: '2024-09-05 11:09:52', status: 'invalid', invalidReason: 'PaaS 上已删除该插件', foundTime: '2024-09-06 16:08:45' },
  { id: 16, name: '旧版容器平台采集', code: 'legacy_bcs_collector', desc: '旧版容器平台指标采集插件', tag: '', type: 'api', source: '', category: 'monitor', refCount: 0, nodeCount: 0, updatedBy: 'system', updateTime: '2024-08-28 15:40:11', status: 'rejected' },
  { id: 17, name: '短信网关（内测）', code: 'legacy_sms_gateway', desc: '旧内测短信网关，已由消息通知替代', tag: '', type: 'api', source: 'message', category: 'message', refCount: 0, nodeCount: 0, updatedBy: 'system', updateTime: '2024-08-15 09:20:36', status: 'rejected' },
];

// 插件引用流程（插件详情侧滑「当前引用」Tab）
// publishedNodes / publishedVersion 为 0 表示「尚未发布」；draftNodes 为 null 表示「无草稿」、0 表示「未引用」
export const MOCK_PLUGIN_REFERENCES = [
  { id: 1, pluginId: 1, flowId: 'T101', flowName: '版本发布通知', maintainer: 'Jerry', publishedNodes: 2, publishedVersion: 'v3.0.0', draftNodes: 2, draftNodeNames: ['清理结果通知', '失败告警', '清理结果通知', '清理结果通知', '清理结果通知', '清理结果通知', '清理结果通知', '清理结果通知'] },
  { id: 2, pluginId: 1, flowId: 'T102', flowName: '每日巡检汇总', maintainer: 'Tom', publishedNodes: 1, publishedVersion: 'v2.1.0', draftNodes: null },
  { id: 3, pluginId: 1, flowId: 'T103', flowName: '故障自愈 · 磁盘清理', maintainer: 'Admin', publishedNodes: 2, publishedVersion: 'v5.0.0', draftNodes: 0 },
  { id: 4, pluginId: 1, flowId: 'T104', flowName: '大区扩容 · 华南', maintainer: 'Lily', publishedNodes: 2, publishedVersion: 'v2.0.0', draftNodes: 5 },
  { id: 5, pluginId: 1, flowId: 'T105', flowName: '发布回滚通知', maintainer: 'Jerry', publishedNodes: 1, publishedVersion: 'v1.2.0', draftNodes: 3 },
  { id: 6, pluginId: 1, flowId: 'T106', flowName: '证书到期提醒', maintainer: 'Admin', publishedNodes: 2, publishedVersion: 'v3.1.0', draftNodes: null },
  { id: 7, pluginId: 1, flowId: 'T107', flowName: '数据库慢查询周报', maintainer: 'Tom', publishedNodes: 0, publishedVersion: '', draftNodes: 4 },
  { id: 8, pluginId: 1, flowId: 'T108', flowName: '容量水位巡检', maintainer: 'Lily', publishedNodes: 3, publishedVersion: 'v2.0.0', draftNodes: null },
];

// 新插件策略对象
// mode: review-全部需要审核 / visible-全部直接通过 / conditional-设条件自动通过
// visible 模式：visibleAfterPass-uncategorized 进未分类 / ai-AI 自动决定目录；visibleAiScope-increment 仅增量 / free 完全自由
// conditional 模式：conditions 直通条件组，每项 { sources, afterPass(uncategorized|ai|assign), aiScope, assignCategory }
export const MOCK_STRATEGY = createDefaultStrategy();
