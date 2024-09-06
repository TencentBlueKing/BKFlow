<template>
  <div class="navigation-menu">
    <menu-select
      v-if="isSpaceManager"
      :is-expand="isExpand" />
    <bk-navigation-menu
      ref="menu"
      :key="randomKey"
      :default-active="currentNav"
      :toggle-active="true"
      item-default-icon-color="#979ba5"
      item-default-color="#96a2b9"
      item-hover-bg-color="#2f3847"
      item-hover-color="#fff"
      item-hover-icon-color="#fff"
      item-active-bg-color="#3a84ff"
      item-active-icon-color="#fff"
      item-active-color="#fff">
      <bk-navigation-menu-item
        v-for="item in routerList"
        :id="item.id"
        :key="item.name"
        :icon="item.icon"
        :disabled="item.disabled"
        @click="handleNavClick">
        <span>{{ item.name }}</span>
      </bk-navigation-menu-item>
    </bk-navigation-menu>
  </div>
</template>

<script>
  import { mapState } from 'vuex';
  import MenuSelect from './MenuSelect.vue';
  import i18n from '@/config/i18n/index.js';
  import bus from '@/utils/bus.js';

  const SPACE_LIST = [
    {
      name: i18n.t('流程'),
      icon: 'common-icon-flow-menu',
      id: 'template',
      disabled: false,
      subRoutes: ['templatePanel', 'templateMock'],
    },
    {
      name: i18n.t('任务'),
      icon: 'common-icon-task-menu',
      id: 'task',
      disabled: false,
      subRoutes: ['taskExecute'],
    },
    {
      name: i18n.t('调试任务'),
      icon: 'common-icon-mock-menu',
      id: 'mockTask',
      disabled: false,
    },
    {
      name: i18n.t('决策表'),
      icon: 'common-icon-decision-menu',
      id: 'decisionTable',
      disabled: false,
      subRoutes: ['decisionEdit'],
    },
    {
      name: i18n.t('空间配置'),
      icon: 'common-icon-bkflow-setting',
      id: 'config',
      disabled: false,
    },
  ];
  const MODULES_LIST = [
    {
      name: i18n.t('空间配置'),
      icon: 'common-icon-space',
      id: 'space',
      disabled: false,
    },
    {
      name: i18n.t('模块配置'),
      icon: 'common-icon-module',
      id: 'module',
      disabled: false,
    },
  ];
  export default {
    name: 'NavigationMenu',
    components: {
      MenuSelect,
    },
    props: {
      isExpand: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        currentNav: '',
        routerList: [],
        randomKey: null,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
      }),
      isSpaceManager() {
        return this.$route.name !== 'systemAdmin';
      },
    },
    watch: {
      $route: {
        handler(val) {
          if (val.meta.admin) {
            const list = val.name === 'spaceAdmin' ? SPACE_LIST : MODULES_LIST;
            this.routerList = list.slice(0);
          } else {
            this.routerList = SPACE_LIST.slice(0);
          }
          this.setNavigationTitle(val);
        },
        immediate: true,
      },
    },
    created() {
      bus.$on('cancelRoute', () => {
        const { name } = this.$route
        if (name !== this.currentNav) {
            this.setNavigationTitle(this.$route)
            this.randomKey = new Date().getTime()
        }
      })
    },
    methods: {
      setNavigationTitle(route) {
        if (route.meta.admin) {
          const defaultNab = route.name === 'spaceAdmin' ? 'template' : 'space';
          this.currentNav = route.query.activeTab || defaultNab;
          return;
        }
        if (route.name === 'EnginePanel') {
          this.currentNav = route.query.type || 'task'
          return
        }
        this.routerList.some((item) => {
          if (item.subRoutes?.includes(route.name)) {
            this.currentNav = item.id;
            return true;
          }
          return false;
        });
      },
      handleNavClick(id = this.currentNav) {
        this.$router.push({
          name: this.isSpaceManager ? 'spaceAdmin' : 'systemAdmin',
          query: {
            space_id: this.isSpaceManager ? this.spaceId : undefined,
            activeTab: id,
          },
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
  .navigation-menu {
    width: 100%;
    background: #1f2738 !important;
  }
  .space-select {
    width: 240px;
    margin-right: 18px;
    color: #d3d9e4;
    border: none;
    background: #252f43;
  }
</style>
