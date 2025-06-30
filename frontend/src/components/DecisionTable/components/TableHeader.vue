<template>
  <div class="decision-table-header">
    <div
      v-for="item in header"
      :key="item.type"
      :title="item.name"
      :style="{ width: `${widthMap[item.type]}px` }"
      :class="['header-cell', { 'index-header': item.type === 'index' }]">
      <template v-if="item.type === 'index'">
        <i
          v-bk-tooltips="$t('需保证有且仅有一条规则被命中')"
          class="common-icon-info" />
        <bk-popover
          placement="bottom"
          theme="light"
          :tippy-options="{ arrow: false }">
          <i class="bk-icon icon-more" />
          <template slot="content">
            <ImportBtn
              :data="data"
              @updateData="$emit('updateData', $event)" />
            <ExportBtn :data="data" />
          </template>
        </bk-popover>
      </template>
      <template v-else>
        <span class="label">{{ item.name }}</span>
        <bk-button
          v-if="!readonly"
          text
          icon="plus-circle"
          @click="$emit('updateField', item.type, 'add')">
          {{ $t('添加字段') }}
        </bk-button>
      </template>
    </div>
  </div>
</template>
<script>
  import ExportBtn from '../ImportExport/ExportBtn.vue';
  import ImportBtn from '../ImportExport/ImportBtn.vue';
  export default {
    name: 'DecisionTableHeader',
    components: {
      ExportBtn,
      ImportBtn,
    },
    props: {
      data: {
        type: Object,
        default: () => ({
          inputs: [],
          outputs: [],
          records: [],
        }),
      },
      widthMap: {
        type: Object,
        default: () => ({
          index: 84,
          width: 0,
          inputs: 0,
          outputs: 0,
        }),
      },
      readonly: {
        type: Boolean,
        default: true,
      },
    },
    data() {
      return {
        header: [
          {
            name: '',
            type: 'index',
          },
          {
            name: this.$t('条件字段'),
            type: 'inputs',
          },
          {
            name: this.$t('结果字段'),
            type: 'outputs',
          },
        ],
      };
    },
  };
</script>
<style lang="scss" scoped>
  .decision-table-header {
    display: flex;
    align-items: center;
    height: 44px;
    width: fit-content;
    width: 100%;
    font-size: 14px;
    .header-cell {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: space-between;
      height: 100%;
      padding: 0 16px;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
      .label {
        color: #313238;
        margin-right: 8px;
        font-weight: 550;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      ::v-deep .bk-button-text {
        flex-shrink: 0;
        .icon-plus-circle {
          margin-right: 0;
          transform: translateY(-2px);
        }
      }
      &:not(:last-child) {
        border-right: 1px solid #dcdee5;
      }
    }
    .index-header {
      position: sticky;
      left: 0;
      justify-content: space-around;
      z-index: 5;
      padding: 0 12px;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
      .common-icon-info {
        color: #c4c6cc;
        margin-top: 2px;
      }
      .icon-more {
        font-size: 16px;
        cursor: pointer;
        &:hover {
          color: #3a84ff;
        }
      }
    }
  }
</style>
