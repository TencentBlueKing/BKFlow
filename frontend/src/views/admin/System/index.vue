<template>
  <div class="system-admin">
    <component
      :is="currentComponent"
      :key="activeTab"
      :dashboard-uid="systemDashboardUid" />
  </div>
</template>

<script>
  import ModuleList from './Module/index.vue';
  import SpaceConfig from './SpaceConfig/index.vue';
  import StatisticsDashboard from '@/components/common/StatisticsDashboard.vue';

  const TAB_COMPONENT_MAP = {
    space: 'SpaceConfig',
    module: 'ModuleList',
    statistics: 'StatisticsDashboard',
  };

  export default {
    name: 'SystemAdmin',
    components: {
      ModuleList,
      SpaceConfig,
      StatisticsDashboard,
    },
    props: {
      hasAlertNotice: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      const { activeTab = 'space' } = this.$route.query;
      return {
        activeTab,
      };
    },
    computed: {
      systemDashboardUid() {
        return window.BKVISION_SYSTEM_DASHBOARD_UID || '';
      },
      currentComponent() {
        return TAB_COMPONENT_MAP[this.activeTab] || 'SpaceConfig';
      },
    },
    watch: {
      '$route.query.activeTab'(val) {
        this.activeTab = val;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .system-admin {
    height: 100vh;
  }
  ::v-deep .bk-table-pagination-wrapper {
    background: #fff;
  }
  ::v-deep .bk-tab-section {
    padding: 20px 0 20px;
  }
</style>
