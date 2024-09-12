const operateMap = {
  equals: '',
  'not-equals': '!=',
  contains: 'contains',
  'not-contains': 'not contains',
  'greater-than': '>',
  'less-than': '<',
  'greater-than-or-equal': '>=',
  'less-than-or-equal': '<=',
  // 范围条件特殊处理
};

const intRegex = /^\d+$/;

export const getCellText = (data = {}) => {
  const { compare, right = {} } = data;
  if (!compare) return '--';
  const { type, value } = right.obj;
  // 非范围条件
  if (compare in operateMap) {
    return `${operateMap[compare]} ${value}`;
  }
  // 范围条件
  const isIntRange = type === 'int[Range]';
  let text = Array.isArray(value) ? value.join(',') : value;
  text = isIntRange ? (`${value.start},${value.end}`) : text;
  return `${compare === 'in-range' ? '' : '!'}[${text}]`;
};

export const validateFiled = (data = []) => {
  const keys = ['desc', 'from', 'id', 'name', 'tips', 'type'];
  const requiredKeys = ['from', 'id', 'name', 'type'];
  let message = '';
  const ids = data.map(field => field.id);

  data.every((field) => {
    // 不存在类型
    if (!['string', 'int', 'select'].includes(field.type)) {
      message = `【${field.name}】列注释配置中type类型不存在`;
      return false;
    }
    if (!['inputs', 'outputs'].includes(field.from)) {
      message = `【${field.name}】列注释配置中from类型不存在`;
      return false;
    }

    // 下拉框类型
    if (field.type === 'select') {
      keys.push('options');
    }

    // 缺少字段
    const missingKeys = keys.filter(key => !(key in field));
    if (missingKeys.length) {
      message = `【${field.name}】列注释配置中缺少${missingKeys.join(',')}字段`;
      return false;
    }

    // id校验
    const idPattern = /^[a-zA-Z][a-zA-Z0-9]*$/.test(field.id);
    if (!idPattern) {
      message = `【${field.name}】列注释配置中key值只能由数字和字母组成且不能以数字开头`;
      return false;
    }
    const idCount = ids.filter(id => id === field.id).length;
    if (idCount > 1) {
      message = `【${field.name}】列注释配置中字段标识已经存在`;
      return false;
    }

    // 必填字段没值
    const emptyRequiredKeys = requiredKeys.filter(key => !field[key]);
    if (emptyRequiredKeys.length) {
      message = `【${field.name}】列注释配置中缺少${emptyRequiredKeys.join(',')}字段为必填项`;
      return false;
    }

    // 下拉框类型
    if (field.type === 'select') {
      // 校验下拉框类型格式
      const { options = {} } = field;
      let isOptionsValid = Object.prototype.toString.call(options) === '[object Object]';
      isOptionsValid = isOptionsValid && (Array.isArray(options.items) && options.type === 'custom');
      isOptionsValid = isOptionsValid && options.items.every(item => (item.id && item.name));
      if (!isOptionsValid) {
        message = `【${field.name}】列注释配置中options结构不对`;
        return false;
      }
    }

    return true;
  });

  return message;
};

export const parseValue = (data = '') => {
  // 解析出表格实际值，类型
  let value = String(data).trim();
  let type = 'equals';

  Object.keys(operateMap).forEach((key) => {
    const text = operateMap[key];
    if (text) {
      const regex = new RegExp(`^${text}`);
      if (regex.test(value)) {
        [, value] = value.split(text);
        type = key;
      }
      return;
    }
    // 数字
    value = intRegex.test(value) ? Number(value) : value;
    // 范围条件
    if (value && /^(!)?\[.*\]$/.test(value)) {
      const [v1, v2] = value.match(/^(!)?\[.*\]$/);
      value = v1.slice(v2 ? 2 : 1, -1).split(',')
        .map(item => intRegex.test(item) ? Number(item) : item.trim());
      type = `${v2 ? 'not-' : ''}in-range`;
    }
  });

  return { value, type };
};

export const validateValue = (value, config) => {
  let message = '';

  // 判断数据类型是否合规
  if (config.type === 'int') {
    const isMatch = Array.isArray(value) ? value.every(item => intRegex.test(item)) : intRegex.test(value);
    if (!isMatch) {
      message = `【${config.name}】列存在非数字类型`;
    }
  } else if (config.type === 'select' && value) {
    const ids = Array.isArray(value) ? value : [value];
    const isMatch = ids.every(id => config.options.items.some(item => item.id === id));
    if (!isMatch) {
      message = `【${config.name}】列存在所填选项不存在`;
    }
  }

  return message;
};

export const getValueRight = (value, type, config) => {
  let objType = config.type === 'select' ? 'select[Range]' : 'int[Range]';
  objType = type !== 'in-range' ? type : objType;
  const objValue = type === 'in-range' && config.type === 'int' ? { start: value[0], end: value[1] } : value;
  const obj = {
    type: objType,
    value: objValue,
  };
  return {
    obj,
    type: 'value',
  };
};
