<template>
  <div class="decision-table">
    <div
      ref="tableDom"
      :class="['decision-table-container', {
        'unset-border': hasInputCol && hasOutputCol
      }]">
      <!-- 表格头 -->
      <TableHeader
        :data="tableData"
        :width-map="widthMap"
        :readonly="readonly || partiallyEdited"
        @updateField="updateField" />
      <!-- 表格列 -->
      <TableColumn
        :data="tableData"
        :width-map="widthMap"
        :active-cell="activeCell"
        :readonly="readonly || partiallyEdited"
        :has-input-col="hasInputCol"
        :has-output-col="hasOutputCol"
        @updateActiveCell="updateActiveCell"
        @operate="handleFieldOperate" />
      <!-- 表格行 -->
      <TableBody
        ref="tableBody"
        :data="tableData"
        :width-map="widthMap"
        :active-cell="activeCell"
        :readonly="readonly"
        :has-input-col="hasInputCol"
        :has-output-col="hasOutputCol"
        @updateData="handleUpdateRecord"
        @updateActiveCell="updateActiveCell"
        @operate="handleRowOperate" />
      <!--空状态-->
      <bk-exception
        v-if="!hasInputCol"
        :style="{
          width: `${widthMap.inputs + 1}px` ,
          left: `${widthMap.index - 1}px`,
          height: `${Math.max(231, (tableData.records.length + 2) * 44)}px`
        }"
        class="field-empty"
        type="empty"
        scene="part">
        {{ $t('暂未添加条件字段') }}
        <div
          v-if="isValidError && !hasInputCol"
          style="color: #ea3636;">
          {{ $t('条件字段未配置，请先完成字段配置') }}
        </div>
      </bk-exception>
      <bk-exception
        v-if="!hasOutputCol"
        :style="{
          width: `${widthMap.outputs + 1 - (hasInputCol ? 1 : 0)}px` ,
          left: `${widthMap.index + widthMap.inputs - 1}px`,
          height: `${Math.max(231, (tableData.records.length + 2) * 44)}px`,
          'border-right': 'none'
        }"
        class="field-empty"
        type="empty"
        scene="part">
        {{ $t('暂未添加结果字段') }}
        <div
          v-if="isValidError && !hasOutputCol"
          style="color: #ea3636;">
          {{ $t('结果字段未配置，请先完成字段配置') }}
        </div>
      </bk-exception>
    </div>
    <!--错误信息-->
    <div
      v-if="isEmptyValid"
      class="error-msg">
      {{ $t('请至少完整填写一条规则') }}
    </div>
    <!--侧栏-->
    <SideSlider
      :slide-info="slideInfo"
      :col-field-info="colFieldInfo"
      :readonly="readonly || (partiallyEdited && slideInfo.type === 'field')"
      :inputs="tableData.inputs"
      :slider-width="sliderWidth"
      @onConfirm="handleSaveRule"
      @onClose="handleSliderClose"
      @updateField="handleSaveField" />
  </div>
</template>
<script>
  import TableHeader from './components/TableHeader.vue';
  import TableColumn from './components/TableColumn.vue';
  import TableBody from './components/TableBody.vue';
  import SideSlider from './SideSlider/index.vue';
  import { makeId } from '@/utils/uuid.js';
  import tools from '@/utils/tools.js';
  export default {
    name: 'DecisionTable',
    components: {
      TableHeader,
      TableColumn,
      TableBody,
      SideSlider,
    },
    props: {
      readonly: {
        type: Boolean,
        default: false,
      },
      data: {
        type: Object,
        default: () => ({
          inputs: [],
          outputs: [],
          records: [],
        }),
        required: true,
      },
      sliderWidth: {
        type: Number,
        default: 1000,
      },
      partiallyEdited: { // 半编辑
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        tableDom: null,
        resizeObserver: null,
        widthMap: {
          index: 84,
          width: 0,
          inputs: 0,
          outputs: 0,
        },
        tableData: {
          inputs: [],
          outputs: [],
          records: [],
        },
        activeCell: {
          type: '',
          index: '',
        },
        slideInfo: {
          isShow: false,
          title: '',
          type: '',
          operate: '',
          from: '',
        },
        colFieldInfo: {},
        isValidError: false,
        isEmptyValid: false,
      };
    },
    computed: {
      hasInputCol() {
        return !!this.tableData.inputs.length;
      },
      hasOutputCol() {
        return !!this.tableData.outputs.length;
      },
    },
    watch: {
      data: {
        handler(val) {
          // 临时处理！！！由于产品形态上不支持填空，所以使用【is-null, not-null】的旧数据需要暂转为【equal】
          val.records.forEach((recode) => {
            if (recode.inputs.type !== 'common') return;
            recode.inputs.conditions.forEach((item) => {
              if (['is-null', 'not-null'].includes(item.compare)) {
                item.compare = 'equals';
                item.right.obj.value = '';
              }
            });
          });

          this.tableData = val;
        },
        deep: true,
        immediate: true,
      },
      tableData: {
        handler(val) {
          this.isEmptyValid = false;
          this.isValidError = false;
          this.$emit('updateData', val);
        },
        deep: true,
      },
    },
    mounted() {
      this.tableDom = this.$refs.tableDom;
      // 监听表格尺寸变化
      this.resizeObserver = new ResizeObserver(() => {
        setTimeout(() => {
          this.computeWidth();
        }, 0);
      });
      this.resizeObserver.observe(this.tableDom);
    },
    beforeDestroy() {
      this.resizeObserver.unobserve(this.tableDom);
    },
    methods: {
      // 计算表格列、表格头宽度
      computeWidth() {
        const totalWidth = this.tableDom?.offsetWidth || 0;
        const { inputs, outputs } = this.tableData;
        // 最少一列
        const inputLength = inputs.length || 1;
        const outputLength = outputs.length || 1;
        // 单元格宽度
        let width = (totalWidth - 2 - this.widthMap.index) / (inputLength + outputLength);
        width = Math.max(width, 220);
        this.widthMap.width = width;
        // 空状态宽度
        const emptyMin = totalWidth * 0.25;
        const emptyMax = totalWidth * 0.5;
        const emptyWidth = Math.max(emptyMin, Math.min(width, emptyMax));
        this.widthMap.inputs = inputLength ? inputLength * width : emptyWidth;
        this.widthMap.outputs = outputLength ? outputLength * width : emptyWidth;
      },
      // 更新表格列字段
      updateField(type, operate, index = -1) {
        const field = type === 'inputs' ? this.$t('条件字段') : this.$t('结果字段');
        let sideTypeText = operate === 'add' ? this.$t('新增') : this.$t('编辑');
        sideTypeText = this.readonly || this.partiallyEdited ? this.$t('查看') : sideTypeText;
        const isEnMode = window.getCookie('blueking_language') === 'en';
        this.slideInfo = {
          isShow: true,
          title: `${sideTypeText}${isEnMode ? ' ' : ''}${field}`,
          type: 'field',
          operate,
          from: type,
          index,
        };
      },
      // 更新单元格选中态
      updateActiveCell(type = '', index = -1) {
        this.activeCell = { type, index };
      },
      // 表格列操作
      handleFieldOperate(type, operate, index) {
        const colInfo = this.tableData[type][index];
        switch (operate) {
          // 字段编辑
          case 'view':
          case 'edit':
            this.colFieldInfo = colInfo;
            this.updateField(type, operate);
            break;
          // 字段复制
          case 'copy': {
            const data = { ...colInfo, id: `field${makeId(8)}`, name: `${colInfo.name}_clone` };
            this.handleSaveField(data, {
              index: index + 1,
              from: type,
              operate: 'copy',
              oldKey: colInfo.id,
            });
            break;
          }
          case 'insert-left':
          case 'insert-right':
            this.updateField(type, 'add', operate === 'insert-left' ? index : index + 1);
            break;
          // 删除字段
          case 'delete':
            this.handleDeleteField(type, index);
            break;
        }
      },
      // 保存表格列字段
      handleSaveField(data, config) {
        const { from, operate, index = 0 } = config;
        if (['add', 'copy'].includes(operate)) {
          // 字段插入或复制
          if (index > -1) {
            this.tableData[from].splice(index, 0, data);
          } else {
            this.tableData[from].push(data);
          }
          this.handleUpdateRecord('add', {
            ...config,
            key: data.id,
            index: operate === 'copy' ? index - 1 : index,
          });
          this.computeWidth();
          return;
        }
        const colIndex = this.tableData[from].findIndex(item => item.id === data.id);
        this.tableData[from].splice(colIndex, 1, data);
      },
      // 删除表格列字段
      handleDeleteField(type, index) {
        this.tableData[type].splice(index, 1);
        // 删除对应的数据
        this.tableData.records.forEach((record) => {
          if (type === 'outputs') {
            const key = Object.keys(record[type])[index];
            delete record[type][key];
          } else if (record[type].type === 'common') {
            record[type].conditions.splice(index, 1);
          }
        });
        this.updateActiveCell();
        // 重新计算宽度
        this.computeWidth();
      },
      // 新增、编辑表格数据
      handleUpdateRecord(type, config = {}) {
        // 编辑
        if (type === 'edit') {
          const { condition, rowIndex, from, colIndex } = config;
          const fromRecords = this.tableData.records[rowIndex][from];
          if (from === 'inputs') {
            fromRecords.conditions[colIndex] = condition;
          } else {
            fromRecords[condition.key] = condition.value;
          }
          return;
        }
        // 新增
        const { index, from, operate, key, oldKey } = config;
        this.tableData.records.forEach((record) => {
          if (from === 'inputs') {
            /**
             * 如果先创建结果字段后直接添加行，那么再创建输入字段会拿不到conditions
             * 因为添加行的时候没有输入字段所以没有设置conditions，所以在这里需要补上
             */
            if (!record[from].conditions) {
              record[from] = this.getDefaultInputsValue();
              return;
            }

            const { conditions, type } = record[from];
            if (type !== 'common') return;

            if (operate === 'copy') { // 复制
              conditions.splice(index, 0, tools.deepClone(conditions[index]));
            } else { // 新增
              const colInfo = this.tableData.inputs.slice(index)[0];
              const condition = {
                compare: 'equals',
                right: {
                  type: 'value',
                  obj: {
                    type: colInfo.type,
                    value: '',
                  },
                },
              };
              if (index > -1) {
                conditions.splice(index, 0, condition);
              } else {
                conditions.push(condition);
              }
            }
          } else {
            record[from][key] = operate === 'copy' ? tools.deepClone(record[from][oldKey]) : '';
          }
        });
      },
      // 表格行操作
      handleRowOperate(operate, config = {}) {
        const { index } = config;
        const { records } = this.tableData;
        switch (operate) {
          case 'copy': {
            const rowData = tools.deepClone(records[index]);
            this.handleAddRow(index + 1, rowData);
            break;
          }
          case 'add':
            this.handleAddRow(records.length);
            break;
          case 'group':
            this.handleCombine(index);
            break;
          case 'insert-top':
          case 'insert-bottom': {
            const insertIndex = operate === 'insert-top' ? index : index + 1;
            this.handleAddRow(insertIndex);
            break;
          }
          case 'delete': {
            records.splice(index, 1);
            break;
          }
          // 排序
          case 'sort': {
            const { start, end } = config;
            const rowData = records[start];
            records.splice(end, 0, rowData);
            const deleteIndex = start < end ? start : start + 1;
            records.splice(deleteIndex, 1);
            break;
          }
        }
      },
      // 新增行
      handleAddRow(index, row) {
        let data = {};
        if (row) {
          data = row;
        } else {
          data.inputs = this.getDefaultInputsValue();
          data.outputs = this.getDefaultOutputsValue();
        }
        this.tableData.records.splice(index, 0, data);
      },
      // 获取默认值
      getDefaultInputsValue() {
        if (!this.tableData.inputs.length) {
          return {};
        }
        const conditions = this.tableData.inputs.map(item => ({
          compare: 'equals',
          right: {
            type: 'value',
            obj: {
              type: item.type,
              value: '',
            },
          },
        }));
        return { type: 'common', conditions };
      },
      getDefaultOutputsValue() {
        return this.tableData.outputs.reduce((acc, cur) => {
          acc[cur.id] = '';
          return acc;
        }, {});
      },
      // 查看配置
      handleCombine(index) {
        const record = this.tableData.records[index];
        const value = ['or_and', 'expression'].includes(record.inputs.type) ? record.inputs : {};
        this.slideInfo = {
          isShow: true,
          title: this.$t('组合条件设置'),
          type: 'combine',
          operate: '',
          from: '',
          value,
          index,
        };
      },
      // 关闭侧栏
      handleSliderClose() {
        this.slideInfo = {
          isShow: false,
          title: '',
          type: '',
          operate: '',
          from: '',
        };
        this.colFieldInfo = {};
      },
      // 条件组合保存
      handleSaveRule(data) {
        const { index } = this.slideInfo;
        this.tableData.records[index].inputs = data || this.getDefaultInputsValue();
      },
      // 校验
      validate() {
        if (!this.hasInputCol || !this.hasOutputCol) {
          this.isValidError = true;
          return false;
        }
        return this.$refs.tableBody.validate();
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '../../scss/mixins/scrollbar.scss';
  .decision-table {
    background: #fff;
    .decision-table-container {
      position: relative;
      overflow-x: auto;
      @include scrollbar;
      border: 1px solid #dfe0d5;
      &.unset-border {
        border-bottom: none;
      }
    }
    /deep/.field-dropdown-menu {
      display: none;
      width: 16px;
      height: 16px;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      border-radius: 2px;
      background: transparent;
      color: #475468;
      &:hover {
        display: flex !important;
        background: #dfe0e5;
      }
      &:active {
        background: #d1d7e1;
      }
    }
    .field-empty {
      position: absolute;
      z-index: 2;
      top: 44px;
      background: #fff;
      border-right: 1px solid #dcdee5;
      border-left: 1px solid #dcdee5;
      /deep/.bk-exception-text {
        line-height: 20px;
      }
    }
    .error-msg {
      color: #ea3636;
      font-size: 14px;
    }
  }
</style>
<style lang="scss">
  .operate-menu-popover{
    .tippy-tooltip {
      border: 1px solid #dcdee5;
      padding: 4px 0;
      background: #fff !important;
    }
    .operate-menu-list {
      width: 140px;
      .menu-container {
        padding: 4px 0;
        width: 100%;
        font-size: 14px;
        border-bottom: 1px solid #edeff3;
        .menu-item {
          height: 36px;
          padding: 7px 12px;
          display: flex;
          align-items: center;
          color: #313238;
          background: #fff;
          cursor: pointer;
          & > i {
            margin-right: 8px;
            color: #7588A3;
          }
          &:hover {
            background: #F4F5F8;
          }
        }
        .menu-disabled {
          color: #b2bdcc;
          cursor: not-allowed;
          & > i {
            color: #b2bdcc;
          }
          &:hover {
            background: #fff;
          }
        }
        &:last-child {
          border-bottom: none;
        }
      }
    }
  }
</style>
