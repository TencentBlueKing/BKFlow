
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    // 检查空间配置
    checkSpaceConfig({}, data) {
      return axios.get(`/api/space/config/${data.id}/check_space_config/`, { params: data }).then(response => response.data);
    },
    // 无鉴权获取空间基本配置信息
    getNotAuthSpaceConfig({}) {
      return axios.get('/api/space/config/get_control_config/').then(response => response.data);
    },
    getSpaceConfigData({}, data) {
      return axios.get('api/space/admin/space_config/get_all_space_configs/', {
        params: {
          space_id: data.space_id,
        },
      }).then(response => response.data);
    },
    updateSpaceConfig({}, data) {
      let url = 'api/space/admin/space_config/';
      let method = 'post';
      if (data.id) {
        url = `${url}${data.id}/`;
        method = 'patch';
      }

      return axios[method](url, data).then(response => response.data);
    },
    deleteSpaceConfig({}, data) {
      return axios.delete(`api/space/admin/space_config/${data.id}/`).then(response => response.data);
    },
    getSpaceConfigMeta({}, data) {
      return axios.get('api/space/admin/space_config/config_meta/', {
        params: {
          space_id: data.space_id,
        },
      }).then(response => response.data);
    },
  },
};

