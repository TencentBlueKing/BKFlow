/**
 * @file router 配置
 */

import Vue from 'vue';
import VueRouter from 'vue-router';

const NotFound = () => import('@/components/common/modal/ErrorCode404.vue');
const Home = () => import('@/components/common/modal/home.vue');
const EnginePanel = () => import('@/views/enginePanel/index.vue');
const Template = () => import('@/views/template/index.vue');
const TemplatePanel = () => import('@/views/template/TemplateEdit/index.vue');
const TemplateMock = () => import('@/views/template/TemplateMock/index.vue');

const Task = () => import('@/views/task/index.vue');
const TaskExecute = () => import('@/views/task/TaskExecute/index.vue');

const EngineAdmin = () => import('@/views/admin/index.vue');
const SpaceAdmin = () => import('@/views/admin/Space/index.vue');
const SyStemAdmin = () => import('@/views/admin/System/index.vue');
const PluginAdmin = () => import('@/views/admin/Plugin/index.vue');
const DecisionEdit = () => import('@/views/admin/Space/DecisionTable/components/DecisionEdit.vue');

Vue.use(VueRouter);

const routes = [
  {
    path: '/',
    name: 'home',
    component: Home,
  },
  {
    path: '/enginePanel/:spaceId/',
    name: 'EnginePanel',
    component: EnginePanel,
    pathToRegexpOptions: { strict: true },
    props: route => ({
      spaceId: route.params.spaceId,
    }),
  },

  {
    path: '/template',
    component: Template,
    children: [
      {
        path: '',
        component: NotFound,
      },
      {
        path: ':type(edit|clone|view)/:templateId/',
        component: TemplatePanel,
        name: 'templatePanel',
        pathToRegexpOptions: { strict: true },
        props: route => ({
          templateId: route.params.templateId,
          type: route.params.type,
        }),
        meta: { project: true },
      },
      {
        path: 'mock/:step?/:isEnableVersionManage?/:templateId/',
        component: TemplateMock,
        name: 'templateMock',
        pathToRegexpOptions: { strict: true },
        props: route => ({
          templateId: route.params.templateId,
          step: route.params.step,
          version: route.params?.version,
          isEnableVersionManage: route.params.isEnableVersionManage === 'true' || route.params.isEnableVersionManage === true,
        }),
        meta: { project: true },
      },
    ],
  },

  {
    path: '/taskflow',
    component: Task,
    children: [
      {
        path: '',
        component: NotFound,
      },
      {
        path: 'execute/:spaceId/',
        component: TaskExecute,
        name: 'taskExecute',
        pathToRegexpOptions: { strict: true },
        props: route => ({
          spaceId: route.params.spaceId,
          instanceId: route.query.instanceId,
        }),
        meta: { project: true },
      }],
  },
  {
    path: '/bkflow_engine_admin/',
    name: 'engineAdmin',
    pathToRegexpOptions: { strict: true },
    component: EngineAdmin,
    children: [
      {
        path: '',
        name: 'spaceAdmin',
        component: SpaceAdmin,
        pathToRegexpOptions: { strict: true },
        meta: { admin: true },
      },
      {
        path: 'system/',
        name: 'systemAdmin',
        component: SyStemAdmin,
        pathToRegexpOptions: { strict: true },
        meta: { admin: true },
      },
      {
        path: 'plugin/',
        name: 'pluginAdmin',
        component: PluginAdmin,
        pathToRegexpOptions: { strict: true },
        meta: { admin: true },
      },
    ],
  },
  {
    path: '/:path(decision|admin_decision)/:decisionId?/',
    component: DecisionEdit,
    name: 'decisionEdit',
    pathToRegexpOptions: { strict: true },
    props: route => ({
      path: route.params.path,
      decisionId: route.params.decisionId,
      spaceId: route.query.space_id,
      templateId: route.query.template_id,
    }),
  },
  // home
  {
    path: '*',
    name: 'home',
    component: Home,
  },
];

const router = new VueRouter({
  base: window.SITE_URL,
  mode: 'history',
  routes,
});

export default router;
