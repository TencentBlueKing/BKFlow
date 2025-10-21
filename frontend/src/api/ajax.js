/**
 * @file ajax 封装
 */

import Vue from 'vue';
import axios from 'axios';
import i18n from '@/config/i18n/index.js';
import bus from '@/utils/bus.js';
import store from '@/store/index.js';
import { showLoginModal } from '@blueking/login-modal';
import { generateTraceId } from '@/utils/uuid.js';

axios.defaults.baseURL = window.SITE_URL;
axios.defaults.xsrfCookieName = `${window.APP_CODE}_csrftoken`;
axios.defaults.xsrfHeaderName = 'X-CSRFToken';
axios.defaults.withCredentials = true;
axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

axios.interceptors.request.use(
  (config) => {
    config.headers['Bkflow-TOKEN'] = store.state.token || '';
    config.headers.TRACEPARENT = generateTraceId();
    return config;
  },
  error => Promise.reject(error)
);

// 拦截器：在这里对ajax请求做一些统一公用处理
axios.interceptors.response.use(
  (response) => {
    if (Object.prototype.hasOwnProperty.call(response.data, 'result') && !response.data.result) {
      const info = {
        message: response.data,
        traceId: response.headers['bkflow-engine-trace-id'],
        errorSource: 'result',
      };
      if (!response.config.url.includes('template/admin/batch_delete/')) {
        bus.$emit('showErrMessage', info);
      }
    }
    return response;
  },
  (error) => {
    // 取消接口请求
    if (error.message === 'cancelled') {
      console.warn('cancelled');
      return Promise.reject(error);
    }

    const { response } = error;
    console.log(response);
    if (response.data.message) {
      response.data.msg = response.data.message;
    }
    if (response.data.responseText) {
      response.data.msg = response.data.responseText;
    }

    switch (response.status) {
      case 400: {
        const msg = response.data.error || response.data.msg || response.data.msg.error;
        const errorInfo = {
          traceId: response.headers['bkflow-engine-trace-id'],
          message: msg,
        };
        bus.$emit('showErrMessage', errorInfo);
        break;
      }
      case 401: {
        const { data } = response;
        if (data.has_plain && !window.loginWindow) {
          // 退出登录接口不打开登录弹框
          if (response.config.url.indexOf('/logout') === -1) {
            const successUrl = `${window.location.origin}${window.SITE_URL}static/bkflow/login_success.html`;
            let [loginUrl] = data.login_url.split('?');
            loginUrl = `${loginUrl}?c_url=${encodeURIComponent(successUrl)}`;

            showLoginModal({ loginUrl });
          }
        }
        break;
      }
      case 403:
        bus.$emit('showErrorModal', 403);
        break;
      case 500:
        bus.$emit('showErrorModal', response.status, response.data.responseText);
        break;
    }
    if (!response.data) {
      const msg = i18n.t('接口数据返回为空');
      console.warn(i18n.t('接口异常，'), i18n.t('HTTP状态码：'), response.status);
      console.error(msg);
      response.data = {
        code: response.status,
        msg,
      };
    } else {
      const msg = response.data;
      response.data = {
        code: response.status,
        msg,
      };
    }
    return Promise.reject(response);
  }

);

Vue.prototype.$http = axios;

export default axios;
