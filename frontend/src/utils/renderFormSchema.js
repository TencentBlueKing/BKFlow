import tools from './tools';

export default function renderFormSchema(data = [], config = {}) {
  return data.reduce((acc, cur) => {
    const { key, name, desc, type, required, form_type: formType, options, varKey } = cur;

    const typeMap = {
      string: 'input',
      int: 'int',
      json: 'textarea',
      textarea: 'textarea',
      list: 'checkbox',
      table: 'datatable',
      radio: 'radio',
      bool: 'switch',
      boolean: 'switch',
      select: 'select',
      integer: 'int',
    };

    let dataType = typeMap[type];
    dataType = type === 'string' && options ? 'select' : dataType;
    dataType = formType ? typeMap[formType] : dataType;
    dataType = key === 'time_range_field' ? 'datetime_range' : dataType;
    const schema = {
      type: dataType,
      tag_code: key,
      attrs: {
        name,
        description: desc || '',
      },
    };

    if (dataType === 'select') {
      if (Array.isArray(options)) {
        schema.attrs.items = options.map(item => ({
          text: item.text || item,
          value: item.value || item,
        }));
      } else {
        schema.attrs.items = options.items.map(item => ({
          text: item.name,
          value: item.id,
        }));
      }
    }
    if (required) {
      schema.attrs.validation = [{ type: 'required' }];
    }
    if (varKey) {
      schema.attrs.varKey = varKey;
    }
    if (type === 'json') {
      schema.attrs.jsonAttr = 'json-textarea';
      schema.attrs.placeholder = '请输入JSON格式数据{ "xxx": "xxx" }';
      schema.attrs.validation = [
        { type: 'required' },
        {
          type: 'custom',
          args(value) {
            return {
              result: tools.checkIsJSON(value),
              error_message: 'json数据格式不正确',
            };
          },
        },
      ];
    }

    if (cur.default !== undefined) {
      schema.attrs.default = cur.default;
    }

    if (type === 'list') {
      if (formType === 'table') {
        schema.attrs.editable = true;
        schema.attrs.deleteable = true;
        schema.attrs.columns = renderFormSchema(cur.table.fields, {
          ...cur.table.meta,
          ...config,
        });
      } else if (formType !== 'time_range') {
        // checkbox为数组类型
        schema.attrs.items = options.map(item => ({
          name: item,
          value: item,
        }));
      }
    }
    acc.push(schema);

    return acc;
  }, []);
}
