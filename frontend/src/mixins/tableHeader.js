
import TableRenderHeader from '@/components/common/TableRenderHeader.vue';

const tableHeader = {
  methods: {
    renderTableHeader(h, { column }) {
      const dateFields = this.dateFields || [];
      if (dateFields.includes(column.property)) {
        const date = this.requestData[column.property];
        return <TableRenderHeader
          ref="TableRenderHeader"
          name={ column.label }
          property={ column.property }
          orderShow = { false }
          dateValue={ date }
          onDateChange={ data => this.handleDateTimeFilter(data, column.property)}>
        </TableRenderHeader>;
      } if (['scope_type', 'scope_value'].includes(column.property)) {
        const tips = column.property === 'scope_type'
          ? '指对应资源在接入平台所属的作用域范围的类型，方便接入平台对资源进行自定义过滤。如该资源属于业务 1，则该字段的值可设为"project"。'
          : '指对应资源在接入平台所属的作用域范围的值，方便接入平台对资源进行自定义过滤。如该资源属于业务1，则该字段的值可设为"1"。';
        return h('span', {
          class: 'scope-column-label',
        }, [
          h('p', {
            class: 'label-text',
            directives: [{
              name: 'bk-overflow-tips',
            }],
          }, [column.label]),
          h('i', {
            class: 'common-icon-info table-header-tips',
            directives: [{
              name: 'bk-tooltips',
              value: tips,
            }],
          }),
        ]);
      }
      return h('p', {
        class: 'label-text',
        directives: [{
          name: 'bk-overflow-tips',
        }],
      }, [
        column.label,
      ]);
    },
    handleDateTimeFilter(date = [], id) {
      const index = this.searchValue.findIndex(item => item.id === id);
      if (date.length) {
        if (index > -1) {
          this.searchValue[index].values = date;
        } else {
          let name = id === 'start_time' ? '开始时间' : '结束时间';
          name = ['create_time', 'create_at'].includes(id) ? '创建时间' : name;
          name = id === 'update_at' ? '更新时间' : name;
          const info = {
            id,
            type: 'dateRange',
            name,
            values: date,
          };
          this.searchValue.push(info);
          // 添加搜索记录
          this.addSearchRecord(info);
        }
      } else if (index > -1) {
        this.searchValue.splice(index, 1);
      }
    },
  },
};

export default tableHeader;
