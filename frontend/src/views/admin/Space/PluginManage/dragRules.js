/**
 * Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
 * Edition) available.
 * Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 */

/**
 * 目录批量管理页「手动拖拽」的纯规则层：拖拽组解析、落点解析、落点校验、插件调序。
 */

// 拖拽项类型
export const DRAG_TYPE_DIR = 'dir';
export const DRAG_TYPE_PLUGIN = 'plugin';

// 落点类型：根级 / 未分类 / 移入目录 / 目标之前 / 目标之后
export const DROP_ROOT = 'root';
export const DROP_UNCATEGORIZED = 'uncategorized';
export const DROP_INTO = 'into';
export const DROP_BEFORE = 'before';
export const DROP_AFTER = 'after';

// 目录行上/下 25% 为调序区，中间为移入区；插件行按 50% 分两段
const DIR_REORDER_RATIO = 0.25;

// 在目录树中定位节点（一级 / 二级）
export function findCateInfo(categories = [], id) {
  for (const cate of categories) {
    if (cate.id === id) return { node: cate, level: 1, parentId: '', parent: null };
    const sub = (cate.children || []).find(item => item.id === id);
    if (sub) return { node: sub, level: 2, parentId: cate.id, parent: cate };
  }
  return null;
}

// id 是否在 ancestor 目录子树内
export function isDescendantCategory(id, ancestor) {
  return (ancestor.children || []).some(child => child.id === id || isDescendantCategory(id, child));
}

// 拖拽组中的目录信息（剔除父级也在组内的子目录，避免父子目录被拉平成同级）
export function getMovingCateInfos(categories = [], ids = []) {
  const idSet = new Set(ids);
  const infos = [];
  categories.forEach((cate) => {
    if (idSet.has(cate.id)) {
      infos.push({ node: cate, level: 1, parentId: '', parent: null });
      return;
    }
    (cate.children || []).forEach((sub) => {
      if (idSet.has(sub.id)) infos.push({ node: sub, level: 2, parentId: cate.id, parent: cate });
    });
  });
  return infos.filter(info => !infos.some(other => other.node !== info.node
    && isDescendantCategory(info.node.id, other.node)));
}

// 拖拽组解析：起拖项已勾选时拖动全部同类型勾选项，否则只拖当前项
export function resolveDragGroup({ checkedIds = [], categories = [], plugins = [], id, type }) {
  if (checkedIds.includes(id)) {
    const idSet = new Set(checkedIds);
    if (type === DRAG_TYPE_PLUGIN) {
      const ids = plugins.filter(plugin => idSet.has(plugin.id)).map(plugin => plugin.id);
      if (ids.length) return ids;
    } else {
      const ids = [];
      categories.forEach((cate) => {
        if (idSet.has(cate.id)) ids.push(cate.id);
        (cate.children || []).forEach((sub) => {
          if (idSet.has(sub.id)) ids.push(sub.id);
        });
      });
      if (ids.length) return ids;
    }
  }
  return [id];
}

// 行落点解析（ratio = 指针在行内的纵向比例）
export function resolveRowIntent({ dragType, rowType, ratio, targetId }) {
  // 插件落在目录行上统一为「移入该目录」（插件不参与目录序列的调序）
  if (dragType === DRAG_TYPE_PLUGIN && rowType === DRAG_TYPE_DIR) {
    return { kind: DROP_INTO, targetId };
  }
  if (rowType === DRAG_TYPE_DIR) {
    if (ratio < DIR_REORDER_RATIO) return { kind: DROP_BEFORE, targetId };
    if (ratio > 1 - DIR_REORDER_RATIO) return { kind: DROP_AFTER, targetId };
    return { kind: DROP_INTO, targetId };
  }
  return ratio < 0.5
    ? { kind: DROP_BEFORE, targetId }
    : { kind: DROP_AFTER, targetId };
}

// 落点校验：返回 { ok, reason }，reason 非空时用于气泡/错误提示
export function validateDrop({ categories = [], plugins = [], dnd, intent, t = key => key }) {
  if (!intent) return { ok: false, reason: '' };
  const { type, ids = [] } = dnd || {};
  if (!ids.length) return { ok: false, reason: '' };
  if (intent.kind === DROP_ROOT) {
    // 设计稿拦截：插件不能直接放在根目录下
    return type === DRAG_TYPE_PLUGIN
      ? { ok: false, reason: t('插件不能直接放在根目录下') }
      : { ok: true, reason: '' };
  }
  if (intent.kind === DROP_UNCATEGORIZED) {
    // 未分类只收插件（与「移动至...」规则一致）
    return type === DRAG_TYPE_PLUGIN
      ? { ok: true, reason: '' }
      : { ok: false, reason: t('只有插件可以移动到未分类') };
  }
  // 落点目标：优先按目录解析，其次按插件解析（插件行的 before/after 调序）
  const cateTarget = findCateInfo(categories, intent.targetId);
  const pluginTarget = cateTarget
    ? null
    : plugins.find(plugin => plugin.id === intent.targetId) || null;
  if ((!cateTarget && !pluginTarget) || ids.includes(intent.targetId)) {
    return { ok: false, reason: '' };
  }
  if (intent.kind === DROP_INTO) {
    if (!cateTarget) return { ok: false, reason: '' };
    if (type === DRAG_TYPE_PLUGIN) return { ok: true, reason: '' };
    const infos = getMovingCateInfos(categories, ids);
    // 不能移入自身或其子目录（先于层级判定，命中时提示更贴近实际操作）
    if (infos.some(info => isDescendantCategory(cateTarget.node.id, info.node))) {
      return { ok: false, reason: t('不能移动到自身或其子目录下') };
    }
    // 目录移入：最多 2 层，只能进一级目录
    if (cateTarget.level !== 1) return { ok: false, reason: t('目录最多只能有 2 层') };
    // 设计稿拦截：含有子目录的目录无法移动到别的目录下（移入即 3 层）
    if (infos.some(info => (info.node.children || []).length)) {
      return { ok: false, reason: t('含有子目录的目录，无法移动到别的目录下（一共只能拥有 2 层目录）') };
    }
    return { ok: true, reason: '' };
  }
  // before / after
  if (type === DRAG_TYPE_PLUGIN) {
    // 插件只允许在插件序列内调序（目录行已归一为 into）
    return pluginTarget
      ? { ok: true, reason: '' }
      : { ok: false, reason: t('插件不能直接放在根目录下') };
  }
  // 目录组（含「子目录 + 直属插件」混选）的调序校验
  const idSet = new Set(ids);
  const cateInfos = getMovingCateInfos(categories, ids);
  // 落到直属插件行：仅当同父混排（组内目录都是该插件直属一级目录的子目录、组内插件同归属）时允许
  if (!cateTarget) {
    if (!pluginTarget || !pluginTarget.category) return { ok: false, reason: '' };
    if (cateInfos.some(info => info.level !== 2 || info.parentId !== pluginTarget.category)) {
      return { ok: false, reason: '' };
    }
    if (plugins.some(plugin => idSet.has(plugin.id) && (plugin.category || '') !== pluginTarget.category)) {
      return { ok: false, reason: '' };
    }
    return { ok: true, reason: '' };
  }
  // 目录行调序落到二级层级：自身含子目录时会超 2 层
  if (cateTarget.level === 2 && cateInfos.some(info => (info.node.children || []).length)) {
    return { ok: false, reason: t('含有子目录的目录，无法移动到别的目录下（一共只能拥有 2 层目录）') };
  }
  // 混选组落到二级目录行：插件必须与目标目录同父（同一混排序列），否则整组无法一起移动
  if (cateTarget.level === 2
    && plugins.some(plugin => idSet.has(plugin.id) && (plugin.category || '') !== cateTarget.parentId)) {
    return { ok: false, reason: '' };
  }
  return { ok: true, reason: '' };
}

// 插件调序：跨栏拖拽时归属跟随目标插件（拖到某插件前/后即归入该插件所在目录）
// 返回 { list, updates, changed }：updates 为需要写回的归属变更（交给调用方 $set 保证响应式）
export function reorderPlugins({ plugins = [], ids = [], targetId, kind }) {
  const idSet = new Set(ids);
  const target = plugins.find(plugin => plugin.id === targetId);
  if (!target) return { list: plugins, updates: [], changed: false };
  const moving = plugins.filter(plugin => idSet.has(plugin.id));
  if (!moving.length) return { list: plugins, updates: [], changed: false };
  const targetCategory = target.category || '';
  const updates = moving
    .filter(plugin => (plugin.category || '') !== targetCategory)
    .map(plugin => ({ plugin, category: targetCategory }));
  const rest = plugins.filter(plugin => !idSet.has(plugin.id));
  const idx = rest.findIndex(plugin => plugin.id === targetId);
  const insertIdx = idx < 0 ? rest.length : idx + (kind === DROP_AFTER ? 1 : 0);
  const list = [...rest.slice(0, insertIdx), ...moving, ...rest.slice(insertIdx)];
  const orderChanged = list.some((plugin, index) => plugin.id !== plugins[index].id);
  return { list, updates, changed: Boolean(orderChanged || updates.length) };
}

// 第二栏混排序列（某一级目录下的子目录 + 直属插件）整组调序：
// 目录存于父级 children、插件存于 plugins（category = 父级 id），展示时拼接为同一列表，
// 跨类型边界的调序需同时回写两个序列（目录相对顺序 + 同归属插件相对顺序）
// 返回 { children, plugins, changed }
export function reorderMixedColumn({ children = [], plugins = [], parentId, ids = [], targetId, kind }) {
  const idSet = new Set(ids);
  const itemKey = item => (item.kind === DRAG_TYPE_DIR ? item.node.id : item.plugin.id);
  const catPlugins = plugins.filter(plugin => (plugin.category || '') === parentId);
  const seq = [
    ...children.map(node => ({ kind: DRAG_TYPE_DIR, node })),
    ...catPlugins.map(plugin => ({ kind: DRAG_TYPE_PLUGIN, plugin })),
  ];
  const groupIdxs = [];
  seq.forEach((item, index) => {
    if (idSet.has(itemKey(item))) groupIdxs.push(index);
  });
  if (!groupIdxs.length) return { children, plugins, changed: false };
  const group = groupIdxs.map(index => seq[index]);
  const groupSet = new Set(groupIdxs);
  const rest = seq.filter((item, index) => !groupSet.has(index));
  // 摘除组后重新定位目标，按 before / after 插回
  const restTargetIdx = rest.findIndex(item => itemKey(item) === targetId);
  if (restTargetIdx < 0) return { children, plugins, changed: false };
  const insertIdx = restTargetIdx + (kind === DROP_AFTER ? 1 : 0);
  const nextSeq = [...rest.slice(0, insertIdx), ...group, ...rest.slice(insertIdx)];
  const nextChildren = nextSeq.filter(item => item.kind === DRAG_TYPE_DIR).map(item => item.node);
  const nextCatPlugins = nextSeq.filter(item => item.kind === DRAG_TYPE_PLUGIN).map(item => item.plugin);
  // 同归属插件按原槽位写回，其他归属插件位置不变
  const positions = [];
  plugins.forEach((plugin, index) => {
    if ((plugin.category || '') === parentId) positions.push(index);
  });
  const nextPlugins = plugins.slice();
  positions.forEach((pos, index) => {
    nextPlugins[pos] = nextCatPlugins[index];
  });
  const sameOrder = (a, b) => a.length === b.length && a.every((item, index) => item === b[index]);
  // changed 按整个混排序列（视觉顺序）判定：跨类型边界移动时两个子序列可能各自不变
  const changed = !sameOrder(seq.map(itemKey), nextSeq.map(itemKey));
  return { children: nextChildren, plugins: nextPlugins, changed };
}
