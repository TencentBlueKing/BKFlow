
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    loadDecisionList({}, data) {
      const config = {};
      if (data.cancelToken) {
        config.cancelToken = data.cancelToken;
        delete data.cancelToken;
      }
      const url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/`;
      return axios.get(url, {
        params: data,
        ...config,
      }).then(response => response.data);
    },
    deleteDecision({}, data) {
      const url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/${data.id}/`;
      const params = data.isAdmin ? {} : data;
      return axios.delete(url, { params }).then(response => response.data);
    },
    getDecisionData({}, data) {
      const url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/${data.id}/`;
      return axios.get(url, {
        params: data,
      }).then(response => response.data);
    },
    updateDecision({}, data) {
      let url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/`;
      delete data.isAdmin;
      let method = 'post';
      if (data.id) {
        url = `${url}${data.id}/`;
        method = 'patch';
      }

      return axios[method](url, data).then(response => response.data);
    },
    debugDecision({}, data) {
      const url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/${data.id}/evaluate/`;
      return axios.post(url, data).then(response => response.data);
    },
    checkDecisionUsed({}, data) {
      const url = `api/decision_table/${data.isAdmin ? 'admin' : 'user'}/${data.id}/check_decision_tabel_used_by_template/`;
      return axios.get(url, { params: data }).then(response => response.data);
    },
  },
};

