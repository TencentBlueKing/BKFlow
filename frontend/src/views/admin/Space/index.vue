<template>
  <div class="space-admin">
    <component
      :is="tableComponent"
      :key="activeTab"
      :space-id="spaceId"
      :create-method="activeTab === 'mockTask' ? 'MOCK' : ''" />
  </div>
</template>

<script>
  import TemplateList from './Template/index.vue';
  import TaskList from './Task/index.vue';
  import SpaceConfigList from './SpaceConfig/index.vue';
  import DecisionTable from './DecisionTable/index.vue';
  import CredentialList from './Credential/index.vue';
  import { mapState } from 'vuex';

  export default {
    name: 'SpaceAdmin',
    components: {
      TemplateList,
      TaskList,
      SpaceConfigList,
      DecisionTable,
      CredentialList,
    },
    data() {
      const { activeTab = 'template' } = this.$route.query;
      return {
        activeTab,
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.spaceId,
      }),
      tableComponent() {
        const tab = this.activeTab;
        let component = tab === 'config' ? 'SpaceConfigList' : 'TaskList';
        component = tab === 'decisionTable' ? 'DecisionTable' : component;
        component = tab === 'template' ? 'TemplateList' : component;
        component = tab === 'credential' ? 'CredentialList' : component;

        return component;
      },
    },
    watch: {
      '$route.query.activeTab'(val) {
        this.activeTab = val;
      },
    },
    methods: {
      onEngineOperate() {
        const { href } = this.$router.resolve({
          name: 'EnginePanel',
          params: {
            spaceId: this.spaceId,
          },
        });
        window.open(href, '_blank');
      },
    },
  };
</script>
<style lang="scss" scoped>
  .space-admin {
    height: 100%;
  }
  /deep/.bk-table-pagination-wrapper {
    background: #fff;
  }
  /deep/.template-name,
  /deep/.task-name {
    color: #3a84ff;
  }
</style>
