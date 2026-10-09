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
    /**
     * 获取用户收藏的空间列表
     */
    getUserFavorites() {
      return axios.get('/api/space/user-preference/favorites/').then(response => response.data);
    },
    /**
     * 切换空间收藏状态
     * @param {Object} context - vuex context
     * @param {Number} spaceId - 空间ID
     */
    toggleSpaceFavorite(context, spaceId) {
      return axios.post('/api/space/user-preference/toggle_favorite/', { space_id: spaceId }).then(response => response.data);
    },
  },
};

export default user;
