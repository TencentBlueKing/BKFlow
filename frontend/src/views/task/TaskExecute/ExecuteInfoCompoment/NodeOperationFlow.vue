<template>
  <div class="node-operate-flow">
    <bk-table
      v-bkloading="{ isLoading: isFlowLoading }"
      ext-cls="node-operate-flow-table"
      :data="operateFlowData">
      <bk-table-column
        width="220"
        :label="$t('操作时间')"
        prop="operate_date" />
      <bk-table-column
        width="140"
        :label="$t('操作类型')"
        :prop="$store.state.lang === 'en' ? 'operate_type' : 'operate_type_name'" />
      <bk-table-column
        width="160"
        :label="$t('操作来源')"
        :prop="$store.state.lang === 'en' ? 'operate_source' : 'operate_source_name'" />
      <bk-table-column
        width="150"
        :label="$t('操作人')"
        prop="operator" />
      <div
        slot="empty"
        class="empty-data">
        <NoData />
      </div>
    </bk-table>
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import moment from 'moment';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    components: {
      NoData,
    },
    props: {
      nodeId: {
        type: String,
        default: '',
      },
      subProcessTaskId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        isFlowLoading: false,
        operateFlowData: [],
      };
    },
    watch: {
      nodeId() {
        this.getOperationTaskData();
      },
    },
    mounted() {
      this.getOperationTaskData();
    },
    methods: {
      ...mapActions('task/', [
        'getOperationRecordTask',
      ]),
      async getOperationTaskData() {
        const { query } = this.$route;
        try {
          this.isFlowLoading = true;
          if (!this.nodeId) { // 未执行的任务节点操作历史为空
            this.operateFlowData = [];
            return;
          }
          const resp = await this.getOperationRecordTask({
            taskId: this.subProcessTaskId || query.instanceId,
            node_id: this.nodeId || undefined,
          });
          this.operateFlowData = resp.data.map((item) => {
            const operateDate = moment(item.operate_date).format('YYYY-MM-DD HH:mm:ss');
            return {
              ...item,
              operate_date: operateDate,
            };
          }) || [];
        } catch (error) {
          console.warn(error);
        } finally {
          this.isFlowLoading = false;
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';
::v-deep .node-operate-flow-table {
    .bk-table-body-wrapper {
        max-height: calc(100vh - 145px);
        color: #63656e;
        overflow-y: auto;
        @include scrollbar;
    }
    td {
        min-height: 43px !important;
        .cell {
            display: block;
        }
    }
}
</style>
