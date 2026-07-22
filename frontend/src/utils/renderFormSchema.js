import tools from './tools';

const TYPE_MAP = {
  array: 'checkbox',
  bool: 'switch',
  boolean: 'switch',
  int: 'int',
  integer: 'int',
  json: 'textarea',
  list: 'checkbox',
  number: 'int',
  object: 'textarea',
  radio: 'radio',
  select: 'select',
  string: 'input',
  table: 'datatable',
  textarea: 'textarea',
};

const COMPONENT_TYPE_MAP = {
  checkbox: 'checkbox',
  codeEditor: 'code_editor',
  code_editor: 'code_editor',
  'code-editor': 'code_editor',
  password: 'password',
  radio: 'radio',
  select: 'select',
  switcher: 'switch',
  table: 'datatable',
  textarea: 'textarea',
};

const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

function getOptionLabel(item) {
  if (!item || typeof item !== 'object') return String(item);
  if (hasOwn(item, 'label')) return item.label;
  if (hasOwn(item, 'text')) return item.text;
  if (hasOwn(item, 'name')) return item.name;
  if (hasOwn(item, 'value')) return String(item.value);
  return String(item);
}

function getOptionValue(item) {
  if (!item || typeof item !== 'object') return item;
  if (hasOwn(item, 'value')) return item.value;
  if (hasOwn(item, 'id')) return item.id;
  return item;
}

function normalizeOptions(options) {
  if (Array.isArray(options)) {
    return options.map(item => ({
      label: getOptionLabel(item),
      value: getOptionValue(item),
    }));
  }
  if (Array.isArray(options?.items)) {
    return options.items.map(item => ({
      label: getOptionLabel(item),
      value: getOptionValue(item),
    }));
  }
  return [];
}

function getStructuredOptions(property, componentProps) {
  if (Array.isArray(componentProps.datasource)) return componentProps.datasource;
  if (Array.isArray(property.enum)) return property.enum;
  if (Array.isArray(property.items?.enum)) return property.items.enum;
  return [];
}

function getFallbackInput(inputs, key) {
  return inputs.find(item => item && item.key === key) || {};
}

function structuredPropertiesToFields(formSchema, fallbackInputs = []) {
  const properties = formSchema?.properties;
  if (!properties || typeof properties !== 'object' || Array.isArray(properties)) return [];

  const required = new Set(formSchema.required || []);
  return Object.entries(properties).map(([key, propertyValue]) => {
    const property = propertyValue && typeof propertyValue === 'object' ? propertyValue : {};
    const fallback = getFallbackInput(fallbackInputs, key);
    const component = property['ui:component'] || {};
    const componentProps = component.props && typeof component.props === 'object' ? component.props : {};
    const itemSchema = property.items && typeof property.items === 'object' ? property.items : {};
    const field = {
      ...fallback,
      key,
      name: property.title || fallback.name || key,
      desc: property.description || fallback.desc || fallback.description || '',
      type: property.type || fallback.type || 'string',
      required: required.has(key) || !!fallback.required,
      options: getStructuredOptions(property, componentProps),
      uiComponent: component.name,
      uiComponentProps: componentProps,
    };

    if (hasOwn(property, 'default')) field.default = property.default;
    if (property.type === 'array' && itemSchema.type === 'object') {
      field.form_type = 'table';
      field.table = {
        fields: structuredPropertiesToFields(itemSchema, fallback.table?.fields || []),
        meta: fallback.table?.meta || {},
      };
    }
    return field;
  });
}

function resolveFields(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== 'object') return [];
  if (data.form_schema?.properties && typeof data.form_schema.properties === 'object') {
    const fields = structuredPropertiesToFields(data.form_schema, data.inputs || []);
    if (fields.length || Object.keys(data.form_schema.properties).length === 0) return fields;
  }
  return Array.isArray(data.inputs) ? data.inputs : [];
}

function resolveInputComponentType(componentProps) {
  if (componentProps.type === 'textarea') return 'textarea';
  if (componentProps.type === 'password') return 'password';
  if (componentProps.type === 'number') return 'int';
  return 'input';
}

function resolveRenderType(field) {
  const componentName = field.uiComponent;
  if (['input', 'bk-input', 'bfInput'].includes(componentName)) {
    return resolveInputComponentType(field.uiComponentProps || {});
  }
  if (COMPONENT_TYPE_MAP[componentName]) return COMPONENT_TYPE_MAP[componentName];

  const formType = field.form_type;
  if (['input', 'bk-input', 'bfInput'].includes(formType)) return 'input';
  if (COMPONENT_TYPE_MAP[formType]) return COMPONENT_TYPE_MAP[formType];
  if (TYPE_MAP[formType]) return TYPE_MAP[formType];
  if (field.key === 'time_range_field' || formType === 'time_range') return 'datetime_range';
  if (field.table || field.type === 'table') return 'datatable';

  const options = normalizeOptions(field.options);
  if (['string', 'int', 'integer', 'number'].includes(field.type) && options.length) return 'select';
  if (field.type === 'array' && field.table) return 'datatable';
  return TYPE_MAP[field.type] || 'input';
}

function buildValidation(field) {
  const validation = [];
  if (field.required) validation.push({ type: 'required' });
  if (['json', 'object'].includes(field.type)) {
    validation.push({
      type: 'custom',
      args(value) {
        return {
          result: tools.checkIsJSON(value),
          error_message: 'json数据格式不正确',
        };
      },
    });
  }
  return validation;
}

function getComponentAttrs(field, renderType) {
  const supportedComponent = ['input', 'bk-input', 'bfInput'].includes(field.uiComponent)
    || !!COMPONENT_TYPE_MAP[field.uiComponent];
  if (!supportedComponent) return {};

  const attrs = { ...(field.uiComponentProps || {}) };
  delete attrs.datasource;
  if (renderType === 'select') {
    if (hasOwn(attrs, 'allowCreate')) attrs.allowCreate = attrs.allowCreate;
    if (hasOwn(attrs, 'allow_create')) {
      attrs.allowCreate = attrs.allow_create;
      delete attrs.allow_create;
    }
  }
  return attrs;
}

function setOptions(schema, field) {
  const options = normalizeOptions(field.options);
  if (schema.type === 'select') {
    schema.attrs.items = options.map(item => ({ text: item.label, value: item.value }));
  } else if (['checkbox', 'radio'].includes(schema.type)) {
    schema.attrs.items = options.map(item => ({ name: item.label, value: item.value }));
  }
}

function buildRenderFormField(field, config) {
  const renderType = resolveRenderType(field);
  const schema = {
    type: renderType,
    tag_code: field.key,
    attrs: {
      name: field.name || field.key,
      desc: field.desc || field.description || '',
      ...getComponentAttrs(field, renderType),
      ...config,
    },
  };

  const validation = buildValidation(field);
  if (validation.length) schema.attrs.validation = validation;
  if (field.varKey) schema.attrs.varKey = field.varKey;
  if (hasOwn(field, 'default')) schema.attrs.default = field.default;

  if (['json', 'object'].includes(field.type)) {
    schema.attrs.jsonAttr = 'json-textarea';
    schema.attrs.placeholder = schema.attrs.placeholder || '请输入JSON格式数据{ "xxx": "xxx" }';
  }

  setOptions(schema, field);
  if (renderType === 'datatable') {
    schema.attrs.editable = hasOwn(schema.attrs, 'editable') ? schema.attrs.editable : true;
    schema.attrs.deleteable = hasOwn(schema.attrs, 'deleteable') ? schema.attrs.deleteable : true;
    schema.attrs.columns = renderFormSchema(field.table?.fields || [], {
      ...(field.table?.meta || {}),
      ...config,
    });
  }
  return schema;
}

export default function renderFormSchema(data = [], config = {}) {
  return resolveFields(data).map(field => buildRenderFormField(field, config));
}
