<template>
  <div
    v-bkloading="{ isLoading: permissionLoading, zIndex: 102 }"
    class="app">
    <template v-if="!permissionLoading">
      <!--管理端导航路由-->
      <div v-if="!isIframe">
        <notice-component
          v-if="enableNoticeCenter"
          :api-url="apiUrl"
          @show-alert-change="handleAlertChange" />
        <Navigation :class="{ 'with-system-notice': hasAlertNotice }">
          <template slot="page-content">
            <router-view />
          </template>
        </Navigation>
      </div>
      <!--非管理端导航路由-->
      <router-view v-else />
    </template>
    <ErrorCodeModal ref="errorModal" />
  </div>
</template>

<script>
  import { mapState, mapMutations, mapActions } from 'vuex';
  import bus from '@/utils/bus.js';
  import ErrorNotify from '@/utils/errorNotify.js';
  import { setConfigContext } from '@/config/setting.js';
  import ErrorCodeModal from '@/components/common/modal/ErrorCodeModal.vue';
  import Cookies from 'js-cookie';
  import NoticeComponent from '@blueking/notice-component-vue2';
  import '@blueking/notice-component-vue2/dist/style.css';
  import Navigation from '@/components/layout/Navigation.vue';

  export default {
    name: 'App',
    components: {
      ErrorCodeModal,
      NoticeComponent,
      Navigation,
    },
    data() {
      return {
        isInit: true,
        permissionLoading: true,
        enableNoticeCenter: window.ENABLE_NOTICE_CENTER,
        apiUrl: `${window.SITE_URL}notice/announcements/`,
        hasAlertNotice: false,
        errorMsgList: [], // message报错实例
      };
    },
    computed: {
      ...mapState({
        siteUrl: state => state.site_url,
        isIframe: state => state.isIframe,
      }),
      spaceId () {
        const { params, query } = this.$route;
        return params.spaceId || query.space_id
      }
    },
    watch: {
      '$route'(val, oldVal) {
        const { name, params, query } = val;
        if (this.isInit && query.token) {
          this.isInit = false;
          this.setToken(query.token);
          Cookies.set('bkflow-token', query.token, {
            expires: 1,
            domain: window.location.hostname.replace(/^[^.]+(.*)$/, '$1'),
            path: '/',
          });
          this.$router.replace({
            name,
            params,
            query: {
              ...query,
              token: undefined,
            },
          });
        } else if (this.isInit) {
          const bkflowToken = Cookies.get('bkflow-token');
          this.setToken(bkflowToken);
        }
        // 路由发生变化时清空失败message列表
        if (val.name !== oldVal.name && this.errorMsgList.length) {
          this.errorMsgList.forEach(msgInstance => {
            msgInstance.close()
          })
          this.errorMsgList = []
        }
      },
      spaceId: {
        handler(val) {
          if (val) {
            this.setSpaceId(Number(val));
          }
        },
      },
    },
    created() {
      // 被iframe嵌套则不需要展示导航
      if (window.top === window.self) {
        // 判断用户是否为管理员
        this.loadSpacePermission();
      } else {
        this.permissionLoading = false;
        this.setIframe(true);
      }

      window.msg_list = [];
      setConfigContext(this.siteUrl);
      bus.$on('showErrorModal', (type, responseText, title) => {
        this.$refs.errorModal.show(type, responseText, title);
      });
      bus.$on('showErrMessage', (info) => {
        const msg = typeof info.message === 'string' ? info.message : JSON.stringify(info.message);
        window.show_msg(msg, 'error', '', info.traceId, info.errorSource);
      });
      /**
       * 兼容标准插件配置项里，异步请求用到的全局弹窗提示
       */
      window.show_msg = (msg, type = 'error', title = '', traceId, errorSource = '') => {
        const index = window.msg_list.findIndex(item => item.msg === msg);
        if (index > -1) {
          if (traceId && !window.msg_list[index].traceId) {
            window.msg_list[index] = { msg, type, title, traceId, errorSource };
          } else {
            return;
          }
        } else {
          window.msg_list.push({ msg, type, title, traceId, errorSource });
        }
        setTimeout(() => { // 异步执行,可以把前端报错的trace_id同步上
          const info = window.msg_list.find(item => item.msg === msg && item.traceId === traceId);
          if (!info) return;
          this.$nextTick(() => {
            /* eslint-disable-next-line */
            new ErrorNotify(info, this)
          });
        });
      };
      this.getGlobalConfig();
    },
    methods: {
      ...mapActions([
        'getSpacePermission',
        'getGlobalConfig',
      ]),
      ...mapMutations([
        'setToken',
        'setAdmin',
        'setSpaceSuperuser',
        'setAlertNotice',
        'setSpaceId',
        'setIframe',
      ]),
      async loadSpacePermission() {
        try {
          this.permissionLoading = true;
          const resp = await this.getSpacePermission();
          const { is_admin: isAdmin, is_space_superuser: isSpaceSuperuser } = resp.data || {};
          this.setAdmin(isAdmin);
          this.setSpaceSuperuser(isSpaceSuperuser);
        } catch (error) {
          console.warn(error);
        } finally {
          this.permissionLoading = false;
        }
      },
      handleAlertChange(val) {
        this.hasAlertNotice = val;
        this.setAlertNotice(val);
      },
    },
  };
</script>

<style lang="scss">
@import "./scss/app.scss";
@import "./scss/config.scss";

html,
body {
  height: 100%;
}
.app {
  width: 100%;
  height: 100%;
  min-width: 1366px;
}
.with-system-notice {
  height: calc(100vh - 40px);
  /deep/.container-content {
    max-height: calc(100vh - 92px)!important;
  }
}
.interface-exception-notify-message {
  .message-detail .message-copy {
    top: 0 !important;
    right: 0 !important;
  }
}
</style>
