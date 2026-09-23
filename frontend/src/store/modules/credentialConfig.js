/**
 * @file credentialConfig store
 */
import axios from 'axios';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    loadCredentialList({}, params) {
      return axios.get('api/space/admin/credential_config/', { params }).then(response => response.data);
    },
    createCredential({}, params) {
      return axios.post(`api/space/admin/credential_config/?space_id=${params.space_id}`, params).then(response => response.data);
    },
    /**
     * 凭证详情接口
     * @param {String} params.spaceId 空间id
     * @param {String} params.id 详情id
     **/
    getCredential({}, params) {
      return axios.get(`api/space/admin/credential_config/${params.id}/?space_id=${params.space_id}`, params).then(response => response.data);
    },
    updateCredential({}, params) {
      return axios.patch(`api/space/admin/credential_config/${params.id}/?space_id=${params.space_id}`, params).then(response => response.data);
    },
    deleteCredential({}, params) {
      return axios.delete(`api/space/admin/credential_config/${params.id}/?space_id=${params.space_id}`, params).then(response => response.data);
    },
  },
};

