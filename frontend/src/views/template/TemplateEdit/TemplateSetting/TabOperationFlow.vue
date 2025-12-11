<template>
  <bk-sideslider
    :is-show="true"
    :width="800"
    ext-cls="operate-flow"
    :title="$t('操作记录')"
    :quick-close="true"
    :before-close="closeTab">
    <template slot="content">
      <bk-table
        ext-cls="operate-flow-table"
        :data="operateFlowData">
        <bk-table-column
          show-overflow-tooltip
          :render-header="renderTableHeader"
          min-width="130"
          :label="$t('操作时间')"
          prop="operate_date" />
        <bk-table-column
          show-overflow-tooltip
          :render-header="renderTableHeader"
          :label="$t('操作名称')"
          :prop="$store.state.lang === 'en' ? 'operate_type' : 'operate_type_name'" />
        <bk-table-column
          show-overflow-tooltip
          :render-header="renderTableHeader"
          :label="$t('版本')"
          prop="version">
          <template slot-scope="{ row }">
            <span>{{ row.version || '--' }}</span>
          </template>
        </bk-table-column>
        <bk-table-column
          show-overflow-tooltip
          :render-header="renderTableHeader"
          :label="$t('操作来源')"
          prop="operate_source_name" />
        <bk-table-column
          show-overflow-tooltip
          :render-header="renderTableHeader"
          :label="$t('操作人')"
          prop="operator" />
        <div
          slot="empty"
          class="static-ip-empty">
          <NoData />
        </div>
      </bk-table>
    </template>
  </bk-sideslider>
</template>

<script>
  import { mapActions } from 'vuex';
  import moment from 'moment';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    components: {
      NoData,
    },
    data() {
      return {
        operateFlowData: [],
      };
    },
    mounted() {
      this.getOperationTemplateData();
    },
    methods: {
      ...mapActions('task/', [
        'getOperationRecordTemplate',
      ]),
      async getOperationTemplateData() {
        const { params } = this.$route;
        try {
          if (!params.templateId) return;
          const resp = await this.getOperationRecordTemplate({
            templateId: params.templateId,
          });
          this.operateFlowData = resp.data.map((item) => {
            const operateDate = moment(item.operate_date).format('YYYY-MM-DD HH:mm:ss');
            return {
              ...item,
              operate_date: operateDate,
            };
          });
        } catch (error) {
          console.warn(error);
        }
      },
      renderTableHeader(h, { column }) {
        return h('p', {
          class: 'label-text',
          directives: [{
            name: 'bk-overflow-tips',
          }],
        }, [
          column.label,
        ]);
      },
      closeTab() {
        this.$emit('closeTab');
      },
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';
.operate-flow {
    ::v-deep .bk-sideslider-content {
        padding: 20px 30px;
    }
    ::v-deep .operate-flow-table {
        .bk-table-body-wrapper {
            max-height: calc(100vh - 145px);
            color: #63656e;
            overflow-y: auto;
            @include scrollbar;
        }
    }
}
</style>
