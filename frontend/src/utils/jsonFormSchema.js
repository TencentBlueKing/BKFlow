import tools from './tools';

function getDataType(type) {
  if (type === 'bool') return 'boolean';
  if (type === 'int') return 'number';
  if (type === 'list') return 'array';
  return 'string';
}

function getSourceType(type) {
  if (['boolean', 'bool'].includes(type)) return 'bool';
  if (['integer', 'number', 'int', 'float'].includes(type)) return 'int';
  if (['array', 'list'].includes(type)) return 'list';
  if (['object', 'json'].includes(type)) return 'json';
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
  const safeOptions = Array.isArray(options) ? options : [];

  if (compType === 'select') {
    const dataSource = safeOptions.map((item) => {
      const result = {
        label: item.text || item,
        value: item && Object.prototype.hasOwnProperty.call(item, 'value') ? item.value : item,
      };
      return result;
    });
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
    const dataSource = safeOptions.map(item => ({
      label: item.text || item,
      value: item && Object.prototype.hasOwnProperty.call(item, 'value') ? item.value : item,
    }));
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
    if (Object.prototype.hasOwnProperty.call(cur, 'default')) {
      acc[key].default = getDefaultVal(cur.default, type);
    }

    if (formType === 'table') {
      setTableProps(acc, cur, key, config);
    } else {
      setComponentProps(acc, cur, key, config);
    }
    return acc;
  }, {});
}

function schemaPropertyToInput(key, property, required) {
  const type = getSourceType(property.type);
  const input = {
    key,
    name: property.title || key,
    desc: property.description || '',
    type,
    required,
  };
  if (Object.prototype.hasOwnProperty.call(property, 'default')) {
    input.default = property.default;
  }

  const itemSchema = property.items || {};
  const options = property.enum || itemSchema.enum;
  if (Array.isArray(options)) input.options = options;
  if (type === 'list' && itemSchema.type === 'object') {
    const itemRequired = new Set(itemSchema.required || []);
    input.form_type = 'table';
    input.table = {
      fields: Object.entries(itemSchema.properties || {}).map(([itemKey, item]) => (
        schemaPropertyToInput(itemKey, item, itemRequired.has(itemKey))
      )),
      meta: {},
    };
  }
  return input;
}

function mergeStructuredProperty(fallback, property, config) {
  const merged = {
    ...fallback,
    ...property,
    sourceType: property.sourceType || fallback.sourceType,
    formType: property.formType || fallback.formType,
    extend: {
      ...fallback.extend,
      ...(property.extend || {}),
    },
  };
  const customComponent = property['ui:component'];
  if (customComponent) {
    merged['ui:component'] = {
      ...fallback['ui:component'],
      ...customComponent,
      props: {
        ...(fallback['ui:component'].props || {}),
        ...(customComponent.props || {}),
        ...config,
      },
    };
  }
  return merged;
}

function normalizeStructuredProperties(properties = {}, required = [], config = {}) {
  const requiredFields = new Set(required);
  return Object.entries(properties).reduce((acc, [key, rawProperty]) => {
    const property = { ...rawProperty };
    if (property.items?.type === 'object') {
      property.items = {
        ...property.items,
        properties: normalizeStructuredProperties(
          property.items.properties,
          property.items.required,
          config,
        ),
      };
    }
    if (property.type === 'object' && property.properties) {
      property.properties = normalizeStructuredProperties(property.properties, property.required, config);
    }

    const input = schemaPropertyToInput(key, property, requiredFields.has(key));
    const fallback = getProperties([input], config)[key];
    acc[key] = mergeStructuredProperty(fallback, property, config);
    return acc;
  }, {});
}

function normalizeStructuredFormSchema(data, config) {
  const formSchema = data.form_schema;
  const schema = {
    ...formSchema,
    title: formSchema.title || data.id,
    description: formSchema.description || data.desc || '',
    type: 'object',
  };
  schema.properties = normalizeStructuredProperties(
    formSchema.properties,
    formSchema.required,
    config,
  );
  return schema;
}

export default function jsonFormSchema(data, config = {}) {
  if (data.form_schema?.properties) {
    return normalizeStructuredFormSchema(data, config);
  }
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
