<template>
  <div class="decision-table-header">
    <div
      v-for="item in header"
      :key="item.type"
      :title="item.name"
      :style="{ width: `${widthMap[item.type]}px` }"
      :class="['header-cell', { 'index-header': item.type === 'index' }]">
      <template v-if="item.type !== 'index'">
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
  export default {
    name: 'DecisionTableHeader',
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
      /deep/.bk-button-text {
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
      z-index: 5;
      background: #fafbfd;
      border-bottom: 1px solid #dcdee5;
    }
  }
</style>
