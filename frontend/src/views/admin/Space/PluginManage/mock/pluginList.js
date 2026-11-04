/**
 * 插件管理 Mock 实现
 */
import { matchPluginCategory, flattenCategories } from '../shared';
import {
  DEFAULT_CATEGORIES,
  MOCK_PLUGINS,
  MOCK_STRATEGY,
  MOCK_PLUGIN_REFERENCES,
  MOCK_BINDING_SOURCE_GROUPS,
} from './data';

// 模拟请求耗时
const MOCK_DELAY = 300;

const delay = data => new Promise((resolve) => {
  setTimeout(() => resolve(data), MOCK_DELAY);
});

// Mock 运行态：写操作直接落到这里，保证「重新拉列表」能拿到一致数据
const state = {
  plugins: MOCK_PLUGINS.map(item => ({ ...item })),
  categories: JSON.parse(JSON.stringify(DEFAULT_CATEGORIES)),
  strategy: MOCK_STRATEGY,
};

// 按分类过滤（列表与各状态计数共用）
function filterByCategory(category) {
  return state.plugins.filter(row => matchPluginCategory(row, category, state.categories));
}

// 状态计数：已失效不计入「全部」（设计稿 figma 180-3364 备注 a）
function countByStatus(list) {
  const counts = { all: 0, review: 0, visible: 0, hidden: 0, offline: 0, invalid: 0, rejected: 0 };
  list.forEach((row) => {
    if (counts[row.status] !== undefined) {
      counts[row.status] += 1;
    }
    if (row.status !== 'invalid') {
      counts.all += 1;
    }
  });
  return counts;
}

// 枚举过滤值统一为数组：'all' / '' 视为不过滤，字符串单值转数组，数组直接使用
function toFilterList(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  return value && value !== 'all' ? [value] : [];
}

// 手动输入关键词统一为数组：字符串单值转数组，数组直接使用，去空并小写化
function toKeywordList(value) {
  const list = Array.isArray(value) ? value : [value];
  const result = [];
  list.forEach((item) => {
    const raw = String(item || '');
    const text = raw.trim().toLowerCase();
    if (text) result.push(text);
  });
  return result;
}

// 按状态 / 类型 / 来源 / 关键字 / 搜索条件过滤
// searchName / searchDesc / searchUpdatedBy 为输入型模糊匹配（设计稿 figma 2022-19225），
// searchCategory 为枚举型目录过滤（与左侧分类目录叠加，进一步收窄）
// type / source / searchCategory 支持数组多选：命中其一即保留
// keyword（不选择条件的手动输入）为多词 OR：任一词命中「插件名称」或「最近修改人」即保留
function filterByCondition(list, {
  status, type, source, keyword,
  searchName, searchDesc, searchUpdatedBy, searchCategory,
}) {
  const keywordList = toKeywordList(keyword);
  const kwName = (searchName || '').trim().toLowerCase();
  const kwDesc = (searchDesc || '').trim().toLowerCase();
  const kwUpdatedBy = (searchUpdatedBy || '').trim().toLowerCase();
  const typeList = toFilterList(type);
  const sourceList = toFilterList(source);
  const categoryList = toFilterList(searchCategory);
  return list.filter((row) => {
    if (status === 'all') {
      if (row.status === 'invalid') return false;
    } else if (status && row.status !== status) {
      return false;
    }
    if (typeList.length && !typeList.includes(row.type)) return false;
    if (sourceList.length && !sourceList.includes(row.source)) return false;
    if (categoryList.length && !categoryList.includes(row.category)) return false;
    if (kwName && !(row.name || '').toLowerCase().includes(kwName)) return false;
    if (kwDesc && !(row.desc || '').toLowerCase().includes(kwDesc)) return false;
    if (kwUpdatedBy && !(row.updatedBy || '').toLowerCase().includes(kwUpdatedBy)) return false;
    if (keywordList.length) {
      const fields = [row.name, row.updatedBy].map(field => (field || '').toLowerCase());
      if (!keywordList.some(kw => fields.some(field => field.includes(kw)))) return false;
    }
    return true;
  });
}

// 空间推荐按 recommendOrder 升序
function sortByRecommendOrder(list) {
  return [...list].sort((a, b) => (a.recommendOrder || Infinity) - (b.recommendOrder || Infinity));
}

// 定位分类节点：返回节点本身、所在数组与下标、父节点（二级才有），供移动 / 删除复用
function findCategory(id) {
  if (!id) return null;
  const index = state.categories.findIndex(item => item.id === id);
  if (index > -1) {
    return { node: state.categories[index], list: state.categories, index, parent: null };
  }
  for (let i = 0; i < state.categories.length; i++) {
    const parent = state.categories[i];
    const children = parent.children || [];
    const childIndex = children.findIndex(item => item.id === id);
    if (childIndex > -1) {
      return { node: children[childIndex], list: children, index: childIndex, parent };
    }
  }
  return null;
}

// 把若干分类下的插件移到目标分类（targetId 为空表示回到「未分类」）
function movePlugins(fromIds, targetId) {
  state.plugins.forEach((row) => {
    if (fromIds.includes(row.category)) {
      row.category = targetId;
    }
  });
}

// 把来源绑定并入目标分类（去重）
function mergeBindings(target, bindings = []) {
  target.bindings = [...new Set([...(target.bindings || []), ...bindings])];
}

// 一个来源分类只能绑定一个空间分类：本分类选中后，其他分类上的同名绑定要解除
function syncBindings(categoryId, bindings = []) {
  const walk = (node) => {
    if (node.id !== categoryId) {
      node.bindings = (node.bindings || []).filter(item => !bindings.includes(item));
    }
    (node.children || []).forEach(walk);
  };
  state.categories.forEach(walk);
}

// 来源分类 id -> 名称（删除影响的绑定明细展示用，找不到就回退成 id）
function getSourceName(sourceId) {
  for (let i = 0; i < MOCK_BINDING_SOURCE_GROUPS.length; i++) {
    const hit = (MOCK_BINDING_SOURCE_GROUPS[i].children || []).find(item => item.id === sourceId);
    if (hit) return hit.name;
  }
  return sourceId;
}


// 插件概要：分类目录 / 分类计数 / 新插件策略 / 老版本节点数
// plugins 全量目前仅用于「新插件策略」的影响名单，后端可用独立字段下发后删除
export function mockGetPluginSummary() {
  const counts = {
    all: state.plugins.length,
    recommend: state.plugins.filter(item => item.recommended).length,
    uncategorized: state.plugins.filter(item => !item.category).length,
    tree: {},
  };
  flattenCategories(state.categories).forEach((cate) => {
    counts.tree[cate.id] = state.plugins.filter(item => item.category === cate.id).length;
  });
  return delay({
    categories: state.categories,
    counts,
    strategy: state.strategy,
    plugins: state.plugins,
  });
}

// 插件列表：分类 / 状态 / 类型 / 来源 / 关键字 / 搜索条件 / 分页 / 排序由后端处理
export function mockGetPluginList({
  category = 'all',
  status = 'all',
  type = 'all',
  source = 'all',
  keyword = [],
  searchName = '',
  searchDesc = '',
  searchUpdatedBy = '',
  searchCategory = '',
  page = 1,
  page_size: pageSize = 10,
}) {
  const byCategory = filterByCategory(category);
  // 除「状态」外的查询条件（关键字 / 类型 / 来源 / 各搜索项）
  const conditions = {
    type, source, keyword,
    searchName, searchDesc, searchUpdatedBy, searchCategory,
  };
  // Tab 计数：按上述条件过滤后再按状态统计，使搜索/筛选后各 Tab 数量跟随结果变化。
  // status 传空串表示不按状态过滤，否则除当前 Tab 外的其他 Tab 计数恒为 0。
  const statusCounts = countByStatus(filterByCondition(byCategory, { ...conditions, status: '' }));
  const list = filterByCondition(byCategory, { ...conditions, status });
  const sorted = category === 'recommend' ? sortByRecommendOrder(list) : list;
  const start = (page - 1) * pageSize;
  return delay({
    count: sorted.length,
    results: sorted.slice(start, start + pageSize),
    status_counts: statusCounts,
  });
}

// 空间推荐列表
export function mockGetRecommendList() {
  return delay({ results: sortByRecommendOrder(state.plugins.filter(item => item.recommended)) });
}

// 编辑插件：所属分类 / 空间推荐 / 下架配置（下架原因、替换插件）
// 推荐开关变化时同步维护 recommendOrder：开启排到末尾，关闭置空并释放名额
export function mockUpdatePlugin({ pluginId, data }) {
  const row = state.plugins.find(item => item.id === pluginId);
  if (row) {
    Object.assign(row, {
      category: data.category,
      recommended: !!data.recommended,
      offlineReason: data.offlineReason || '',
      replacePluginId: data.replacePluginId || '',
    });
    if (row.recommended && !row.recommendOrder) {
      const maxOrder = state.plugins.reduce((max, item) => Math.max(max, item.recommendOrder || 0), 0);
      row.recommendOrder = maxOrder + 1;
    }
    if (!row.recommended) {
      row.recommendOrder = null;
    }
  }
  return delay(row);
}

// 更新单个插件状态（待审核通过携带 category 落库目标目录；下架时携带并落库下架配置，保证编辑侧滑可回显）
export function mockUpdatePluginStatus({ pluginId, status, category, offlineReason, replacePluginId }) {
  const row = state.plugins.find(item => item.id === pluginId);
  if (row) {
    row.status = status;
    if (category !== undefined) {
      row.category = category;
    }
    if (status === 'offline') {
      if (offlineReason !== undefined) {
        row.offlineReason = offlineReason;
      }
      if (replacePluginId !== undefined) {
        row.replacePluginId = replacePluginId;
      }
      row.offlineBy = 'admin';
      row.offlineTime = new Date().toLocaleString('zh-CN', { hour12: false })
        .replace(/\//g, '-');
    }
  }
  return delay({ pluginId, status });
}

// 批量更新插件状态
export function mockBatchUpdatePluginStatus({ ids, status }) {
  state.plugins.forEach((row) => {
    if (ids.includes(row.id)) {
      row.status = status;
    }
  });
  return delay({ ids, status });
}

// 批量移动插件所属分类
export function mockBatchUpdatePluginCategory({ ids, category, followSource }) {
  state.plugins.forEach((row) => {
    if (ids.includes(row.id)) {
      row.category = followSource ? '' : category;
    }
  });
  return delay({ ids, category, followSource });
}

// 批量删除插件
export function mockDeletePlugins({ ids }) {
  state.plugins = state.plugins.filter(item => !ids.includes(item.id));
  return delay({ ids });
}

// 批量清理失效插件的设置记录（只删记录，不影响已有流程与引用记录）
export function mockCleanPlugins({ ids }) {
  state.plugins = state.plugins.filter(item => !ids.includes(item.id));
  return delay({ ids });
}

// 保存新插件策略（对象结构：{ mode, visibleAfterPass, visibleAiScope, conditions }）
export function mockSavePluginStrategy({ strategy }) {
  state.strategy = strategy;
  return delay({ strategy });
}

// 直通来源分组（「设条件自动通过」策略的直通来源选项）
export function mockGetStrategySources() {
  return delay({ groups: MOCK_BINDING_SOURCE_GROUPS });
}

// 初始化分类目录
export function mockInitCategories() {
  state.categories = JSON.parse(JSON.stringify(DEFAULT_CATEGORIES));
  return delay({ categories: state.categories });
}

// 保存空间推荐顺序
export function mockSaveRecommendOrder({ ids }) {
  ids.forEach((id, index) => {
    const row = state.plugins.find(item => item.id === id);
    if (row) {
      row.recommendOrder = index + 1;
    }
  });
  return delay({ ids });
}

// 取消推荐（立即生效并释放名额）
export function mockCancelRecommend({ pluginId }) {
  const row = state.plugins.find(item => item.id === pluginId);
  if (row) {
    row.recommended = false;
  }
  return delay({ pluginId });
}

// 分类目录移动：position 为 before / after（同级排序）或 inner（移动到目标分类下）
// targetId 为空 + position=inner 表示升为第 1 级
export function mockSaveCategoryOrder({ id, targetId, position = 'after' }) {
  const found = findCategory(id);
  if (!found) return delay({ id, targetId, position });
  // 先从原位置摘出来
  found.list.splice(found.index, 1);
  if (position === 'inner') {
    const parent = targetId ? state.categories.find(item => item.id === targetId) : null;
    if (parent) {
      // 二级不能再有子级：被移动节点的子级一并升为第 1 级
      (found.node.children || []).forEach(child => state.categories.push(child));
      found.node.children = [];
      parent.children = parent.children || [];
      parent.children.push(found.node);
    } else {
      found.node.children = found.node.children || [];
      state.categories.push(found.node);
    }
    return delay({ id, targetId, position });
  }
  const target = findCategory(targetId);
  if (!target) {
    found.list.splice(found.index, 0, found.node);
    return delay({ id, targetId, position });
  }
  // 跨层级拖到二级节点旁边时，被移动节点自身的子级升为第 1 级
  if (target.parent && (found.node.children || []).length) {
    found.node.children.forEach(child => state.categories.push(child));
    found.node.children = [];
  }
  const offset = position === 'before' ? 0 : 1;
  target.list.splice(target.index + offset, 0, found.node);
  return delay({ id, targetId, position });
}

// 新建分类：父分类留空时作为第 1 级
export function mockCreateCategory({ data }) {
  const node = {
    id: `cate_${Date.now()}`,
    name: data.name,
    desc: data.desc || '',
    bindings: data.bindings || [],
    children: [],
  };
  syncBindings(node.id, node.bindings);
  const parent = data.parentId ? state.categories.find(item => item.id === data.parentId) : null;
  if (parent) {
    parent.children = parent.children || [];
    parent.children.push(node);
  } else {
    state.categories.push(node);
  }
  return delay({ category: node });
}

// 编辑分类：名称 / 描述 / 父分类 / 来源绑定全量提交
export function mockUpdateCategory({ categoryId, data }) {
  const found = findCategory(categoryId);
  if (!found) return delay({ categoryId });
  const { node } = found;
  node.name = data.name;
  node.desc = data.desc || '';
  node.bindings = data.bindings || [];
  syncBindings(node.id, node.bindings);
  const currentParentId = found.parent ? found.parent.id : '';
  const nextParentId = data.parentId || '';
  if (currentParentId !== nextParentId) {
    mockSaveCategoryOrder({ id: categoryId, targetId: nextParentId, position: 'inner' });
  }
  return delay({ category: node });
}

// 删除分类的影响：决定前端用「直接确认」还是「选择去向」的弹窗
export function mockGetCategoryDeleteImpact({ categoryId }) {
  const found = findCategory(categoryId);
  if (!found) return delay({});
  const { node, parent } = found;
  const childIds = (node.children || []).map(item => item.id);
  const scopeIds = [node.id, ...childIds];
  const inScope = state.plugins.filter(item => scopeIds.includes(item.category));
  const pluginCount = inScope.length;
  // 已下架插件数与直接挂在本分类下的插件数：弹窗要如实告知，避免用户误判影响面
  const offlineCount = inScope.filter(item => item.status === 'offline').length;
  const directPluginCount = inScope.filter(item => item.category === node.id).length;
  // 来源绑定明细：来源名 -> 绑定所在的分类名（本分类或它的某个子分类）
  const bindings = [];
  [node, ...(node.children || [])].forEach((cate) => {
    (cate.bindings || []).forEach((sourceId) => {
      bindings.push({ sourceName: getSourceName(sourceId), categoryName: cate.name });
    });
  });
  return delay({
    level: parent ? 2 : 1,
    name: node.name,
    parentName: parent ? parent.name : '',
    childNames: (node.children || []).map(item => item.name),
    pluginCount,
    offlineCount,
    directPluginCount,
    bindingCount: bindings.length,
    bindings,
    // 「并入其他第 1 级分类」的候选（排除自己）
    firstLevelOptions: state.categories
      .filter(item => item.id !== node.id)
      .map(item => ({ id: item.id, name: item.name })),
  });
}

// 删除分类
// strategy: promote-子分类升为第 1 级 / merge-并入 targetCategoryId / uncategorized-全部回到未分类
export function mockDeleteCategory({ categoryId, strategy = 'promote', targetCategoryId = '' }) {
  const found = findCategory(categoryId);
  if (!found) return delay({ categoryId });
  const { node, list, index, parent } = found;
  const children = node.children || [];
  const childIds = children.map(item => item.id);
  list.splice(index, 1);

  if (parent) {
    // 二级分类：其下插件与绑定移到所属的第 1 级分类
    movePlugins([node.id], parent.id);
    mergeBindings(parent, node.bindings);
  } else if (strategy === 'merge' && targetCategoryId) {
    const target = state.categories.find(item => item.id === targetCategoryId);
    if (target) {
      target.children = [...(target.children || []), ...children];
      movePlugins([node.id], target.id);
      mergeBindings(target, node.bindings);
    }
  } else if (strategy === 'uncategorized') {
    movePlugins([node.id, ...childIds], '');
  } else {
    // promote：子分类升为第 1 级，直接挂在本分类下的插件回到未分类
    children.forEach(child => state.categories.push(child));
    movePlugins([node.id], '');
  }
  return delay({ categoryId });
}

// 来源分类列表：标注每个来源当前绑定到哪个分类（编辑自己时不算已绑定）
export function mockGetBindingSources({ categoryId = '' }) {
  const flat = flattenCategories(state.categories);
  const bindingMap = {};
  flat.forEach((cate) => {
    const found = findCategory(cate.id);
    if (!found) return;
    (found.node.bindings || []).forEach((sourceId) => {
      bindingMap[sourceId] = { id: cate.id, name: cate.name };
    });
  });
  const groups = MOCK_BINDING_SOURCE_GROUPS.map(group => ({
    ...group,
    children: group.children.map((item) => {
      const bound = bindingMap[item.id];
      const isSelf = bound && bound.id === categoryId;
      return {
        ...item,
        boundCategoryId: bound && !isSelf ? bound.id : '',
        boundCategoryName: bound && !isSelf ? bound.name : '',
      };
    }),
  }));
  return delay({ groups });
}

// 引用范围筛选：all-全部 / published-发布版本引用 / draft-草稿引用
function filterByScope(list, scope) {
  if (scope === 'published') return list.filter(item => item.publishedNodes > 0);
  if (scope === 'draft') return list.filter(item => item.draftNodes > 0);
  return list;
}

// 插件详情：引用统计与引用流程一次下发，避免侧滑头部再来一次请求
export function mockGetPluginDetail({ plugin }) {
  const references = MOCK_PLUGIN_REFERENCES.filter(item => item.pluginId === plugin.id);
  const refs = {
    // 引用记录本身就是流程维度，此处按流程去重
    flowCount: references.length,
    versionCount: references.filter(item => item.publishedNodes > 0).length,
    draftOnlyCount: references.filter(item => !item.publishedNodes && item.draftNodes > 0).length,
  };
  return delay({ plugin: { ...plugin }, refs, references });
}

// 插件引用流程列表：引用范围 / 关键字 / 分页由后端处理
export function mockGetPluginReferences({
  pluginId,
  scope = 'all',
  keyword = '',
  page = 1,
  page_size: pageSize = 10,
}) {
  const kw = (keyword || '').trim().toLowerCase();
  const list = filterByScope(
    MOCK_PLUGIN_REFERENCES.filter(item => item.pluginId === pluginId),
    scope,
  ).filter((item) => {
    if (!kw) return true;
    return [item.flowName, item.maintainer].some(field => (field || '').toLowerCase().includes(kw));
  });
  const start = (page - 1) * pageSize;
  return delay({
    count: list.length,
    results: list.slice(start, start + pageSize),
  });
}

// 目录批量管理页数据：目录树 + 全量插件
export function mockGetCategoryManageData() {
  return delay({
    categories: JSON.parse(JSON.stringify(state.categories)),
    plugins: state.plugins.map(item => ({ ...item })),
  });
}

// 目录批量管理页保存：整体提交目录结构与插件归属（含本页删除的插件）
export function mockSaveCategoryManage({ categories, plugins, deletedPluginIds }) {
  if (Array.isArray(categories)) {
    state.categories = JSON.parse(JSON.stringify(categories));
  }
  const deleted = new Set(deletedPluginIds || []);
  state.plugins = state.plugins.filter(row => !deleted.has(row.id));
  (plugins || []).forEach(({ id, category }) => {
    const row = state.plugins.find(item => item.id === id);
    if (row) row.category = category || '';
  });
  return delay({ saved: true });
}
