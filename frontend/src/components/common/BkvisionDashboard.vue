<template>
  <div :class="['bkvision-dashboard', { 'is-empty': !dashboardUid || !sdkUrl }]">
    <div
      v-if="dashboardUid && sdkUrl"
      :id="containerId"
      class="dashboard-container" />
    <bk-exception
      v-else
      class="dashboard-empty"
      type="empty" />
  </div>
</template>

<script>
  import { uuid } from '@/utils/uuid.js';

  export default {
    name: 'BkvisionDashboard',
    props: {
      dashboardUid: {
        type: String,
        default: '',
      },
      extraParams: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        containerId: `bk-vision-${uuid()}`,
      };
    },
    computed: {
      baseUrl() {
        return window.BKVISION_BASE_URL || '';
      },
      sdkUrl() {
        return window.BKVISION_MAIN_JS_SRC_URL || '';
      },
    },
    watch: {
      dashboardUid() {
        this.initDashboard();
      },
      extraParams: {
        handler() {
          this.initDashboard();
        },
        deep: true,
      },
    },
    mounted() {
      this.initDashboard();
    },
    methods: {
      loadScript(src) {
        return new Promise((resolve, reject) => {
          if (window.BkVisionSDK) {
            resolve();
            return;
          }
          const script = document.createElement('script');
          script.src = src;
          script.onload = resolve;
          script.onerror = reject;
          document.body.append(script);
        });
      },
      async initDashboard() {
        if (!this.dashboardUid || !this.sdkUrl) {
          return;
        }
        try {
          await this.loadScript(this.sdkUrl);
          await this.$nextTick();
          const container = document.getElementById(this.containerId);
          if (!container) {
            return;
          }
          container.innerHTML = '';
          window.BkVisionSDK.init(
            `#${this.containerId}`,
            this.dashboardUid,
            {
              constants: { ...this.extraParams },
              apiPrefix: '/bkvision/',
            },
          );
        } catch (err) {
          console.error(err);
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .bkvision-dashboard {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    &.is-empty {
      min-height: calc(100vh - 100px);
    }
  }
  .dashboard-container {
    width: 100%;
    height: 100%;
  }
</style>
