import i18n from '@/config/i18n/index.js';

// 条件字段描述
export const conditionFieldDesc = {
  equals: i18n.t('等于'),
  'not-equals': i18n.t('不等于'),
  // 'is-null': '为空',
  // 'not-null': '不为空',
  contains: i18n.t('包含'),
  'not-contains': i18n.t('不包含'),
  'greater-than': i18n.t('大于'),
  'less-than': i18n.t('小于'),
  'greater-than-or-equal': i18n.t('大于等于'),
  'less-than-or-equal': i18n.t('小于等于'),
  'in-range': i18n.t('在范围内'),
  'not-in-range': i18n.t('不在范围内'),
};

// 条件列表
export const getConditionList = (type) => {
  const conditionList = [];
  switch (type) {
    case 'string':
      conditionList.push(...[
        { key: 'contains', name: conditionFieldDesc.contains },
        { key: 'not-contains', name: conditionFieldDesc['not-contains'] },
      ]);
      break;
    case 'int':
      conditionList.push(...[
        { key: 'greater-than', name: conditionFieldDesc['greater-than'] },
        { key: 'less-than', name: conditionFieldDesc['less-than'] },
        { key: 'greater-than-or-equal', name: conditionFieldDesc['greater-than-or-equal'] },
        { key: 'less-than-or-equal', name: conditionFieldDesc['less-than-or-equal'] },
        { key: 'in-range', name: conditionFieldDesc['in-range'] },
      ]);
      break;
    case 'select':
      conditionList.push(...[
        { key: 'in-range', name: conditionFieldDesc['in-range'] },
        { key: 'not-in-range', name: conditionFieldDesc['not-in-range'] },
      ]);
      break;
  }
  return [
    { key: 'equals', name: conditionFieldDesc.equals },
    { key: 'not-equals', name: conditionFieldDesc['not-equals'] },
    ...conditionList,
    // { key: 'is-null', name: conditionFieldDesc['is-null'] },
    // { key: 'not-null', name: conditionFieldDesc['not-null'] },
  ];
};

// 列操作面板
export const columnOperateMenu =  [
  [
    {
      key: 'edit',
      label: i18n.t('编辑字段'),
      icon: 'bk-icon icon-edit-line',
    },
    {
      key: 'copy',
      label: i18n.t('复制字段'),
      icon: 'bk-icon icon-copy',
    },
  ],
  [
    {
      key: 'insert-left',
      label: i18n.t('向左插入1列'),
      icon: 'bk-icon icon-arrows-left-line',
    },
    {
      key: 'insert-right',
      label: i18n.t('向右插入1列'),
      icon: 'bk-icon icon-arrows-right--line',
    },
  ],
];

// 行操作面板
export const rowOperateMenu =  [
  [
    {
      key: 'copy',
      label: i18n.t('复制行'),
      icon: 'bk-icon icon-copy',
    },
    {
      key: 'group',
      label: i18n.t('组合条件设置'),
      icon: 'bk-icon icon-cog',
    },
  ],
  [
    {
      key: 'insert-top',
      label: i18n.t('向上插入1列'),
      icon: 'bk-icon icon-arrows-up-line',
    },
    {
      key: 'insert-bottom',
      label: i18n.t('向下插入1列'),
      icon: 'bk-icon icon-arrows-down-line',
    },
  ],
  [
    {
      key: 'delete',
      label: i18n.t('删除行'),
      icon: 'bk-icon icon-delete',
    },
  ],
];

// 生成单元格文案
export const generateCellText = (compare, value, cell) => {
  let text = value;
  // 下拉框类型
  const { type, options } = cell.column;
  if (type === 'select') {
    if (!Array.isArray(value)) {
      value = [value];
    }
    text = options.items.reduce((acc, cur) => {
      if (value.includes(cur.id)) {
        acc.push(cur.name);
      }
      return acc;
    }, []).join(' | ');
  }
  // 数组区间类型
  if (type === 'int' && compare === 'in-range') {
    text = `${value.start}到${value.end}`;
  }
  const compareText = compare === 'equals' ? '' : conditionFieldDesc[compare];
  // 为空/不为空
  if (['is-null', 'not-null'].includes(compare)) {
    return compareText || '';
  }
  // 等于
  if (compare === 'equals') {
    return text;
  }
  // 在范围内/不在范围内
  text = type === 'int' ? text : ` " ${text} " `;
  if (['in-range', 'not-in-range'].includes(compare)) {
    const insertIndex = compareText.length - 3;
    if (text) {
      return `${compareText.slice(0, insertIndex)}${text}${compareText.slice(insertIndex)}`;
    }
    return '';
  }

  return compareText + text;
};
