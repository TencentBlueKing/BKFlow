<template>
  <bk-button
    text
    theme="primary"
    :disabled="isDisabled"
    @click="handleClick">
    {{ '导出' }}
  </bk-button>
</template>
<script>
  import XLSX from 'xlsx-js-style';
  import moment from 'moment-timezone';
  import { getCellText } from './dataTransfer.js';
  export default {
    props: {
      name: {
        type: String,
        default: '',
      },
      data: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {

      };
    },
    computed: {
      isDisabled() {
        return !this.data.records.length;
      },
    },
    methods: {
      handleClick() {
        const { inputs, outputs, records } = this.data;

        // 设置单元格的样式
        const cellStyles = {
          alignment: {
            horizontal: 'center',  // 水平居中
            vertical: 'center',     // 垂直居中
          },
          border: ['top', 'bottom', 'left', 'right'].reduce((acc, side) => {
            acc[side] = { style: 'thin', color: { rgb: '000000' } };
            return acc;
          }, {}),
        };

        // 定义表头和注释
        const headers =  [
          {
            label: 'Input',
            children: inputs.map((item) => {
              const { id, name, ...rest } = item;
              return { label: `${name}(${id})`, description: JSON.stringify(rest) };
            }),
          },
          {
            label: 'Output',
            children: outputs.map((item) => {
              const { id, name, ...rest } = item;
              return { label: `${name}(${id})`, description: JSON.stringify(rest) };
            }),
          },
        ];
        const data = records.reduce((acc, cur) => {
          // 暂时过滤【条件组合】类型！！！
          if (cur.inputs.type !== 'common') return acc;
          const arr = [];
          cur.inputs.conditions.forEach((item, index) => {
            const inputInfo = inputs[index];
            const v = getCellText(item);
            if (inputInfo.type === 'select') {
              // 下拉框类型导出为text
              const option = inputInfo.options.items.find(o => o.id === v);
              arr.push({ v: option.name, t: 's', s: cellStyles });
            } else {
              arr.push({ v, t: 's', s: cellStyles });
            }
          });
          outputs.forEach((item) => {
            if (item.type === 'select') {
              // 下拉框类型导出为text
              const option = item.options.items.find(o => o.id === cur.outputs[item.id]);
              arr.push({ v: option.name, t: 's', s: cellStyles });
            } else {
              arr.push({ v: cur.outputs[item.id], t: 's', s: cellStyles });
            }
          });
          acc.push(arr);
          return acc;
        }, []);

        const wb = XLSX.utils.book_new();

        // 定义工作表数据
        const wsData = [];

        // 表头
        const topHeader = [];
        const subHeader = [];
        const comments = [];

        headers.forEach((header, headerIndex) => {
          topHeader.push({
            v: header.label,
            t: 's',
            s: {
              ...cellStyles,
              font: { bold: true, sz: 16 },
              fill: { fgColor: { rgb: '9FE3FF' } },
            },
          });
          for (let i = 1; i < header.children.length; i++) {
            topHeader.push(null);
          }
          header.children.forEach((child, childIndex) => {
            subHeader.push({
              v: child.label,
              t: 's',
              s: {
                ...cellStyles,
                font: { bold: true },
                fill: { fgColor: { rgb: '9FE3FF' } },
              },
            });
            const c = headerIndex === 0 ? childIndex : (headers[headerIndex - 1].children.length + childIndex);
            comments.push({
              cell: XLSX.utils.encode_cell({ c, r: 1 }),
              comment: child.description,
            });
          });
        });

        wsData.push(topHeader);
        wsData.push(subHeader);

        // 填充数据
        wsData.push(...data);

        // 创建工作表
        const ws = XLSX.utils.aoa_to_sheet(wsData);

        // 合并单元格设置
        let colIndex = 0;
        headers.forEach((header) => {
          ws['!merges'] = ws['!merges'] || [];
          ws['!merges'].push({
            s: { r: 0, c: colIndex },
            e: { r: 0, c: colIndex + header.children.length - 1 },
          });
          colIndex += header.children.length;
        });

        // 添加注释
        comments.forEach(({ cell, comment }) => {
          if (!ws[cell].c) ws[cell].c = [];
          ws[cell].c.hidden = true;
          ws[cell].c.push({ t: comment });
        });

        // 调整列高宽
        ws['!cols'] = subHeader.map(() => ({ wch: 40 }));
        ws['!rows'] = [
          { hpx: 40 },
          { hpx: 25 },
          ...data.map(() => ({ hpx: 20 })),
        ];

        // 将工作表添加到工作簿中
        XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');

        // 导出工作簿
        XLSX.writeFile(wb, `${this.name || 'Decision'}_${moment().format('YYYYMMDDHHmmss')}.xlsx`);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .bk-button-text {
    font-size: 12px;
    color: #63656e;
    &.is-disabled {
      color: #dcdee5;
    }
  }
</style>
