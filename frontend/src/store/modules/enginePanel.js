/**
 * @file enginePanel store
 */
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    saveActionData({}, data) {
      const { method, params } = data;
      return axios[method]('task_system_superuser/trigger_engine_admin_action/', params).then(response => response);
    },
  },
};

