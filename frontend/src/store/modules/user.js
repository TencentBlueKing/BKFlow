import axios from 'axios';

export default {
  namespaced: true,

  state: {
    preference: null,
  },

  mutations: {
    SET_PREFERENCE(state, preference) {
      state.preference = preference;
    },
  },

  actions: {
    // 获取用户偏好设置
    async getUserPreference({ commit }) {
      try {
        const response = await axios.get('/api/space/user/get_preference/');
        const data = response.data;
        commit('SET_PREFERENCE', data);
        return data;
      } catch (error) {
        console.error('[Store/user] 获取用户偏好失败:', error);
        throw error;
      }
    },

    // 保存用户偏好设置
    async saveUserPreference({ commit }, spaceId) {
      try {
        const response = await axios.post('/api/space/user/save_preference/', { space_id: spaceId });
        const data = response.data;
        commit('SET_PREFERENCE', data);
        return data;
      } catch (error) {
        console.error('[Store/user] 保存用户偏好失败:', error);
        throw error;
      }
    },
  },
};
