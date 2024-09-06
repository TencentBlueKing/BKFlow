/**
 * @file enginePanel store
 */
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    getSystemModuleData({}, data = {}) {
      return axios.get('api/admin/module_info/', {
        params: { ...data },
      }).then(response => response.data);
    },
    updateSystemModule({}, data) {
      let url = 'api/admin/module_info/';
      let method = 'post';
      if (data.id) {
        url = `${url}${data.id}/`;
        method = 'patch';
      }

      return axios[method](url, data).then(response => response.data);
    },
    deleteSystemModule({}, data) {
      return axios.delete(`api/admin/module_info/${data.id}/`).then(response => response.data);
    },
    getSystemModuleMeta({}) {
      return axios.get('api/admin/module_info/get_meta/').then(response => response.data);
    },
    getSpaceMeta() {
      return axios.get('api/space/get_meta/').then(response => response.data);
    },
    updateSpaceConfig({}, data) {
      let url = 'api/space/';
      let method = 'post';
      if (data.id) {
        url = `${url}${data.id}/`;
        method = 'patch';
      }

      return axios[method](url, data).then(response => response.data);
    },
  },
};

