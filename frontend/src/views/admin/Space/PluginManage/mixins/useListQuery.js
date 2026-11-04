/**
 * 列表查询条件：状态 Tab / 搜索条件（Search select）/ 分页
 */
export default {
  props: {
    // 当前选中分类 id（作为查询条件之一，切换分类后回到第一页并重置状态 Tab）
    category: {
      type: String,
      default: 'all',
    },
  },
  data() {
    return {
      activeTab: 'visible',
      // 输入型-模糊匹配：插件名称(name) / 最近修改人(updatedBy)
      // 枚举型-选择匹配：类型(type) / 来源(source) / 目录(category)
      searchValues: [],
      // 接口返回的总条数，同步给分页组件
      total: 0,
      pagination: {
        current: 1,
        count: 0,
        limit: 10,
      },
    };
  },
  computed: {
    // 搜索条件转查询参数
    searchParams() {
      const params = {
        // 枚举型条件（类型/来源/目录）为数组，支持同字段多选；输入型为单值字符串
        searchType: [],
        searchSource: [],
        searchCategory: [],
        searchName: '',
        searchDesc: '',
        searchUpdatedBy: '',
        // 不选择条件的手动输入：多个独立关键词，彼此 OR（模糊匹配插件名称 / 最近修改人）
        keyword: [],
      };
      const enumFields = ['type', 'source', 'category'];
      const fieldMap = {
        type: 'searchType',
        source: 'searchSource',
        category: 'searchCategory',
        name: 'searchName',
        desc: 'searchDesc',
        updatedBy: 'searchUpdatedBy',
      };
      (this.searchValues || []).forEach((chip) => {
        const { id, name, values } = chip || {};
        const text = String(name || '').trim();
        // 多词之间 OR（模糊匹配插件名称 / 最近修改人），重复输入去重
        if (!Array.isArray(values) || !values.length || !fieldMap[id]) {
          if (text && !params.keyword.includes(text)) params.keyword.push(text);
          return;
        }
        // 枚举型取选项 id、输入型取文本 name；键名在循环外算一次，避免每个候选项重复判断
        const isEnumField = enumFields.includes(id);
        const valueKey = isEnumField ? 'id' : 'name';
        const picked = values
          .map(item => item && item[valueKey])
          .filter(val => val !== undefined && val !== null && val !== '');
        if (isEnumField) {
          // 同字段多个 chip 合并去重（如「类型：API 插件」+「类型：蓝鲸插件」）
          params[fieldMap[id]] = Array.from(new Set(params[fieldMap[id]].concat(picked)));
        } else if (picked.length) {
          const [first] = picked;
          params[fieldMap[id]] = first;
        }
      });
      console.log('searchParams', params);
      return params;
    },
    queryParams() {
      const search = this.searchParams;
      return {
        category: this.category,
        status: this.activeTab,
        type: search.searchType.length ? search.searchType : 'all',
        source: search.searchSource.length ? search.searchSource : 'all',
        searchName: search.searchName,
        searchDesc: search.searchDesc,
        searchUpdatedBy: search.searchUpdatedBy,
        searchCategory: search.searchCategory,
        keyword: search.keyword,
        page: this.pagination.current,
        page_size: this.pagination.limit,
      };
    },
  },
  watch: {
    total: {
      handler(val) {
        this.pagination.count = val;
        this.clampCurrentPage();
      },
      immediate: true,
    },
    // 状态 Tab 变化
    activeTab() {
      this.resetPageAndFetch();
    },
    // 搜索条件变化
    searchValues() {
      this.resetPageAndFetch();
    },
    'pagination.current'() {
      this.fetchList();
    },
    'pagination.limit'() {
      this.resetPageAndFetch();
    },
    // 切换分类
    category() {
      if (this.activeTab !== 'visible') {
        this.activeTab = 'visible';
        return;
      }
      this.resetPageAndFetch();
    },
  },
  methods: {
    fetchList() {},
    reload() {
      this.resetPageAndFetch();
    },
    // 查询条件变化后回到第一页再请求（已是第一页时直接请求，避免重复触发）
    resetPageAndFetch() {
      if (this.pagination.current === 1) {
        this.fetchList();
      } else {
        this.pagination.current = 1;
      }
    },
    // 总条数变少时收敛当前页码，避免停在空白页
    clampCurrentPage() {
      const totalPage = Math.max(Math.ceil(this.pagination.count / this.pagination.limit), 1);
      if (this.pagination.current > totalPage) {
        this.pagination.current = totalPage;
      }
    },
  },
};
