<template>
  <div
    class="decision-table-cell"
    :style="{ width: `${cell.type === 'common' ? widthMap.width : widthMap[cell.from]}px` }">
    <!--编辑态-->
    <component
      :is="cell.from === 'inputs' ? 'InputCell' : 'OutputCell'"
      v-if="isEditMode"
      :cell="cell" />
    <!--查看配置-->
    <bk-button
      v-else-if="cell.type === 'or_and'"
      text
      @click="$emit('operate', 'group', cell.rowIndex)">
      {{ $t('查看配置') }}
    </bk-button>
    <!--条件组合-表达式-->
    <div
      v-else-if="cell.type === 'expression'"
      v-bk-overflow-tips
      class="cell-text">
      {{ cell.condition }}
    </div>
    <!--查看态-->
    <div
      v-else
      :class="['cell-text', { 'is-placeholder': !cellText }]"
      @click="toggleEditing">
      {{ cellText || cell.column.tips || $t('请输入') }}
    </div>
    <!--异常态-->
    <div
      v-if="!isEditMode && cell.isError"
      class="is-error"
      @click="toggleEditing">
      <i
        v-bk-tooltips="{ content: errorTipContent }"
        class="bk-icon icon-exclamation-circle-shape" />
    </div>
  </div>
</template>
<script>
  import InputCell from './components/InputCell.vue';
  import OutputCell from './components/OutputCell.vue';
  import { generateCellText } from '../../common/field.js';
  import tools from '@/utils/tools.js';
  import i18n from '@/config/i18n/index.js';
  export default {
    name: 'DecisionTableCell',
    components: {
      InputCell,
      OutputCell,
    },
    props: {
      readonly: {
        type: Boolean,
        default: true,
      },
      cell: {
        type: Object,
        default: () => ({}),
      },
      activeCell: {
        type: Object,
        default: () => ({
          type: '',
          index: -1,
        }),
      },
      editCell: {
        type: Object,
        default: () => ({
          rowIndex: -1,
          colIndex: -1,
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
    },
    data() {
      return {
        cellText: '',
      };
    },
    computed: {
      isEditMode() {
        const { rowIndex, colIndex } = this.cell;
        return rowIndex === this.editCell.rowIndex && colIndex === this.editCell.colIndex;
      },
      errorTipContent() {
        return this.cellText ? i18n.t('暂不支持带有英文双引号(") 的输入值') : i18n.t('内容填写不完整');
      },
    },
    watch: {
      cell: {
        handler(val) {
          this.getCellText(val);
          // 通知父级更新数据
          if (val.type === 'common') {
            const cell = tools.deepClone(val);
            this.$emit('updateData', cell);
          }
        },
        deep: true,
        immediate: true,
      },
      isEditMode(val, oldVal) {
        if (!val && oldVal) {
          this.cell.isError = false;
        }
      },
    },
    methods: {
      toggleEditing() {
        if (this.readonly) {
          return;
        }
        const { type, index } = this.activeCell;
        const { rowIndex, colIndex } = this.cell;
        if (type === 'row' && index === rowIndex) {
          this.$emit('updateEditCell', { rowIndex, colIndex });
        }
      },
      getCellText(cell) {
        if (cell.type === 'or_and') {
          this.cellText = this.$t('组合条件');
          return;
        }
        if (!cell.condition || cell.type !== 'common') {
          this.cellText = '';
          return;
        }
        // 输入字段
        if (cell.from === 'inputs') {
          const { compare, right } = cell.condition;
          const { value, type } = right.obj;
          const isNullType = ['is-null', 'not-null'].includes(compare);
          const isIntZero = type === 'int' && value === 0;
          if ((compare && value) || isNullType || isIntZero) {
            this.cellText = String(generateCellText(compare, value, cell));
          } else {
            this.cellText = '';
          }
        }  else {
          // 输出字段
          const { type, options } = cell.column;
          let { value: text } = cell.condition;
          // 下拉框类型
          if (type === 'select') {
            if (!Array.isArray(text)) {
              text = [text];
            }
            text = options.items.reduce((acc, cur) => {
              if (text.includes(cur.id)) {
                acc.push(cur.name);
              }
              return acc;
            }, []).join(' | ');
          }
          this.cellText = text;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .decision-table-cell {
    height: 100%;
    position: relative;
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid #dfe0d5;
    .cell-text {
      min-width: 100%;
      padding: 0 16px;
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow: hidden;
      &.is-placeholder {
        color: #c4c6cc;
      }
    }
    .is-error {
      width: 100%;
      height: 100%;
      position: absolute;
      left: 0;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding-right: 12px;
      border: 1px solid #ea3636;
      i {
        font-size: 14px;
        color: #ea3636;
        cursor: pointer;
      }
    }
    &:not(:last-child) {
      border-right: 1px solid #dfe0d5;
    }
  }
</style>
