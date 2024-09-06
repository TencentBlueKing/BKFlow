
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
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

