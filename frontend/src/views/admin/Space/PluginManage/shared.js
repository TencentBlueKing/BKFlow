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
    visibleAfterPass: 'uncategorized',
    visibleAiScope: 'increment',
    conditions: [],
  };
}

// 插件状态文案与图标
export function getStatusMap(t) {
  return {
    visible: { label: t('可用'), icon: 'commonicon-icon common-icon-yuan-dui' },
    review: { label: t('待审核'), icon: 'commonicon-icon common-icon-daishenhe' },
    invalid: { label: t('已失效'), icon: 'commonicon-icon common-icon-yuan-jinggao' },
    rejected: { label: t('未启用'), icon: 'commonicon-icon common-icon-shixiao' },
  };
}

export function getStatusTabs(counts = {}, t) {
  return [
    { value: 'visible', label: t('启用'), icon: 'commonicon-icon common-icon-yuan-dui', count: counts.visible || 0, badgeClass: 'is-active' },
    { value: 'invalid', label: t('已失效'), icon: 'commonicon-icon common-icon-yuan-jinggao', count: counts.invalid || 0, badgeClass: 'is-active' },
    { divider: true },
    { value: 'review', label: t('待审核'), icon: 'commonicon-icon common-icon-daishenhe', count: counts.review || 0, badgeClass: 'is-warn' },
    { value: 'rejected', label: t('未启用'), icon: 'commonicon-icon common-icon-shixiao', count: counts.rejected || 0, badgeClass: 'is-active' },
  ];
}

// 插件类型下拉选项
export function getTypeOptions(t) {
  return [
    { value: 'all', label: t('全部') },
    { value: 'api', label: t('API 插件') },
    { value: 'bk_plugin', label: t('蓝鲸插件') },
    { value: 'builtin', label: t('内置') },
    { value: 'remote_api', label: t('远程 API 来源') },
  ];
}

// 插件类型文案
export function getTypeText(type, t) {
  const map = {
    api: t('API 插件'),
    bk_plugin: t('蓝鲸插件'),
    builtin: t('内置'),
    remote_api: t('远程 API 来源'),
  };
  return map[type] || '--';
}

// 插件来源下拉选项
export function getSourceOptions(t) {
  return [
    { value: 'all', label: t('全部') },
    { value: 'job', label: t('作业平台(JOB)') },
    { value: 'message', label: t('消息通知') },
    { value: 'bk', label: t('蓝鲸服务(BK)') },
    { value: 'ticket', label: t('工单') },
    { value: 'monitor', label: t('蓝鲸监控') },
  ];
}

// 插件来源文案
export function getSourceText(source, t) {
  const map = {
    job: t('作业平台(JOB)'),
    message: t('消息通知'),
    bk: t('蓝鲸服务(BK)'),
    ticket: t('工单'),
    monitor: t('蓝鲸监控'),
  };
  return source ? (map[source] || '--') : '--';
}

// 状态变更成功提示文案
export function getStatusChangeMessage(status, t) {
  const map = {
    visible: t('上架成功'),
    review: t('已通过审核'),
    rejected: t('已忽略'),
  };
  return map[status] || t('操作成功');
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
  if (category === 'uncategorized') return !row.category;
  const group = categories.find(item => item.id === category);
  if (group) {
    const childIds = (group.children || []).map(child => child.id);
    return row.category === group.id || childIds.includes(row.category);
  }
  return row.category === category;
}

// 所属分类名称（找不到时回落 '--'）
export function getCategoryPath(categories, categoryId) {
  const cate = (categories || []).find(item => item.id === categoryId);
  return cate ? cate.name : '--';
}

// 行内操作：按当前状态推导可执行动作
export function getRowActions(row, t) {
  const actionMap = {
    visible: [
      { label: t('编辑'), type: 'edit' },
      { label: t('停用'), type: 'status', status: 'rejected' },
    ],
    review: [
      { label: t('通过'), type: 'status', status: 'visible', message: t('已通过审核') },
      { label: t('忽略'), type: 'status', status: 'rejected' },
    ],
    rejected: [
      { label: t('通过'), type: 'status', status: 'visible', message: t('已通过审核') },
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
