/**
 * @file user preference store
 * @desc 用户偏好设置相关的 store
 */

import axios from 'axios';

const user = {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    /**
     * 获取用户偏好设置
     */
    getUserPreference() {
      return axios.get('/api/space/user-preference/current/').then(response => response.data);
    },
    /**
     * 保存用户最后选择的空间
     * @param {Object} context - vuex context
     * @param {Object} params - 参数
     * @param {Number} params.space_id - 空间ID
     */
    saveUserPreference(context, params) {
      return axios.post('/api/space/user-preference/save/', params).then(response => response.data);
    },
  },
};

export default user;
