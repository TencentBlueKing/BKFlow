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
  import bus from '@/utils/bus.js';
  import { SPACE_LIST, ROUTE_LIST_MAP } from '@/constants/route.js';


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
        menuRouteName: '',
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
      }),
      isSpaceManager() {
        return !['systemAdmin', 'pluginAdmin'].includes(this.$route.name);
      },
    },
    watch: {
      $route: {
        handler(val) {
          const { meta, name } = val;
          const isAdminRouter = meta.admin && ROUTE_LIST_MAP[name];
          this.menuRouteName = isAdminRouter ? name : 'spaceAdmin';
          const list = isAdminRouter ? ROUTE_LIST_MAP[name] : SPACE_LIST;
          this.routerList = [...list];
          this.setNavigationTitle(val);
        },
        immediate: true,
      },
    },
    created() {
      bus.$on('cancelRoute', () => {
        const { name } = this.$route;
        if (name !== this.currentNav) {
            this.setNavigationTitle(this.$route);
            this.randomKey = new Date().getTime();
        }
      });
    },
    methods: {
      setNavigationTitle(route) {
        if (route.meta.admin) {
          this.currentNav = route.query.activeTab || this.routerList[0].id;
          return;
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
          name: this.menuRouteName,
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
