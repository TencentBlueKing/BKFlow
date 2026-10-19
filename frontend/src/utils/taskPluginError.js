export const formatTaskPluginMetaError = (response, context) => {
  const data = response.data || {};
  const {
    pluginCode,
    pluginName,
    pluginVersion,
    t,
  } = context;
  if (response.status === 403) {
    return {
      title: t('插件详情加载失败'),
      message: t('插件可能已下架或当前无访问权限，请联系管理员确认。'),
    };
  }
  if (response.status === 404 || data.error_code === 'PLUGIN_UNAVAILABLE') {
    return {
      title: t('插件已下架，节点参数无法加载'),
      message: t(
        '插件「{name}」的版本「{version}」已从当前环境下架。执行记录仍可查看；如需重新执行，请先在流程中替换该插件。',
        { name: pluginName || pluginCode, version: pluginVersion || '--' },
      ),
    };
  }
  if (data.error_code === 'PLUGIN_DETAIL_UNAVAILABLE') {
    return {
      title: t('插件详情加载失败'),
      message: t('插件可能已下架或当前无访问权限，请联系管理员确认。'),
    };
  }
  return undefined;
};
