/**
 * 插件管理接口层：所有请求集中在此，组件只关心参数与返回值。
 * TODO: 后端接口就绪后，把每个函数的 mockXxx 替换为真实 axios 请求，调用方无需改动。
 */
import {
  mockGetPluginSummary,
  mockGetPluginList,
  mockGetRecommendList,
  mockUpdatePlugin,
  mockUpdatePluginStatus,
  mockBatchUpdatePluginStatus,
  mockBatchUpdatePluginCategory,
  mockDeletePlugins,
  mockCleanPlugins,
  mockSavePluginStrategy,
  mockGetStrategySources,
  mockInitCategories,
  mockSaveRecommendOrder,
  mockCancelRecommend,
  mockCreateCategory,
  mockUpdateCategory,
  mockDeleteCategory,
  mockGetCategoryDeleteImpact,
  mockGetBindingSources,
  mockGetPluginDetail,
  mockGetPluginReferences,
  mockGetCategoryManageData,
  mockSaveCategoryManage,
} from './mock/pluginList';

// 插件概要：分类目录 / 分类计数 / 新插件策略 / 老版本节点数
// TODO: axios.get(`api/space/admin/plugin/summary/?space_id=${params.spaceId}`)
export function getPluginSummary(params) {
  return mockGetPluginSummary(params);
}

// 插件列表：分类 / 状态 / 类型 / 来源 / 关键字 / 排序 / 分页全部由后端处理
// params: { spaceId, category, status, type, source, keyword, page, page_size }
// keyword 为「不选择条件的手动输入」关键词数组，多词 OR，后端对插件名称 / 最近修改人做模糊匹配
// 返回: { count, results, status_counts }
// TODO: axios.get(`api/space/admin/plugin/list/?space_id=${params.spaceId}`, { params })
export function getPluginList(params) {
  return mockGetPluginList(params);
}

// 空间推荐列表（独立形态，无分页）
// TODO: axios.get(`api/space/admin/plugin/recommend/list/?space_id=${params.spaceId}`)
export function getRecommendList(params) {
  return mockGetRecommendList(params);
}

// 编辑插件：所属分类 / 空间推荐 / 下架配置（下架原因、替换插件）全量提交
// data: { category, recommended, offlineReason, replacePluginId }
// TODO: axios.post(`api/space/admin/plugin/${params.pluginId}/?space_id=${params.spaceId}`, params.data)
export function updatePlugin(params) {
  return mockUpdatePlugin(params);
}

// 更新单个插件状态（待审核通过可携带 category 目标目录；下架时可携带 offlineReason / replacePluginId）
// TODO: axios.post(`api/space/admin/plugin/${params.pluginId}/status/?space_id=${params.spaceId}`, { status: params.status, category: params.category, offline_reason: params.offlineReason, replace_plugin_id: params.replacePluginId })
export function updatePluginStatus(params) {
  return mockUpdatePluginStatus(params);
}

// 批量更新插件状态（列表「更多操作」里的隐藏 / 显示 / 下架 / 上架）
// TODO: axios.post(`api/space/admin/plugin/batch_status/?space_id=${params.spaceId}`, { ids: params.ids, status: params.status })
export function batchUpdatePluginStatus(params) {
  return mockBatchUpdatePluginStatus(params);
}

// 批量移动插件所属分类（列表工具栏「批量移动」）
// followSource 为 true 时清除单独指定，回到来源分类绑定
// TODO: axios.post(`api/space/admin/plugin/batch_category/?space_id=${params.spaceId}`, { ids: params.ids, category: params.category, follow_source: params.followSource })
export function batchUpdatePluginCategory(params) {
  return mockBatchUpdatePluginCategory(params);
}

// 批量删除插件
// TODO: axios.delete(`api/space/admin/plugin/batch_delete/?space_id=${params.spaceId}`, { data: { ids: params.ids } })
export function deletePlugins(params) {
  return mockDeletePlugins(params);
}

// 批量清理失效插件设置记录（只删记录，不影响已有流程与引用记录）
// TODO: axios.delete(`api/space/admin/plugin/batch_clean/?space_id=${params.spaceId}`, { data: { ids: params.ids } })
export function cleanPlugins(params) {
  return mockCleanPlugins(params);
}

// 保存新插件策略（对象结构：{ mode, visibleAfterPass, visibleAiScope, conditions }）
// TODO: axios.post(`api/space/admin/plugin/strategy/?space_id=${params.spaceId}`, { strategy: params.strategy })
export function savePluginStrategy(params) {
  return mockSavePluginStrategy(params);
}

// 直通来源分组（「设条件自动通过」策略的直通来源选项）
// 返回: { groups: [{ id, name, icon, children: [{ id, name, whole }] }] }
// TODO: axios.get(`api/space/admin/plugin/strategy/sources/?space_id=${params.spaceId}`)
export function getStrategySources() {
  return mockGetStrategySources();
}

// 初始化插件分类目录
// TODO: axios.post(`api/space/admin/plugin/category/init/?space_id=${params.spaceId}`)
export function initCategories(params) {
  return mockInitCategories(params);
}

// 保存空间推荐顺序（拖拽松开即保存）
// TODO: axios.post(`api/space/admin/plugin/recommend/order/?space_id=${params.spaceId}`, { ids: params.ids })
export function saveRecommendOrder(params) {
  return mockSaveRecommendOrder(params);
}

// 取消推荐（立即生效并释放名额，共 10 个）
// TODO: axios.delete(`api/space/admin/plugin/recommend/${params.pluginId}/?space_id=${params.spaceId}`)
export function cancelRecommend(params) {
  return mockCancelRecommend(params);
}

// 新建分类（分类最多 2 级，parentId 留空表示第 1 级）
// data: { name, parentId, desc, bindings }
// TODO: axios.post(`api/space/admin/plugin/category/?space_id=${params.spaceId}`, params.data)
export function createCategory(params) {
  return mockCreateCategory(params);
}

// 编辑分类（复用新建抽屉，全量提交）
// TODO: axios.put(`api/space/admin/plugin/category/${params.categoryId}/?space_id=${params.spaceId}`, params.data)
export function updateCategory(params) {
  return mockUpdateCategory(params);
}

// 删除分类
// params: { spaceId, categoryId, strategy, targetCategoryId }
// strategy: promote-子分类升为第 1 级 / merge-并入其他第 1 级分类 / uncategorized-全部回到未分类
// TODO: axios.delete(`api/space/admin/plugin/category/${params.categoryId}/?space_id=${params.spaceId}`, { data: params })
export function deleteCategory(params) {
  return mockDeleteCategory(params);
}

// 删除前的影响评估：决定用「直接确认」还是「选择内容去向」的弹窗
// 返回: { level, name, parentName, childNames, pluginCount, bindingCount, firstLevelOptions }
// TODO: axios.get(`api/space/admin/plugin/category/${params.categoryId}/delete_impact/?space_id=${params.spaceId}`)
export function getCategoryDeleteImpact(params) {
  return mockGetCategoryDeleteImpact(params);
}

// 来源分类列表（新建/编辑分类抽屉的「来源绑定」）
// 返回: { groups: [{ id, name, icon, children: [{ id, name, whole, boundCategoryId, boundCategoryName }] }] }
// TODO: axios.get(`api/space/admin/plugin/category/binding_sources/?space_id=${params.spaceId}`, { params })
export function getBindingSources(params) {
  return mockGetBindingSources(params);
}

// 插件详情（列表点击插件名打开详情侧滑）
// params: { spaceId, plugin }
// 返回: { plugin, refs: { flowCount, versionCount, draftOnlyCount }, references: [] }
// TODO: axios.get(`api/space/admin/plugin/${params.plugin.id}/detail/?space_id=${params.spaceId}`)
export function getPluginDetail(params) {
  return mockGetPluginDetail(params);
}

// 插件引用流程列表（详情侧滑「当前引用」Tab）
// params: { spaceId, pluginId, scope, keyword, page, page_size }
// 返回: { count, results }
// TODO: axios.get(`api/space/admin/plugin/${params.pluginId}/references/?space_id=${params.spaceId}`, { params })
export function getPluginReferences(params) {
  return mockGetPluginReferences(params);
}

// 目录批量管理页数据：目录树 + 全量插件（页面内本地修改，保存时统一提交）
// TODO: axios.get(`api/space/admin/plugin/category/manage_data/?space_id=${params.spaceId}`)
export function getCategoryManageData(params) {
  return mockGetCategoryManageData(params);
}

// 目录批量管理页保存：整体提交目录结构与插件归属（deletedPluginIds 为本页删除的插件）
// TODO: axios.post(`api/space/admin/plugin/category/manage_save/?space_id=${params.spaceId}`, params)
export function saveCategoryManage(params) {
  return mockSaveCategoryManage(params);
}
