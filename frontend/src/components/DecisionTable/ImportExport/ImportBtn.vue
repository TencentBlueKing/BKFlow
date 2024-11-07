<template>
  <div>
    <label
      :for="isDisabled ? '' : 'xls-file'"
      :class="['file-label', { 'is-disabled': isDisabled }]">
      {{ '导入' }}
    </label>
    <input
      id="xls-file"
      ref="fileInput"
      type="file"
      accept=".xlsx, .xls"
      style="display: none;"
      @change="handleFile">
  </div>
</template>
<script>
  import * as XLSX from 'xlsx';
  import tools from '@/utils/tools.js';
  import { validateFiled, parseValue, validateValue, getValueRight } from './dataTransfer.js';
  export default {
    props: {
      data: {
        type: Object,
        default: () => ({}),
      },
    },
    computed: {
      isDisabled() {
        const { inputs, outputs, records } = this.data;
        return inputs.length > 0 || outputs.length > 0 || records.length > 0;
      },
    },
    methods: {
      handleFile(event) {
        const file = event.target.files[0];
        const reader = new FileReader();

        reader.onload = this.processFile;
        reader.onerror = () => {
          this.showMessage('读取文件失败');
        };

        reader.readAsArrayBuffer(file);

        // 处理完文件后，重置文件输入字段
        this.$refs.fileInput.value = '';
      },
      processFile(e) {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });

        // 读取第一个工作表
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // 将工作表转换为JSON
        let jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
        jsonData = jsonData.filter(row => (!row.every(cell => !cell))); // 过滤空行

        // 表格至少三层结构 类型、字段、数据
        if (jsonData.length < 3) {
          this.showMessage('数据结构不对');
          return;
        }

        const sheetValue = Object.values(worksheet);
        this.parseSheetData(jsonData, sheetValue);
      },
      parseSheetData(jsonData, sheetValue) {
        const inputs = [];
        const outputs = [];
        const records = [];
        console.log(jsonData, sheetValue);
        const result = jsonData.some((row, rIndex) => {
          // 类型
          if (rIndex === 0) return false;

          // 字段
          if (rIndex === 1) {
            const { header, result } = this.getHeader(row, sheetValue);
            if (!result) return true;

            // 校验header
            const message = validateFiled(header);
            if (message) {
              this.showMessage(message);
              return true;
            }

            header.forEach((item) => {
              if (item.from === 'inputs') {
                inputs.push(item);
              } else {
                outputs.push(item);
              }
            });

            return false;
          }

          // 数据
          const header = [...inputs, ...outputs];
          const record = this.getRecord(row, header);
          if (!record.result) return true;
          delete record.result;
          records.push(record);

          return false;
        });

        if (result) return;

        this.$emit('updateData', { inputs, outputs, records });
      },
      getHeader(row, sheetValue) {
        const header = [];
        const titleRegex = /^([^\(]+)\(([^)]+)\)$/;
        const result = row.every((cell) => {
          if (!titleRegex.test(cell)) {
            this.showMessage(`表格【${cell}】列标题数据结构不对`);
            return false;
          }

          const comment = sheetValue.find(value => Object.prototype.toString.call(value) === '[object Object]' && value.v === cell);

          if (!comment || !comment.c) {
            this.showMessage(`表格【${cell}】列缺少相应的配置注释`);
            return false;
          }

          const { t } = comment.c[0];
          if (!tools.checkIsJSON(t)) {
            this.showMessage(`表格【${cell}】列的配置注释不是json格式`);
            return false;
          }
          const [, name, id] = cell.match(titleRegex);
          header.push({
            id,
            name,
            ...JSON.parse(t),
          });

          return true;
        });

        return { header, result };
      },
      getRecord(row, header) {
        const inputs = {
          conditions: [],
          type: 'common',
        };
        const outputs = {};

        const result = header.every((col, colIndex) => {
          // 解析value和操作方式
          const { value, type } = parseValue(row[colIndex]);

          // 校验value
          const message = validateValue(value, col);
          if (message) {
            this.showMessage(message);
            return false;
          }

          // 生成record
          if (col.from === 'outputs') {
            outputs[col.id] = value.trim();
          }
          if (col.from === 'inputs') {
            inputs.conditions.push({
              compare: type,
              right: getValueRight(value, type, col),
            });
          }

          return true;
        });

        return { inputs, outputs, result };
      },
      showMessage(message, theme = 'error') {
        this.$bkMessage({ message, theme });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .file-label {
    line-height: 24px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    &:hover {
      color: #3a84ff;
    }
    &.is-disabled {
      color: #dcdee5;
      cursor: not-allowed;
    }
  }
</style>
