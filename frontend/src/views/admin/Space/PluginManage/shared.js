/**
 * 插件管理模块共用逻辑
 */

// 空间推荐名额上限
export const MAX_RECOMMEND = 10;

// 目录分类图标
export const CATEGORY_ICONS = {
  all: 'commonicon-icon common-icon-shitu-lianglan',
  recommend: 'bk-icon icon-star',
  uncategorized: 'bk-icon icon-question-circle',
  level1: 'commonicon-icon common-icon-file-open-dakaiwenjianjia',
  level2: 'commonicon-icon common-icon-file-close-shouqiwenjianjia',
};

// 新插件策略的默认结构
export function createDefaultStrategy() {
  return {
    mode: 'review',
  };
}

export function normalizePluginStatus(status) {
  return ['disabled', 'expired'].includes(status) ? 'not_enable' : status;
}

// 插件状态文案与图标
export function getStatusMap(t) {
  return {
    enable: { label: t('启用'), icon: 'commonicon-icon common-icon-yuan-dui' },
    pending_review: { label: t('待审核'), icon: 'commonicon-icon common-icon-daishenhe' },
    not_enable: { label: t('未启用'), icon: 'commonicon-icon common-icon-shixiao' },
  };
}

export function getStatusTabs(counts = {}, t) {
  return [
    { value: 'enable', label: t('启用'), icon: 'commonicon-icon common-icon-yuan-dui', count: counts.enable || 0, badgeClass: 'is-active' },
    { divider: true },
    { value: 'pending_review', label: t('待审核'), icon: 'commonicon-icon common-icon-daishenhe', count: counts.pending_review || 0, badgeClass: 'is-warn' },
    { value: 'not_enable', label: t('未启用'), icon: 'commonicon-icon common-icon-shixiao', count: counts.not_enable || 0, badgeClass: 'is-active' },
  ];
}

// 插件类型下拉选项
export function getTypeOptions(t) {
  return [
    { value: 'all', label: t('全部') },
    { value: 'api', label: t('API 插件') },
    { value: 'bk_plugin', label: t('蓝鲸插件') },
    { value: 'builtin', label: t('内置插件') },
  ];
}

// 插件类型文案
export function getTypeText(type, t) {
  const map = {
    api: t('API 插件'),
    bk_plugin: t('蓝鲸插件'),
    builtin: t('内置插件'),
  };
  return map[type] || '--';
}

// 插件来源下拉选项（来源即插件类型：内置 / 蓝鲸 / API 三种）
export function getSourceOptions(t) {
  return [
    { value: 'all', label: t('全部') },
    { value: 'api', label: t('API 插件') },
    { value: 'bk_plugin', label: 'PaaS' },
    { value: 'builtin', label: 'BKflow' },
  ];
}

// 插件来源文案
export function getSourceText(sourceKey, t) {
  if (!sourceKey) return '--';
  const key = String(sourceKey);
  if (key.includes('/')) return key;
  const map = {
    api: t('API 插件'),
    bk_plugin: 'PaaS',
    builtin: 'BKflow',
  };
  return map[key] || key;
}

// 来源筛选匹配
export function matchPluginSource(sourceKey, value) {
  const key = String(sourceKey || '');
  if (value === 'api') {
    return key !== 'bk_plugin' && key !== 'builtin';
  }
  return key === value;
}

// 状态变更成功提示文案
export function getStatusChangeMessage(status, t) {
  const map = {
    enable: t('已启用'),
    pending_review: t('已转入待审核'),
    disabled: t('已停用'),
    not_enable: t('已停用'),
  };
  return map[status] || t('操作成功');
}

export function mapBackendStatus(fromStatus, status) {
  if (status === 'not_enable') {
    return 'disabled';
  }
  return status;
}

// 扁平化分类（下拉选择、分类计数用），子级名称带父级前缀
export function flattenCategories(categories = []) {
  const list = [];
  (categories || []).forEach((group) => {
    list.push({ id: group.id, name: group.name });
    (group.children || []).forEach((child) => {
      list.push({ id: child.id, name: `${group.name} / ${child.name}` });
    });
  });
  return list;
}

// 分类 id -> 分类自身名称（只取最后一层，不含父级路径），供列表标题等处直接按 id 取值
export function buildCategoryNameMap(categories = []) {
  const map = {};
  (categories || []).forEach((group) => {
    map[group.id] = group.name;
    (group.children || []).forEach((child) => {
      map[child.id] = child.name;
    });
  });
  return map;
}

// 插件是否属于指定分类：all 全部 / recommend 空间推荐 / uncategorized 未分类 / 具体分类 id（父级包含其子级）
export function matchPluginCategory(row, category, categories = []) {
  if (!category || category === 'all') return true;
  if (category === 'recommend') return !!row.recommended;
  if (category === 'uncategorized') return !row.directory_id;
  const directoryId = String(row.directory_id);
  const group = categories.find(item => String(item.id) === String(category));
  if (group) {
    const childIds = (group.children || []).map(child => String(child.id));
    return directoryId === String(group.id) || childIds.includes(directoryId);
  }
  return directoryId === String(category);
}

// 所属分类名称（找不到时回落 '--'）
export function getCategoryPath(categories, categoryId) {
  const id = String(categoryId);
  const cate = (categories || []).find(item => String(item.id) === id);
  return cate ? cate.name : '--';
}

// 行内操作
export function getRowActions(row, t) {
  const actionMap = {
    enable: [
      { label: t('编辑'), type: 'edit' },
      { label: t('停用'), type: 'status', status: 'disabled' },
    ],
    pending_review: [
      { label: t('启用'), type: 'status', status: 'enable', message: t('已启用') },
      { label: t('不启用'), type: 'status', status: 'disabled' },
    ],
    disabled: [
      { label: t('启用'), type: 'status', status: 'enable', message: t('已启用') },
    ],
  };
  return actionMap[row.status] || [];
}

// 所属分类列头
export function renderCategoryHeader(h, column, t) {
  const tipsItems = [
    { icon: 'common-icon-link-guanlian', text: t('跟随来源分类绑定') },
    { icon: 'common-icon-shoudongqueren', text: t('用户手动调整') },
  ];
  return h('bk-popover', {
    props: {
      placement: 'top-start',
      width: 270,
      theme: 'light',
      transfer: true,
      extCls: 'category-header-popover',
    },
  }, [
    h('span', { class: 'category-header-label' }, [column.label]),
    h('div', { slot: 'content', class: 'category-tips-content' }, [
      h('p', { class: 'tips-title' }, [column.label]),
      h('ul', { class: 'tips-list' }, tipsItems.map(item => h('li', { class: 'tips-item' }, [
        h('span', { class: 'tips-item-inner' }, [
          h('i', { class: ['tips-icon', item.icon] }),
          h('span', [item.text]),
        ]),
      ]))),
    ]),
  ]);
}
