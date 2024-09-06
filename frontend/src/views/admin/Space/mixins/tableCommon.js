import { mapState } from 'vuex';

const tableCommon = {
  props: {
    createMethod: {
      type: String,
      default: 'API',
    },
    spaceId: [String, Number],
  },
  data() {
    const { current = 1, limit = 20 } = this.$route.query;
    return {
      listLoading: false,
      pagination: {
        current: Number(current),
        count: 0,
        limit: Number(limit),
      },
      totalPage: 1,
      ordering: '',
      requestData: {},
      searchValue: [],
    };
  },
  computed: {
    ...mapState({
      hasAlertNotice: state => state.hasAlertNotice,
    }),
    tableMaxHeight() {
      let maxHeight = window.innerHeight - 154;
      if (this.hasAlertNotice) {
        maxHeight -= 40;
      }
      return maxHeight;
    },
    // 获取默认排序配置
    getDefaultSortConfig() {
      const { ordering } = this;
      if (ordering) {
        if (/^-/.test(this.ordering)) {
          return { prop: ordering.replace(/^-/, ''), order: 'descending' };
        }
        return { prop: ordering, order: 'ascending' };
      }
      return {};
    },
    listFunctionName() {
      return `get${this.pageType.replace(/^\w/, c => c.toUpperCase())}`;
    },
    isSearchEmpty() {
      return !!this.searchValue.length;
    },
  },
  watch: {
    spaceId: {
      handler() {
        this.updateSearchSelect();
        this.getList();
      },
    },
  },
  created() {
    if (this.setting) {
      this.getFields();
    }
  },
  methods: {
    // 获取当前视图表格头显示字段
    getFields() {
      const settingFields = localStorage.getItem(this.pageType);
      let selectedFields;
      if (settingFields) {
        const { fieldList = [], size } = JSON.parse(settingFields);
        this.setting.size = size || 'small';
        selectedFields = fieldList.length ? fieldList : this.defaultSelected;
        if (!fieldList.length || !size) {
          localStorage.removeItem(this.pageType);
        }
      } else {
        selectedFields = this.defaultSelected;
      }
      this.setting.selectedFields = this.tableFields.slice(0).filter(m => selectedFields.includes(m.id));
    },
    // 表格功能选项
    handleSettingChange({ fields, size }) {
      this.setting.size = size;
      this.setting.selectedFields = fields;
      const fieldIds = fields.map(m => m.id);
      localStorage.setItem(this.pageType, JSON.stringify({
        fieldList: fieldIds,
        size,
      }));
    },
    handleSearchSelectChange(val) {
      this.requestData = val;
      this.getList();
    },
    getList() {
      this[this.listFunctionName]();
    },
    handlePageChange(val) {
      this.pagination.current = val;
      this.updateUrl({ current: val });
      this.getList();
    },
    handlePageLimitChange(val) {
      this.pagination.limit = val;
      this.pagination.current = 1;
      this.updateUrl({ limit: val, current: 1 });
      this.getList();
    },
    addSearchRecord(data) {
      const instance = this.$refs.tableOperate;
      instance && instance.addSearchRecord(data);
    },
    updateSearchSelect(data = []) {
      const instance = this.$refs.tableOperate;
      if (instance) {
        instance.searchSelectValue = data;
      }
    },
    updateUrl(data = {}) {
      const { name, query } = this.$route;
      this.$router.replace({
        name,
        query: {
          ...query,
          ...data,
        },
      });
    },
  },
};

export default tableCommon;
