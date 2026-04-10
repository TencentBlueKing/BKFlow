<template>
  <div class="statistics-dashboard">
    <BkvisionDashboard
      :dashboard-uid="dashboardUid"
      :extra-params="extraParams" />
  </div>
</template>

<script>
  import BkvisionDashboard from '@/components/common/BkvisionDashboard.vue';

  export default {
    name: 'StatisticsDashboard',
    components: {
      BkvisionDashboard,
    },
    props: {
      dashboardUid: {
        type: String,
        default: '',
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
    },
    computed: {
      extraParams() {
        if (this.spaceId) {
          return { space_id: this.spaceId };
        }
        return {};
      },
    },
  };
</script>

<style lang="scss" scoped>
  .statistics-dashboard {
    height: 100%;
  }
</style>
