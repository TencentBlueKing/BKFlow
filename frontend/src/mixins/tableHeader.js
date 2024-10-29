
import TableRenderHeader from '@/components/common/TableRenderHeader.vue';
import i18n from '@/config/i18n/index.js';

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
          ? i18n.t('scopeType')
          : i18n.t('scopeValue');
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
