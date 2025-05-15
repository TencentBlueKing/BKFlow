<template>
  <div class="navigation-head-right">
    <!-- 语言 -->
    <div
      v-bk-tooltips="{
        ...basicTipsConfig,
        extCls: 'more-language-tips',
        content: '#more-language-html'
      }"
      class="language-icon">
      <i :class="`bk-icon icon-${curLanguage}`" />
    </div>
    <div id="more-language-html">
      <div
        class="operate-item"
        :class="{ 'active': curLanguage === 'chinese' }"
        data-test-id="navHeader_list_chinese"
        @click="toggleLanguage('chinese')">
        <i class="bk-icon icon-chinese" />
        {{ '中文' }}
      </div>
      <div
        class="operate-item"
        :class="{ 'active': curLanguage === 'english' }"
        data-test-id="navHeader_list_english"
        @click="toggleLanguage('english')">
        <i class="bk-icon icon-english" />
        {{ 'English' }}
      </div>
    </div>
    <!-- 更多操作 -->
    <div
      v-bk-tooltips="{
        ...basicTipsConfig,
        extCls: 'more-operation-tips',
        content: '#more-operation-html'
      }"
      :class="['help-icon', { active: isMoreOperateActive }]">
      <i class="common-icon-help" />
    </div>
    <div id="more-operation-html">
      <div
        class="operate-item"
        @click="goToHelpDoc">
        {{ $t('产品文档') }}
      </div>
      <div
        class="operate-item"
        @click="onOpenVersion">
        {{ $t('版本日志') }}
      </div>
    </div>
    <!-- 用户icon -->
    <div
      v-bk-tooltips="{
        ...basicTipsConfig,
        distance: 25,
        extCls: 'logout-tips',
        content: '#logout-html'
      }"
      class="user-avatar">
      {{ username }}
      <i class="bk-icon icon-down-shape" />
    </div>
    <div id="logout-html">
      <div
        class="operate-item"
        @click="handleLogout">
        {{ $t('退出登录') }}
      </div>
    </div>
    <!-- 日志组件 -->
    <version-log
      ref="versionLog"
      :log-list="logList"
      :log-detail="logDetail"
      :md-mode="true"
      :loading="logListLoading || logDetailLoading"
      @active-change="handleVersionChange" />
  </div>
</template>
<script>
  import { mapActions, mapMutations, mapState } from 'vuex';
  import VersionLog from './VersionLog.vue';
  import Cookies from 'js-cookie';
    import axios from 'axios';

  export default {
    name: 'NavigationHeadRight',
    components: {
      VersionLog,
    },
    data() {
      return {
        bkDocUrl: window.BK_DOC_URL,
        logList: [],
        logDetail: '',
        isMoreOperateActive: false,
        logListLoading: false,
        logDetailLoading: false,
        curLanguage: 'chinese',
        basicTipsConfig: {
          placement: 'bottom-end',
          allowHtml: 'true',
          arrow: false,
          distance: 17,
          theme: 'light',
          hideOnClick: false,
        },
      };
    },
    computed: {
      ...mapState({
        username: state => state.username,
      }),
    },
    watch: {

    },
    created() {
      this.curLanguage = window.getCookie('blueking_language') === 'en' ? 'english' : 'chinese';
      // this.queryHasNewVersion()
    },
    methods: {
      ...mapActions([
        'logout',
        'queryNewVersion',
        'getVersionList',
        'getVersionDetail',

      ]),
      ...mapActions('project', [
        'loadUserProjectList',
      ]),
      ...mapMutations('project', [
        'setProjectId',
      ]),
      async toggleLanguage(language) {
        this.curLanguage = language;
        const local = language === 'chinese' ? 'zh-cn' : 'en';
        const domain = window.BK_DOMAIN || window.location.hostname.replace(/^[^.]+(.*)$/, '$1');
        Cookies.set('blueking_language', local, {
          expires: 1,
          domain,
          path: '/',
        });
        if (window.BK_PAAS_ESB_HOST) {
            const url = `${window.BK_PAAS_ESB_HOST}/api/c/compapi/v2/usermanage/fe_update_user_language/`;
            try {
              await axios.jsonp(url, { language: local });
            } catch (error) {
              console.warn(error);
            } finally {
              window.location.reload();
            }
        } else {
            window.location.reload();
        }
    },
      goToHelpDoc() {
        window.open(this.bkDocUrl, '_blank');
      },
      // 查询用户是否读过最新的产品日志，如果自动弹出日志弹窗
      async queryHasNewVersion() {
        const res = await this.queryNewVersion();
        if (!res.data.has_read_latest) {
          this.onOpenVersion();
        }
      },
      /* 打开版本日志 */
      async onOpenVersion() {
        this.$refs.versionLog.show();
        try {
          this.logListLoading = true;
          const res = await this.getVersionList();
          this.logList = res.data;
        } catch (e) {
          console.log(e);
        } finally {
          this.logListLoading = false;
        }
      },
      async loadLogDetail(version) {
        try {
          this.logDetailLoading = true;
          const res = await this.getVersionDetail({ version });
          this.logDetail = res.data;
        } catch (e) {
          console.log(e);
        } finally {
          this.logDetailLoading = false;
        }
      },
      handleVersionChange(data) {
        const version = data[0];
        this.loadLogDetail(version);
      },
      async handleLogout() {
        try {
          await this.logout();
        } catch (error) {
          console.warn(error);
        } finally {
          let loginUrl = window.LOGIN_URL;
          loginUrl = /\/$/.test(loginUrl) ? loginUrl : `${loginUrl}/`;
          window.location.replace(`${loginUrl}?is_from_logout=1&c_url=${window.location.href}`);
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .navigation-head-right {
    display: flex;
    align-items: center;
    .language-icon,
    .help-icon {
      display: flex;
      justify-content: center;
      align-items: center;
      width: 32px;
      height: 32px;
      font-size: 16px;
      color: #768197;
      border-radius: 50%;
      cursor: pointer;
      transition: brackground .2s;
      &.tippy-active {
        background: linear-gradient(270deg,#253047,#263247);
        i {
          color: #d3d9e4;
        }
      }
    }
    .language-icon {
      margin-right: 10px;
      font-size: 18px;
    }
    .common-icon-help {
      font-size: 14px;
    }
    .user-avatar {
      margin-left: 16px;
      font-size: 14px;
      color: #96a2b9;
      cursor: pointer;
      .icon-down-shape {
        position: relative;
        top: -1px;
        color: #979ba5;
      }
      &:hover {
        color: #d3d9e4;
        i {
          color: #d3d9e4;
        }
      }
    }
    ::v-deep .bk-select.is-disabled {
      background: none;
    }
  }
</style>
<style lang="scss">
  .tippy-popper.more-language-tips,
  .tippy-popper.logout-tips,
  .tippy-popper.more-operation-tips {
    .tippy-tooltip {
      padding: 4px 0;
      border: 1px solid #dcdee5;
      box-shadow: 0 2px 6px 0 rgba(0,0,0,0.10);
      border-radius: 2px;
      .tippy-content {
        padding: 0;
      }
    }
    #more-language-html,
    #logout-html,
    #more-operation-html {
      .operate-item {
        display: block;
        height: 32px;
        line-height: 33px;
        padding: 0 16px;
        color: #63656e;
        font-size: 12px;
        text-decoration: none;
        white-space: nowrap;
        cursor: pointer;
        &:hover {
          background-color: #eaf3ff;
          color: #3a84ff;
        }
      }
    }
    #more-language-html {
      .operate-item {
        padding: 0 14px;
        .bk-icon {
          font-size: 14px;
        }
        &.active {
          background-color: #eaf3ff;
          color: #3a84ff;
        }
      }
    }
  }
</style>
