/**
 * @file main store
 */

import Vue from 'vue';
import Vuex from 'vuex';
import axios from 'axios';
import i18n from '@/config/i18n/index.js';
import { getPlatformConfig, setShortcutIcon } from '@blueking/platform-config';

import enginePanel from './modules/enginePanel';
import task from './modules/task';
import template from './modules/template';
import project from './modules/project';
import atomForm from './modules/atomForm';
import templateList from './modules/templateList';
import taskList from './modules/taskList';
import spaceConfig from './modules/spaceConfig';
import system from './modules/system';
import decisionTable from './modules/decisionTable';
import credentialConfig from './modules/credentialConfig';

Vue.use(Vuex);

const getAppLang = () => {
  const result = window.getCookie('blueking_language') === 'en' ? 'en' : 'zh-cn';
  return result;
};

const store = new Vuex.Store({
  // 模块
  modules: {
    enginePanel,
    task,
    template,
    project,
    atomForm,
    templateList,
    taskList,
    spaceConfig,
    system,
    decisionTable,
    credentialConfig,
  },
  // 公共 store
  state: {
    username: window.USERNAME,
    footer: '',
    hasStatisticsPerm: null, // 是否有运营数据查看权限
    hideHeader: window.HIDE_HEADER === 1,
    site_url: window.SITE_URL,
    app_id: window.APP_ID, // 轻应用 id
    view_mode: window.VIEW_MODE,
    lang: getAppLang(),
    notFoundPage: false,
    categorys: [],
    components: [],
    isSuperUser: window.IS_SUPERUSER === 1,
    v1_import_flag: window.IMPORT_V1_FLAG,
    rsa_pub_key: window.RSA_PUB_KEY,
    permissionMeta: {
      system: [],
      resources: [],
      actions: [],
    },
    infoBasicConfig: {
      title: i18n.t('确认离开当前页?'),
      subTitle: i18n.t('离开将会导致未保存信息丢失'),
      okText: i18n.t('离开'),
      cancelText: i18n.t('取消'),
      maskClose: false,
      closeFn: () => true,
    },
    token: '',
    spaceId: '',
    spaceList: [],
    isAdmin: false,
    isSpaceSuperuser: false, // 是否为某个空间下的管理员
    isCurSpaceSuperuser: false, // 是否为当前空间管理员
    hasAlertNotice: false,
    platformInfo: { // 项目全局配置
      bkAppCode: window.APP_CODE,
      name: window.APP_NAME || 'BKFlow',
      brandName: window.RUN_VER_NAME || i18n.t('蓝鲸智云'),
      favicon: `${window.SITE_URL}static/core/images/bkflow.png`,
      i18n: {},
    },
    isIframe: false,
  },
  // 公共 getters
  getters: {

  },
  // 公共 mutations
  mutations: {
    setToken(state, token) {
      state.token = token;
    },
    setSpaceId(state, id) {
      state.spaceId = id;
    },
    setSpaceList(state, val) {
      state.spaceList = val;
    },
    setAdmin(state, val) {
      state.isAdmin = val;
    },
    setAppId(state, id) {
      state.app_id = id;
    },
    setPageFooter(state, content) {
      state.footer = content;
    },
    setStatisticsPerm(state, perm) {
      state.hasStatisticsPerm = perm;
    },
    setViewMode(state, mode) {
      state.view_mode = mode;
    },
    setNotFoundPage(state, val) {
      state.notFoundPage = val;
    },
    setCategorys(state, data) {
      state.categorys = data;
    },
    setSingleAtomList(state, data) {
      state.components = data;
    },
    setPermissionMeta(state, data) {
      state.permissionMeta = data;
    },
    setSpaceSuperuser(state, val) {
      state.isSpaceSuperuser = val;
    },
    setCurSpaceSuperuser(state, val) {
      state.isCurSpaceSuperuser = val;
    },
    setAlertNotice(state, val) {
      state.hasAlertNotice = val;
    },
    setPlatformInfo(state, content) {
      state.platformInfo = content;
    },
    setIframe(state, val) {
      state.isIframe = val;
    },
  },
  actions: {
    // 更新token
    updateToken({ state }) {
      if (!state.token) return;
      return axios.post(`api/permission/token/${state.token}/renewal/`).then(response => response.data);
    },
    // 获取空间管理页权限
    getSpacePermission() {
      return axios.get('is_admin_user/').then(response => response.data);
    },
    // 获取当前空间管理页权限
    getCurrentSpacePermission({}, params) {
      return axios.get('is_current_space_admin/', { params }).then(response => response.data);
    },
    // 获取空间列表
    loadSpaceList({}, data) {
      return axios.get('api/space/', {
        params: { ...data },
      }).then(response => response.data);
    },
    // 获取空间详情
    getSpaceDetail({}, data) {
      return axios.get(`api/space/${data.id}/`).then(response => response.data);
    },
    // 获取页面动态 footer 内容
    getFooterContent() {
      return axios.get('core/footer/').then(response => response.data);
    },
    // 查询用户是否查看最新的版本日志
    queryNewVersion() {
      return axios.get('version_log/has_user_read_latest/').then(response => response.data);
    },
    // 获取项目版本更新日志列表
    getVersionList() {
      return axios.get('version_log/version_logs_list/').then(response => response.data);
    },
    // 版本日志详情
    getVersionDetail({}, data) {
      return axios.get('version_log/markdown_version_log_detail/', {
        params: {
          log_version: data.version,
        },
      }).then(response => response.data);
    },
    getCategorys({ commit }) {
      axios.get('analysis/get_task_category/').then((response) => {
        commit('setCategorys', response.data.data);
      });
    },
    getNotifyTypes() {
      return axios.get('get_msg_types/').then(response => response.data);
    },
    getNotifyGroup(params) {
      return axios.get('api/v3/staff_group/', { params }).then(response => response.data);
    },
    // 获取收藏列表
    loadCollectList() {
      return axios.get('api/v3/collection/').then(response => response.data);
    },
    // 收藏模板，批量操作
    addToCollectList(list) {
      return axios.post('api/v3/collection/', list).then(response => response.data);
    },
    // 删除收藏模板，单个删除
    deleteCollect(id) {
      return axios.delete(`api/v3/collection/${id}/`).then(response => response.data);
    },
    // ip 选择器接口 start --->
    // 查询业务在 CMDB 的主机
    getHostInCC(data) {
      const { url, fields, topo, search_host_lock } = data;
      return axios.get(url, {
        params: {
          fields: JSON.stringify(fields),
          topo: JSON.stringify(topo),
          search_host_lock,
        },
        baseURL: '/',
      }).then(response => response.data);
    },
    // 查询业务在 CMDB 的拓扑树
    getTopoTreeInCC(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    // 查询业务在 CMDB 的拓扑模型
    getTopoModelInCC(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    // 查询业务在 CMDB 的动态分组
    getDynamicGroup(data) {
      return axios.get(data.url, { baseURL: '/', start: data.start, limit: 200 }).then(response => response.data);
    },
    // <--- ip 选择器接口 end
    // 开区资源选择器接口 start --->
    getResourceConfig(data) {
      return axios.get(data.url).then(response => response.data);
    },
    saveResourceScheme(params) {
      const { url, data } = params;
      return axios.patch(url, data).then(response => response.data);
    },
    createResourceScheme(params) {
      const { url, data } = params;
      return axios.post(url, data).then(response => response.data);
    },
    getCCSearchTopoSet(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    getCCSearchTopoResource(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    getCCSearchModule(data) {
      return axios.get(data.url, {
        params: {
          bk_set_id: data.bk_set_id,
        },
        baseURL: '/',
      }).then(response => response.data);
    },
    getCCSearchObjAttrHost(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    getCCSearchColAttrSet(data) {
      return axios.get(data.url, { baseURL: '/' }).then(response => response.data);
    },
    getCCHostCount(data) {
      return axios.get(data.url, { baseURL: '/', params: { bk_inst_id: data.ids } }).then(response => response.data);
    },
    // <--- 开区资源选择器接口 end
    /**
   * 获取权限相关元数据
   */
    getPermissionMeta({ commit }) {
      return axios.get('iam/api/meta/').then((response) => {
        commit('setPermissionMeta', response.data.data);
        return response.data;
      });
    },
    /**
   * 查询用户是否有某项权限
   */
    queryUserPermission(data) {
      return axios.post('iam/api/is_allow/', data).then(response => response.data);
    },
    /**
   * 查询用户是否有公共流程管理页面权限
   */
    queryUserCommonPermission() {
      return axios.get('iam/api/is_allow/common_flow_management/').then(response => response.data);
    },
    /**
   * 获取权限中心跳转链接
   */
    getIamUrl(data) {
      return axios.post('iam/api/apply_perms_url/', data).then(response => response.data);
    },
    /**
   * 项目收藏、取消项目收藏
   */
    projectFavorite(data) {
      return axios.post(`api/v3/user_project/${data.id}/favor/`).then(response => response.data);
    },
    projectuCancelFavorite(data) {
      return axios.delete(`api/v3/user_project/${data.id}/cancel_favor/`).then(response => response.data);
    },
    /**
     * 获取当前用户的全局设置
     * @returns {Object}
     */
    async getGlobalConfig({ state, commit }) {
      // 默认配置
      const config = { ...state.platformInfo };
      let resp;
      const bkRepoUrl = window.BK_PAAS_SHARED_RES_URL;
      if (bkRepoUrl) {
        resp = await getPlatformConfig(`${bkRepoUrl}/bk_flow/base.js`, config);
      } else {
        resp = await getPlatformConfig(config);
      }
      const { name, brandName, i18n } = config;
      document.title = `${i18n.name || name} | ${i18n.brandName || brandName}`;
      setShortcutIcon(resp.favicon);
      commit('setPlatformInfo', resp);
      return resp;
    },
    // 退出登录
    logout() {
      return axios.get('logout').then(response => response.data);
    },
  },
});

export default store;
