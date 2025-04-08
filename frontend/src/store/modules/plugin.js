/**
 * @file credentialConfig store
 */
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    loadPluginManagerList({}, params) {
      return axios.get('api/bk_plugin/manager/', { params }).then(response => response.data);
    },
    updatePluginManager({}, params) {
      return axios.patch(`api/bk_plugin/manager/${params.code}/`, params).then(response => response.data);
    },
    loadBkPluginList({}, params) {
      return axios.get('api/bk_plugin/', { params }).then(response => response.data.data);
    },
  },
};
