import i18n from '@/config/i18n/index.js';

export const SPACE_LIST = [
  {
    name: i18n.t('流程'),
    icon: 'common-icon-flow-menu',
    id: 'template',
    disabled: false,
    subRoutes: ['templatePanel', 'templateMock'],
  },
  {
    name: i18n.t('任务'),
    icon: 'common-icon-task-menu',
    id: 'task',
    disabled: false,
    subRoutes: ['taskExecute', 'EnginePanel'],
  },
  {
    name: i18n.t('调试任务'),
    icon: 'common-icon-mock-menu',
    id: 'mockTask',
    disabled: false,
  },
  {
    name: i18n.t('决策表'),
    icon: 'common-icon-decision-menu',
    id: 'decisionTable',
    disabled: false,
    subRoutes: ['decisionEdit'],
  },
  {
    name: i18n.t('空间配置'),
    icon: 'common-icon-bkflow-setting',
    id: 'config',
    disabled: false,
  },
  {
    name: i18n.t('凭证管理'),
    icon: 'common-icon-credential',
    id: 'credential',
    disabled: false,
  },
];

export const MODULES_LIST = [
  {
    name: i18n.t('空间配置'),
    icon: 'common-icon-space',
    id: 'space',
    disabled: false,
  },
  {
    name: i18n.t('模块配置'),
    icon: 'common-icon-module',
    id: 'module',
    disabled: false,
  },
];

export const PLUGIN_LIST = [
  {
    name: i18n.t('蓝鲸插件'),
    icon: 'common-icon-space',
    id: 'plugin',
    disabled: false,
  },
];

export const ROUTE_LIST_MAP = {
  spaceAdmin: SPACE_LIST,
  systemAdmin: MODULES_LIST,
  pluginAdmin: PLUGIN_LIST,
};

export const routeNameMap = {
  spaceAdmin: 'space-manager',
  systemAdmin: 'system-manager',
  pluginAdmin: 'plugin-manager',
};
