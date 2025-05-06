<template>
  <div class="navigation-head-left">
    <ul class="header-nav">
      <template v-for="nav in headerList">
        <li
          v-if="nav.show"
          :key="nav.id"
          class="header-nav-item"
          :class="{ 'item-active': nav.id === navActive }"
          @click="onHandleNavClick(nav)">
          {{ nav.name }}
        </li>
      </template>
    </ul>
  </div>
</template>

<script>
  import { mapState } from 'vuex';
  import { routeNameMap } from '@/constants/route.js';

  export default {
    name: 'NavigationHeadLeft',
    data() {
      return {
        navActive: '',
      };
    },
    computed: {
      ...mapState({
        isAdmin: state => state.isAdmin,
        isSpaceSuperuser: state => state.isSpaceSuperuser,
        isBkPluginManager: state => state.isBkPluginManager,
      }),
      headerList() {
        return [
          {
            name: this.$t('空间管理'),
            id: 'space-manager',
            show: this.isSpaceSuperuser || this.isAdmin,
          },
          {
            name: this.$t('系统管理'),
            id: 'system-manager',
            show: this.isAdmin,
          },
          {
            name: this.$t('我的插件'),
            id: 'plugin-manager',
            show: this.isBkPluginManager,
          },
        ];
      },
    },
    watch: {
      '$route.name': {
        handler(val) {
          if (!val || val === 'home') {
            this.navActive = '';
            return;
          }
          this.navActive = routeNameMap[val] || 'space-manager';
        },
        deep: true,
        immediate: true,
      },
    },
    methods: {
      onHandleNavClick(nav) {
        const { meta } = this.$route;
        if (this.navActive === nav.id && meta.admin) return;

        const routeInfo = Object.entries(routeNameMap).find(routeInfo => routeInfo[1] === nav.id);
        this.$router.push({ name: routeInfo[0] });
      },
    },
  };
</script>

<style lang="scss" scoped>
  .navigation-head-left {
    .header-nav {
      display: flex;
    }
    .header-nav-item {
      height:50px;
      display:flex;
      align-items:center;
      margin-right:40px;
      font-size: 14px;
      color:#96a2b9;
      min-width:56px;
      &:hover {
        cursor:pointer;
        color:#d3d9e4;
      }
      &.item-active {
        color: #fff;
      }
    }
  }
</style>
