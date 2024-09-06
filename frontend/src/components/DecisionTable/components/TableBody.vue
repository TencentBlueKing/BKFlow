<template>
  <div class="decision-table-body">
    <vue-draggable
      :value="renderData"
      handle=".row-handle"
      :force-fallback="true"
      drag-class="row-drag"
      :sort="false"
      :style="{ minHeight: (!hasInputCol || !hasOutputCol) ? '187px' : 'unset' }"
      @start="dragRowStart"
      @end="dragRowEnd">
      <div
        v-for="(row, rowIndex) in renderData"
        :key="rowIndex"
        :class="[
          'table-row',
          {
            'active-row': judgeHightLight(rowIndex),
            'row-drag-hover': dragRowIndex > -1
          }
        ]"
        @mouseover="dropRowIndex = rowIndex"
        @click.stop="$emit('updateActiveCell', 'row', rowIndex)">
        <!--序列号-->
        <div
          :class="['index-wrap', { 'active-cell': dropdownIndex === rowIndex }]"
          :style="{ width: `${widthMap.index}px` }">
          <i
            v-if="!readonly"
            class="row-handle common-icon-drawable" />
          <span class="row-index">{{ rowIndex + 1 }}</span>
          <i
            v-if="!readonly"
            ref="tooltipsHtml"
            v-bk-tooltips="rowOperateMenuHtml"
            class="bk-icon icon-angle-up-fill field-dropdown-menu"
            @click="dropdownIndex = rowIndex" />
        </div>
        <!--没有输入字段时添加空的占位dom-->
        <div
          v-if="!hasInputCol"
          :style="{ width: `${widthMap.inputs}px` }" />
        <!--单元格-->
        <TableCell
          v-for="(cell, cellIndex) in row"
          :key="cellIndex"
          :class="{ 'active-cell': judgeHightLight(rowIndex, cell) }"
          :readonly="readonly"
          :cell="cell"
          :active-cell="activeCell"
          :edit-cell="editCell"
          :width-map="widthMap"
          @operate="handleClickMenu"
          @updateData="$emit('updateData', 'edit', $event)"
          @updateEditCell="editCell = $event" />
        <!--列单元格操作面板-->
        <ul
          v-if="!readonly"
          id="column-operate-menu"
          class="operate-menu-list">
          <li
            v-for="(operate, index) in operateList"
            :key="index"
            class="menu-container">
            <div
              v-for="child in operate"
              :key="child.key"
              :class="['menu-item', { 'menu-disabled': child.key === 'group' && !hasInputCol }]"
              @click.stop="handleClickMenu(child.key, rowIndex)">
              <i :class="child.icon" />
              <span>{{ child.label }}</span>
            </div>
          </li>
        </ul>
      </div>
      <!--新增行-->
      <div
        v-if="!readonly && (hasInputCol || hasOutputCol)"
        :class="['table-row', 'plus-row', { 'row-drag-hover': dragRowIndex > -1 }]"
        @mouseover="dropRowIndex = renderData.length"
        @click.stop="handleClickMenu('add')">
        <div
          class="index-wrap"
          :style="{ width: `${widthMap.index}px` }">
          <i class="bk-icon icon-plus-line" />
        </div>
        <div
          :style="{ width: `${widthMap.inputs + widthMap.outputs}px` }"
          class="empty-cell" />
      </div>
    </vue-draggable>
  </div>
</template>
<script>
  import VueDraggable from 'vuedraggable';
  import TableCell from './TableCell/index.vue';
  import { rowOperateMenu } from '../common/field.js';
  import tools from '@/utils/tools.js';
  export default {
    name: 'DecisionTableBody',
    components: {
      VueDraggable,
      TableCell,
    },
    props: {
      readonly: {
        type: Boolean,
        default: true,
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
      activeCell: {
        type: Object,
        default: () => ({
          type: '',
          index: -1,
        }),
      },
      data: {
        type: Object,
        default: () => ({
          inputs: [],
          outputs: [],
          records: [],
        }),
      },
      hasInputCol: {
        type: Boolean,
        default: false,
      },
      hasOutputCol: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        renderData: [],
        operateList: rowOperateMenu,
        dropdownIndex: -1,
        rowOperateMenuHtml: {
          allowHTML: true,
          width: 140,
          trigger: 'click',
          theme: 'light',
          content: '#column-operate-menu',
          placement: 'bottom-start',
          arrow: false,
          distance: 2,
          zIndex: 8,
          extCls: 'operate-menu-popover',
          onClose: () => {
            this.dropdownIndex = -1;
          },
        },
        editCell: {
          rowIndex: -1,
          colIndex: -1,
        },
        dragRowIndex: -1,
        dropRowIndex: -1,
      };
    },
    computed: {
      selectedRow() {
        const { index } = this.activeCell;
        if (index > -1) {
          return this.renderData[index];
        }
        return [];
      },
    },
    watch: {
      activeCell: {
        handler(val) {
          const key = val.type === 'row' ? 'rowIndex' : 'colIndex';
          if (this.editCell[key] === val.index) {
            return;
          }
          this.editCell = {
            rowIndex: -1,
            colIndex: -1,
          };
        },
        deep: true,
      },
      data: {
        handler(val) {
          this.getRenderData(val.records);
        },
        deep: true,
        immediate: true,
      },
    },
    methods: {
      // 获取表格数据
      getRenderData(records) {
        records = tools.deepClone(records);
        this.renderData = records.map((record, rowIndex) => {
          const { inputs, outputs } = record;
          const data = [];
          // 输入
          if (this.data.inputs.length) {
            if (inputs.type === 'common') {
              inputs.conditions.forEach((item, index) => {
                const column = this.data.inputs[index];
                data.push({
                  from: 'inputs',
                  type: inputs.type,
                  condition: item,
                  column,
                  rowIndex,
                  colIndex: index,
                  isError: false,
                });
              });
            } else {
              data.push({
                from: 'inputs',
                type: inputs.type,
                condition: inputs.conditions,
                rowIndex,
                isError: false,
              });
            }
          }
          // 输出
          this.data.outputs.forEach((item, index) => {
            const condition = { key: item.id, value: outputs[item.id] };
            const colIndex = index + (this.data.inputs.length || 0);
            data.push({
              from: 'outputs',
              type: 'common',
              condition,
              column: item,
              rowIndex,
              colIndex,
              isError: false,
            });
          });
          return data;
        });
      },
      // 行开始拖拽
      dragRowStart(e) {
        this.dragRowIndex = e.oldIndex;
      },
      // 行结束拖拽
      dragRowEnd() {
        if (this.dropRowIndex !== -1 && this.dragRowIndex !== this.dropRowIndex) {
          const config = { start: this.dragRowIndex, end: this.dropRowIndex };
          this.$emit('operate', 'sort', config);
        }
        this.dragRowIndex = -1;
        this.dropRowIndex = -1;
      },
      // 行操作面板选中
      handleClickMenu(operate, rowIndex) {
        // 如果没有输入列禁止点击
        if (operate === 'group' && !this.hasInputCol) {
          return;
        }
        this.$emit('operate', operate, { index: rowIndex });
        this.hideTippy();
        if (operate === 'add' && this.hasInputCol) {
          // 默认选中新增的行
          this.$nextTick(() => {
            const rowIndex = this.renderData.length - 1;
            this.editCell = {
              rowIndex,
              colIndex: 0,
            };
            this.$emit('updateActiveCell', 'row', rowIndex);
          });
        }
      },
      // 关闭操作面板
      hideTippy() {
        const { index } = this.activeCell;
        const tooltipsInstance = this.$refs.tooltipsHtml;
        if (tooltipsInstance) {
          const { _tippy: tipInstance } = tooltipsInstance[index] || {};
          tipInstance && tipInstance.hide();
        }
      },
      // 判断行是否高亮
      judgeHightLight(rowIndex, cell = {}) {
        const { type, index } = this.activeCell;
        if (type === 'column') {
          const inputCount = this.data.inputs.length;
          return cell.colIndex === index
            || (['or_and', 'expression'].includes(cell.type) && index < inputCount);
        }
        return rowIndex === index;
      },
      // 校验
      validate() {
        if (!this.renderData.length) {
          this.$parent.isEmptyValid = true;
          return false;
        }
        let result = true;
        this.renderData.forEach((row) => {
          // 判断整行是否全为空
          const isEmpty = row.every((cell) => {
            if (['or_and', 'expression'].includes(cell.type)) {
              return false;
            }
            return !this.hasValue(cell);
          });
          // 不全为空时进行校验
          if (!isEmpty) {
            row.forEach((cell) => {
              if (!this.hasValue(cell)) {
                cell.isError = true;
                result = false;
              }
            });
          }
        });
        return result;
      },
      hasValue(cell) {
        if (cell.from === 'outputs') {
          const { value } = cell.condition;
          return value === 0 ? true : value;
        }
        if (cell.type !== 'common') {
          return true;
        }
        const { value } = cell.condition.right?.obj;
        if (value === 0 || ['is-null', 'not-null'].includes(cell.condition.compare)) {
          return true;
        }
        return !!value;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .decision-table-body {
    width: fit-content;
    .table-row {
      height: 44px;
      display: flex;
      align-items: center;
      font-size: 14px;
      color: #575961;
      .index-wrap {
        position: sticky;
        left: 0;
        z-index: 6;
        height: 100%;
        display: flex;
        flex-shrink: 0;
        justify-content: center;
        align-items: center;
        padding: 0 8px;
        background: #fff;
        border-right: 1px solid #dfe0d5;
        border-bottom: 1px solid #dfe0d5;
        .row-handle {
          display: none;
          font-size: 16px;
          color: #7588a3;
          cursor: move;
        }
        .row-index {
          margin: -2px 14px 0;
        }
        &.active-cell,
        &:hover {
          i {
            display: flex !important;
          }
        }
      }
      &:hover {
        background: #f4f5f8;
        .index-wrap {
          background: #f4f5f8;
        }
      }
    }
    .active-row,
    .active-cell {
      background: #e5f4ff !important;
      .index-wrap {
        background: #e5f4ff !important;
      }
    }
    .plus-row {
      cursor: pointer;
      background: #fff;
      .empty-cell {
        height: 100%;
        border-bottom: 1px solid #dfe0d5;
      }
    }
    .row-drag-hover:hover {
      background: #fff;
      border-top: 1px solid #3a84ff;
      div {
        pointer-events: none;
      }
    }
    .row-drag {
      background: #e5f4ff !important;
      border:  1px solid #e6e9ee;
      border-bottom: none;
      .row-handle {
        display: block !important;
      }
    }
  }
</style>
