<template>
  <div class="decision-table-column">
    <!--序列号-->
    <div
      v-if="hasInputCol || hasOutputCol"
      :style="{ width: `${widthMap.index}px` }"
      class="index-cell">
      {{ $t('序号') }}
    </div>
    <!--表格头单元-->
    <div
      v-for="(column, columnIndex) in columnRenderList"
      :key="columnIndex"
      :style="{ width: `${column.width || widthMap.width}px` }"
      :class="['column-cell', {
        'active-cell': activeCell.type === 'column' && activeCell.index === columnIndex
      }]"
      @click.stop="$emit('updateActiveCell', 'column', columnIndex)">
      <div
        class="column-content"
        :style="{ width: dropdownIndex === columnIndex ? 'calc(100% - 16px)' : '100%' }">
        <i :class="columnTypeIcons[column.type]" />
        <div
          v-bk-overflow-tips
          class="column-name ellipsis">
          {{ column.name }}
        </div>
        <div
          v-bk-overflow-tips
          class="column-id ellipsis">
          {{ `（${column.id}）` }}
        </div>
        <i
          v-if="column.desc"
          v-bk-tooltips.top="{
            content: filterXSS(column.desc),
            allowHTML: false,
            multiple: true,
            maxWidth: 400
          }"
          class="bk-icon icon-question-circle column-tips" />
      </div>
      <span
        ref="tooltipsHtml"
        v-bk-tooltips="columnOperateMenuHtml"
        :style="{ display: dropdownIndex === columnIndex ? 'flex' : 'none' }"
        class="bk-icon icon-angle-up-fill field-dropdown-menu"
        @click="handleOperateMenuShow(column, columnIndex)" />
      <!--列单元格操作面板-->
      <ul
        v-if="readonly"
        id="column-operate-menu"
        class="operate-menu-list">
        <li class="menu-container">
          <div
            class="menu-item"
            @click.stop="handleClickMenu('view')">
            <i class="bk-icon icon-edit-line" />
            <span>{{ $t('查看字段/列') }}</span>
          </div>
        </li>
      </ul>
      <ul
        v-else
        id="column-operate-menu"
        class="operate-menu-list">
        <li
          v-for="(operate, index) in operateList"
          :key="index"
          class="menu-container">
          <div
            v-for="child in operate"
            :key="child.key"
            class="menu-item"
            @click.stop="handleClickMenu(child.key)">
            <i :class="child.icon" />
            <span>{{ child.label }}</span>
          </div>
        </li>
        <li class="menu-container">
          <div
            v-if="canDelete(column)"
            class="menu-item"
            @click.stop="handleClickMenu('delete')">
            <i class="bk-icon icon-delete" />
            <span>{{ $t('删除字段/列') }}</span>
          </div>
          <div
            v-else
            v-bk-tooltips.top="'字段设置了组合条件不允许删除'"
            class="menu-item menu-disabled">
            <i class="bk-icon icon-delete" />
            <span>{{ $t('删除字段/列') }}</span>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
<script>
  import { columnOperateMenu } from '../common/field.js';
  export default {
    name: 'DecisionTableColumn',
    components: {

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
      activeCell: {
        type: Object,
        default: () => ({
          type: '',
          index: -1,
        }),
      },
      readonly: {
        type: Boolean,
        default: true,
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
        dropdownIndex: -1,
        operateList: columnOperateMenu,
        selectedColumn: {
          column: {},
          index: -1,
        },
        columnOperateMenuHtml: {
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
          onClose: this.handleOperateMenuClose,
        },
        ruleKeyList: new Set(),
        columnTypeIcons: {
          string: 'common-icon-string',
          int: 'common-icon-number',
          select: 'common-icon-checkbox',
        },
      };
    },
    computed: {
      columnRenderList() {
        const typeList = ['inputs', 'outputs'];
        const result = [];
        if (!this.hasInputCol && !this.hasOutputCol) {
          return result;
        }
        // 如果没有输入/输出字段时默认添加一个空的用来占位
        typeList.forEach((key) => {
          const value = this.data[key];
          if (value.length) {
            result.push(...value);
          } else {
            result.push({ key: '', name: '', width: this.widthMap[key] || 0 });
          }
        });
        return result;
      },
    },
    watch: {
      data: {
        handler() {
          this.getCombineKeyList();
        },
        deep: true,
        immediate: true,
      },
    },
    methods: {
      // 获取被引用的字段
      getCombineKeyList() {
        this.ruleKeyList.clear();
        this.data.records.forEach((i) => {
          if (i.inputs.type !== 'or_and') return;
          i.inputs.conditions.conditions?.forEach((j) => {
            j.conditions.forEach((k) => {
              this.ruleKeyList.add(k.left.obj.key);
            });
          });
        });
      },
      // 列单元格点击
      handleClickCell(index) {
        this.activeCell.type = 'column';
        this.activeCell.index = index;
      },
      // 打开操作面板
      handleOperateMenuShow(column, index) {
        this.dropdownIndex = index;
        this.selectedColumn = { column, index };
      },
      // 操作点击
      handleClickMenu(operate) {
        const { column, index } = this.selectedColumn;
        // 这个1表达的意思时如果没有输入字段会有一个默认的空字段占位
        const inputLength = this.hasInputCol ? this.data.inputs.length : 1;
        const columnIndex = column.from === 'inputs' ? index : index - inputLength;
        if (operate === 'delete') {
          this.$bkInfo({
            type: 'error',
            theme: 'primary',
            title: this.$t('确定删除字段/列吗？'),
            subTitle: this.$t('删除时，会将整列内容同时删除且不可撤回，请谨慎！'),
            okText: this.$t('删除'),
            confirmFn: () => {
              this.$emit('operate', column.from, operate, columnIndex);
              this.hideTippy();
            },
          });
          return;
        }
        // operate: 操作类型, column.from:inputs or outputs
        this.$emit('operate', column.from, operate, columnIndex);
        this.hideTippy();
      },
      // 是否允许删除列
      canDelete({ from, id }) {
        if (from === 'outputs' || !this.ruleKeyList.size) {
          return true;
        }
        // 与或规则中使用了该字段，不可删除
        return !this.ruleKeyList.has(id);
      },
      // 关闭操作面板
      hideTippy() {
        const { index } = this.selectedColumn;
        const { _tippy: tipInstance } = this.$refs.tooltipsHtml[index] || {};
        tipInstance && tipInstance.hide();
      },
      // 操作面板关闭
      handleOperateMenuClose() {
        this.dropdownIndex = -1;
        this.selectedColumn = {
          column: {},
          index: -1,
        };
      },
    },
  };
</script>
<style lang="scss" scoped>
  .decision-table-column {
    display: flex;
    align-items: center;
    height: 44px;
    width: fit-content;
    font-size: 14px;
    .column-cell {
      height: 100%;
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      color: #313238;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
      &:last-child {
        border-right: none;
      }
      .column-content {
        width: 100%;
        display: flex;
        align-items: center;
        & > i {
          margin-right: 8px;
        }
        .column-id {
          color: #c4c6cc;
        }
        .ellipsis {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .column-tips {
          margin-left: 4px;
          color: #b2bdcc;
        }
      }
      &:hover {
        background: #f4f5f8;
        .field-dropdown-menu {
          display: flex !important;
        }
        .column-content {
          width: calc(100% - 16px) !important;
        }
      }
    }
    .index-cell {
      position: sticky;
      flex-shrink: 0;
      left: 0;
      z-index: 6;
      height: 44px;
      text-align: center;
      line-height: 42px;
      background: #fff;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
    }
    .active-cell {
      background: #e5f4ff;
      &:hover {
        background: #e5f4ff;
      }
    }
  }
</style>
