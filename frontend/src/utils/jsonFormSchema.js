import tools from './tools';

function getDataType(type) {
  if (type === 'bool') return 'boolean';
  if (type === 'int') return 'number';
  if (type === 'list') return 'array';
  return 'string';
}

function createBaseProperty(cur, type, formType, config) {
  const { name, desc, options } = cur;

  const dataType = getDataType(type);
  const compType = getCompType(type, formType, options);

  return {
    title: name,
    type: dataType,
    sourceType: type,
    formType,
    description: desc || '',
    extend: {
      can_hook: 'can_hook' in config ? config.can_hook : true,
      hook: false,
    },
    'ui:component': {
      name: compType,
      props: {},
    },
  };
}

function createValidationRules(type) {
  let validRules = type === 'bool' ? '{{ typeof $self.value === "boolean" }}' : '{{ $self.value?.length > 0 }}';
  validRules = type === 'int' ? '{{ $self.value >= 0 }}' : validRules;
  return [{
    validator: validRules,
    message: '值不能为空',
  }];
}

function getDefaultVal(defaultVal, type) {
  if (type === 'json' && !tools.checkIsJSON(defaultVal)) {
    return JSON.stringify(defaultVal, null, 4);
  }
  return defaultVal;
}

function getCompType(type, formType, options) {
  let compType = 'bfInput';
  // 支持表单类型
  if (formType) {
    compType = ['input', 'textarea'].includes(formType) ? compType : formType;
  } else if (type === 'list') {
    compType = formType === 'time_range' ? 'datetimerange' : 'checkbox';
    compType = formType === 'table' ? 'table' : compType;
  } else {
    compType = ['int', 'string'].includes(type) && options?.length ? 'select' : compType;
    compType = type === 'bool' ? 'switcher' : compType;
  }
  return compType;
}

function setComponentProps(acc, cur, key, config) {
  const { multiple, hint, allow_create: allowCreate, options, type, form_type: formType } = cur;
  const { name: compType } = acc[key]['ui:component'];

  if (compType === 'select') {
    const dataSource = options.map((item) => {
      const result = {
        label: item.text || item,
        value: item.value || item,
      };
      return result;
    }) || [];
    acc[key].type = multiple ? 'array' :  acc[key].type;
    acc[key]['ui:component'].props = {
      ...config,
      datasource: dataSource,
      multiple,
      allowCreate,
      searchable: true,
    };
  } else if (compType === 'checkbox') {
    acc[key]['ui:props'] = {
      ...config,
    };
    const dataSource = options.map(item => ({
      label: item.text || item,
      value: item.value || item,
    })) || [];
    acc[key]['ui:component'].props = { datasource: dataSource };
  } else if (['int', 'string', 'textarea'].includes(type)) {
    // 区分文本框和数字框
    let inputType = type === 'int' ? 'number' : 'text';
    inputType = formType === 'textarea' ? 'textarea' : inputType;
    acc[key]['ui:component'].props = {
      ...config,
      placeholder: hint,
      type: inputType,
    };
  } else if (type === 'json') {
    acc[key]['ui:component'].props = {
      ...config,
      placeholder: hint || '请输入JSON格式数据{ "xxx": "xxx" }',
      type: 'textarea',
      extCls: 'json-textarea',
    };
  } else if (formType === 'time_range') {
    acc[key]['ui:component'].name = 'bk-date-picker';
    acc[key]['ui:component'].props = {
      ...config,
      type: 'datetimerange',
      placeholder: hint || '请选择时间范围',
      transfer: true,
      multiple: false,
    };
  }
}

function setTableProps(acc, cur, key, config) {
  const properties = getProperties(cur.table.fields, {
    ...cur.table.meta,
    ...config,
  });
  const tableColumnProps = { showOverflowTooltip: { interactive: true } };
  Object.values(properties).forEach((item) => {
    if (item['ui:props']) {
      item['ui:props'].tableColumnProps = tableColumnProps;
    } else {
      item['ui:props'] = { tableColumnProps };
    }
    /* 特殊处理！！！
    * 表格下单元格如果为下拉框，则popover宽度默认为auto
    * 设置为字符串类型宽度是为了避免select组件使用默认宽度
    */
    if (item['ui:component'].name === 'select') {
      item['ui:component'].props['popover-width'] = 'max-content';
    }
  });
  acc[key].items = {
    type: 'object',
    properties,
  };
  acc[key]['ui:props'] = {
    ...config,
  };
}

function getProperties(data = [], config = {}) {
  return data.reduce((acc, cur) => {
    const { key, type, required, form_type: formType, meta_desc: metaDesc } = cur;

    acc[key] = createBaseProperty(cur, type, formType, config);

    if (metaDesc) acc[key].metaDesc = metaDesc;
    if (required) acc[key]['ui:rules'] = createValidationRules(type);
    if (cur.default) acc[key].default = getDefaultVal(cur.default, type);

    if (formType === 'table') {
      setTableProps(acc, cur, key, config);
    } else {
      setComponentProps(acc, cur, key, config);
    }
    return acc;
  }, {});
}

export default function jsonFormSchema(data, config = {}) {
  const { id, desc, inputs } = data;
  if (!Array.isArray(inputs)) return {};
  const keys = inputs.reduce((acc, cur) => {
    if (cur.required) {
      acc.push(cur.key);
    }
    return acc;
  }, []);
  const schema = {
    title: id,
    description: desc,
    type: 'object',
    required: keys,
    properties: getProperties(inputs, config),
  };
  return schema;
}
