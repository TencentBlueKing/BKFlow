<template>
  <bk-navigation
    :side-title="appName"
    :default-open="true"
    navigation-type="top-bottom"
    :need-menu="isNeedMenu"
    @toggle="isExpand = $event">
    <div
      slot="side-icon"
      class="logo-area"
      @click="$router.push({ name: 'home' })">
      <img
        :src="platformInfo.appLogo || logo"
        height="24px"
        class="logo mt5">
    </div>
    <template slot="header">
      <navigator-head-left />
      <navigator-head-right />
    </template>
    <template slot="menu">
      <navigation-menu :is-expand="isExpand" />
    </template>
    <slot name="page-content" />
  </bk-navigation>
</template>

<script>
  import { mapState, mapActions, mapMutations } from 'vuex';
  import NavigatorHeadLeft from './NavigationHeadLeft.vue';
  import NavigatorHeadRight from './NavigationHeadRight.vue';
  import NavigationMenu from './NavigationMenu.vue';
  export default {
    name: 'Navigation',
    components: {
      NavigatorHeadLeft,
      NavigatorHeadRight,
      NavigationMenu,
    },
    data() {
      return {
        logo: require('../../assets/images/logo.png'),
        isExpand: false,
      };
    },
    computed: {
      ...mapState({
        platformInfo: state => state.platformInfo,
        isAdmin: state => state.isAdmin,
        spaceId: state => state.spaceId,
        isCurSpaceSuperuser: state => state.isCurSpaceSuperuser,
      }),
      isNeedMenu() {
        const { name, meta } = this.$route;
        let isShow = meta.admin || this.isAdmin || this.isCurSpaceSuperuser;
        isShow = isShow && name && name !== 'home';
        return isShow;
      },
      appName() {
        const { i18n, name } = this.platformInfo;
        return i18n.name || name;
      },
    },
    watch: {
      spaceId: {
        handler(val) {
          if (val) {
            this.loadCurSpacePermission();
          }
        },
      },
    },
    methods: {
      ...mapActions([
        'getCurrentSpacePermission',
      ]),
      ...mapMutations([
        'setAdmin',
        'setCurSpaceSuperuser',
      ]),
      async loadCurSpacePermission() {
        try {
          const resp = await this.getCurrentSpacePermission({ space_id: this.spaceId });
          const { is_admin: isAdmin, is_space_superuser: isCurSpaceSuperuser } = resp.data || {};
          this.setAdmin(isAdmin);
          this.setCurSpaceSuperuser(isCurSpaceSuperuser);
        } catch (error) {
          console.warn(error);
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .bk-navigation {
    min-width: 1366px;
    .logo-area {
      cursor: pointer;
    }
    /deep/.header-right {
      justify-content: space-between;
    }
    /deep/.navigation-container {
      max-width: 100% !important;
    }
    /deep/.container-content {
      position: relative;
      padding: 0 !important;
    }

    /deep/.nav-slider {
      background: #1f2738 !important;
      .nav-slider-list {
        height: 100% !important;
      }
    }
  }
</style>
