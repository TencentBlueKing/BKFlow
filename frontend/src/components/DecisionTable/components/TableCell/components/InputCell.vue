<template>
  <div class="input-cell">
    <div
      ref="tooltipsHtml"
      v-bk-tooltips="cellEditMenuHtml"
      class="cell-wrap"
      @click="handleCellClick">
      <span
        v-bk-overflow-tips
        :class="['cell-text', { 'is-placeholder': isDefaultText }]">
        {{ isDefaultText ? (cell.column.tips || $t('请输入')) : cellText }}
      </span>
      <i class="bk-icon icon-1_up" />
    </div>
    <!--输入单元格编辑面板-->
    <div
      id="cell-compare-menu"
      class="compare-menu-wrap">
      <div class="menu-title">
        {{ $t('条件') }}
      </div>
      <CompareSelector
        v-model="cellData.compare"
        :column="cell.column"
        :condition-list="conditionList"
        :cell-data="cellData" />
      <div class="menu-title mt25">
        {{ $t('值') }}
      </div>
      <ValueSelector
        :key="cellData.compare"
        v-model="cellData.right.obj.value"
        :compare="cellData.compare"
        :column="cell.column" />
    </div>
  </div>
</template>
<script>
  import { generateCellText, getConditionList } from '../../../common/field.js';
  import ValueSelector from '../../../common/ValueSelector.vue';
  import CompareSelector from '../../../common/CompareSelector.vue';
  export default {
    name: 'InputCell',
    components: {
      ValueSelector,
      CompareSelector,
    },
    props: {
      cell: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        cellEditMenuHtml: {
          allowHTML: true,
          width: 400,
          trigger: 'click',
          theme: 'light',
          content: '#cell-compare-menu',
          placement: 'bottom-start',
          arrow: false,
          distance: 3,
          zIndex: 8,
          offset: '-15 0',
          hideOnClick: 'toggle',
          extCls: 'compare-menu-popover',
          onHidden: this.handleEditMenuTipsHidden,
        },
        conditionList: [],
        cellText: '',
        isDefaultText: true,
        cellData: this.cell.condition,
      };
    },
    computed: {
      isMultiple() {
        return ['in-range', 'not-in-range'].includes(this.cellData.compare);
      },
    },
    watch: {
      cellData: {
        handler(val) {
          this.getCellText(val);
        },
        deep: true,
        immediate: true,
      },
    },
    methods: {
      handleCellClick() {
        if (this.conditionList.length) return;
        this.conditionList = getConditionList(this.cell.column.type);
      },
      getCellText() {
        const { compare, right } = this.cellData;
        const { value, type } = right.obj;
        const isNullType = ['is-null', 'not-null'].includes(compare);
        const isIntZero = type === 'int' && value === 0;
        // 如果没有值且没有条件时展示默认值
        if (!compare && !value) {
          this.isDefaultText = true;
          return;
        }
        // 如果没有值且条件不为空/非空时不往下计算
        if (!value && !isNullType && !isIntZero) {
          this.isDefaultText = true;
          return;
        }
        // 如果为空/非空时需清空值
        if (isNullType) {
          right.obj.value = '';
        }
        // 计算展示文案
        this.cellText = generateCellText(compare, value, this.cell);
        this.isDefaultText = false;
      },
      // 气泡关闭时如果值为空则恢复为默认数据格式
      handleEditMenuTipsHidden() {
        const { value, type } = this.cellData.right.obj;
        let hasValue = this.cell.column.type === 'int' ? (typeof value === 'number') : !!value?.length;
        // 校验数字类型，范围条件下是否有值
        hasValue = type === 'int[Range]' ? Object.values(value).every(item => item || item === 0) : hasValue;
        // 条件为空/非空 则默认为有值
        hasValue = ['is-null', 'not-null'].includes(this.cellData.compare) ? true : hasValue;
        if (!hasValue) {
          this.cellData.compare = 'equals';
          this.cellData.right.obj = {
            type: this.cell.column.type,
            value: '',
          };
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .input-cell {
    height: 100%;
    width: 100%;
    z-index: 5;
    padding: 0 16px;
    background: #fff;
    border: 1px solid #1272FF;
    box-shadow: 0 0 4px 1px #1272ff33;
    .cell-wrap {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 14px;
      .cell-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        &.is-placeholder {
          color: #c4c6cc;
        }
      }
      i {
        flex-shrink: 0;
        margin-left: 8px;
      }
    }
  }
</style>
<style lang="scss">
  .compare-menu-popover {
    .tippy-tooltip {
      padding: 0;
      box-shadow: 0 2px 10px #0000001a;
    }
    .compare-menu-wrap {
      padding: 20px;
      border: 1px solid #e6e9ee;
      .menu-title {
        font-size: 14px;
        margin-bottom: 8px;
        color: #1e252e;
      }
    }
  }
  .compare-select-popover {
    .bk-option {
      &:hover {
        color: #63656e;
        background: #f4f5f8 !important;
      }
      &.is-selected {
        color: #3a84ff;
        background: #fff;
      }
    }
    .bk-option-content {
      display: flex;
      align-items: center;
    }
  }
</style>
