import tools from './tools';

function getProperties(data = [], config = {}) {
  return data.reduce((acc, cur) => {
    const { key, name, desc, type, required, form_type: formType, options, meta_desc: metaDesc } = cur;

    let dataType = type === 'bool' ? 'boolean' : 'string';
    dataType = type === 'int' ? 'number' : dataType;
    acc[key] = {
      title: name,
      type: dataType,
      sourceType: type,
      formType,
      description: desc || '',
      extend: {
        can_hook: 'can_hook' in config ? config.can_hook : true,
        hook: false,
      },
    };

    if (metaDesc) {
      acc[key].metaDesc = metaDesc;
    }

    if (required) {
      let validRules = type === 'bool' ? '{{ typeof $self.value === "boolean" }}' : '{{ $self.value?.length > 0 }}';
      validRules = type === 'int' ? '{{ $self.value >= 0 }}' : validRules;
      acc[key]['ui:rules'] = [{
        validator: validRules,
        message: '值不能为空',
      }];
    }

    if (cur.default) {
      let defaultVal = cur.default;
      if (type === 'json' && !tools.checkIsJSON(defaultVal)) {
        defaultVal = JSON.stringify(cur.default, null, 4);
      }
      acc[key].default = defaultVal;
    }

    if (type === 'list') {
      acc[key].type = 'array';
      if (formType === 'table') {
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
      } else if (formType !== 'time_range') {
        // checkbox为数组类型
        acc[key].items = {
          type: 'string',
          enum: options.map(item => item.value || item) || [],
        };
        acc[key].uniqueItems = true;
        acc[key]['ui:props'] = {
          ...config,
        };
        return acc;
      }
    }

    let compType = 'bfInput';
    // 支持表单类型
    if (formType) {
      if (!['input', 'textarea'].includes(formType)) {
        compType = formType;
      }
    } else {
      compType = ['int', 'string'].includes(type) && options?.length ? 'select' : compType;
      compType = type === 'bool' ? 'switcher' : compType;
    }
    acc[key]['ui:component'] = {
      name: compType,
      props: {
        ...config,
      },
    };
    if (options && options.length) {
      const dataSource = options.map((item) => {
        const result = {
          label: item.text || item,
          value: item.value || item,
        };
        return result;
      }) || [];
      acc[key]['ui:component'].props.datasource = dataSource;
    } else if (['int', 'string', 'textarea'].includes(type)) {
      // 区分文本框和数字框
      let inputType = type === 'int' ? 'number' : 'text';
      inputType = formType === 'textarea' ? 'textarea' : inputType;
      acc[key]['ui:component'].props.type = inputType;
    } else if (type === 'json') {
      acc[key]['ui:component'].props = {
        ...config,
        placeholder: '请输入JSON格式数据{ "xxx": "xxx" }',
        type: 'textarea',
        extCls: 'json-textarea',
      };
    } else if (formType && formType === 'time_range') {
      acc[key]['ui:component'].name = 'bk-date-picker';
      acc[key]['ui:component'].props = {
        ...config,
        type: 'datetimerange',
        placeholder: '请选择时间范围',
        transfer: true,
        multiple: false,
      };
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
