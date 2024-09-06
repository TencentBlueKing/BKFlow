<template>
  <div class="system-admin">
    <component
      :is="activeTab === 'space' ? 'SpaceConfig' : 'ModuleList'"
      :key="activeTab" />
  </div>
</template>

<script>
  import ModuleList from './Module/index.vue';
  import SpaceConfig from './SpaceConfig/index.vue';
  export default {
    name: 'SystemAdmin',
    components: {
      ModuleList,
      SpaceConfig,
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
    watch: {
      '$route.query.activeTab'(val) {
        this.activeTab = val;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .system-admin {
    height: 100%;
  }
  /deep/.bk-table-pagination-wrapper {
    background: #fff;
  }
  /deep/.bk-tab-section {
    padding: 20px 0 20px;
  }
</style>
