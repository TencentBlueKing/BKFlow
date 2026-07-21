const getComponentDataValue = (data, key) => {
  const item = data[key];
  if (item && typeof item === 'object' && Object.prototype.hasOwnProperty.call(item, 'value')) {
    return item.value;
  }
  return item;
};

export const resolveUniformApiPluginVersion = (component = {}) => {
  const data = component.data || {};
  const apiMeta = component.api_meta || {};
  return getComponentDataValue(data, 'uniform_api_plugin_version')
    || getComponentDataValue(data, 'plugin_version')
    || apiMeta.plugin_version
    || component.version
    || '';
};

export const buildUniformApiMetaParams = ({
  meta_url: metaUrl,
  meta_url_template: metaUrlTemplate,
  version,
  scope_type: scopeType,
  scope_value: scopeValue,
}) => {
  const params = {
    meta_url: metaUrl,
    scope_type: scopeType,
    scope_value: scopeValue,
  };
  if (metaUrlTemplate) {
    params.meta_url_template = metaUrlTemplate;
    if (version !== undefined && version !== null && version !== '') {
      params.version = String(version);
    }
  }
  return params;
};
