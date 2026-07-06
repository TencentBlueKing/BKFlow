<template>
  <div
    v-bkloading="{ isLoading: categoryLoading || apiLoading }"
    class="api-panel">
    <bk-tab-panel
      v-for="tab in apiTabList"
      :key="tab.key"
      :name="tab.key"
      :label="tab.name"
      class="api-plugin-panel">
      <div
        v-if="categoryList.length"
        class="group-area">
        <div
          v-for="option in categoryList"
          :key="option.id"
          :class="['group-item', {
            active: option.id === categoryActive
          }]"
          :data-test-id="`templateEdit_apiList_${option.id}`"
          @click="onSelectCategory(option.id)">
          {{ option.name }}
        </div>
      </div>
      <div class="api-list">
        <template v-if="apiList.length > 0">
          <div
            v-for="(plugin, index) in apiList"
            :key="index"
            :class="['plugin-item', { 'is-active': plugin.id === apiActive }]"
            @click="onSelectApiPlugin(plugin)">
            <span
              v-if="plugin.highlightName"
              class="plugin-name"
              v-html="plugin.highlightName" />
            <span
              v-else
              class="plugin-name">{{ plugin.name }}</span>
          </div>
        </template>
        <NoData
          v-else
          :type="searchStr ? 'search-empty' : 'empty'"
          :message="searchStr ? $t('搜索结果为空') : ''"
          @searchClear="$emit('handleSearch', '')" />
      </div>
    </bk-tab-panel>
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'ApiPlugin',
    components: {
      NoData,
    },
    props: {
      apiTabList: {
        type: Array,
        default: () => ([]),
      },
      currentTab: {
        type: String,
        default: '',
      },
      searchStr: {
        type: String,
        default: '',
      },
      crtPlugin: {
        type: String,
        default: '',
      },
      crtGroup: {
        type: String,
        default: '',
      },
      spaceId: {
        type: [Number, String],
        default: '',
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        categoryLoading: false,
        apiLoading: false,
        categoryList: [],
        categoryActive: '',
        apiList: [],
        apiActive: this.crtPlugin,
        pagination: {
          current: 1,
          count: 0,
          limit: 30,
        },
      };
    },
    computed: {
      crtApiKey() {
        return this.apiTabList.find(item => item.key === this.currentTab)?.key;
      },
    },
    watch: {
      crtApiKey: {
        handler(val) {
          if (val) {
            this.getUniformCategoryList();
          } else {
            this.categoryActive = '';
            this.categoryList = [];
            this.apiActive = '';
            this.apiList = [];
          }
        },
        deep: true,
        immediate: true,
      },
    },
    mounted() {
      const listWrapEl = this.$el.querySelector('.api-list');
      listWrapEl.addEventListener('scroll', this.handleApiPluginScroll, false);
    },
    beforeDestroy() {
      const listWrapEl = this.$el.querySelector('.api-list');
      listWrapEl.removeEventListener('scroll', this.handleApiPluginScroll, false);
    },
    methods: {
      ...mapActions('template', [
        'loadUniformCategoryList',
        'loadUniformApiList',
      ]),
      async getUniformCategoryList() {
        try {
          this.categoryLoading = true;
          const resp = await this.loadUniformCategoryList({
            ...this.scopeInfo,
            spaceId: this.spaceId,
            api_name: this.crtApiKey,
          });
          if (!resp.result) return;
          this.categoryList = resp.data;
          if (!this.categoryActive) {
            this.categoryActive = this.crtGroup || this.categoryList[0]?.id;
          }
          this.getUniformApiList();
        } catch (error) {
          console.warn(error);
        } finally {
          this.categoryLoading = false;
        }
      },
      async getUniformApiList(reset = true) {
        try {
          this.apiLoading = true;
          const { current, limit } = this.pagination;
          const resp = await this.loadUniformApiList({
            offset: (current - 1) * limit,
            limit,
            spaceId: this.spaceId,
            ...this.scopeInfo,
            category: this.categoryActive,
            key: this.searchStr || undefined,
            api_name: this.crtApiKey,
          });
          if (!resp.result) return;
          const pluginList = resp.data.apis;
          const searchStr = this.escapeRegExp(this.searchStr);
          const reg = new RegExp(searchStr, 'i');
          pluginList.forEach((item) => {
            if (this.searchStr !== '') {
              item.highlightName = this.filterXSS(item.name).replace(reg, `<span style="color: #ff9c01;">${this.searchStr}</span>`);
            }
          });
          if (reset) {
            this.apiList = pluginList;
          } else {
            this.apiList.push(...pluginList);
          }
          this.pagination.count = resp.data.total;
        } catch (error) {
          console.warn(error);
        } finally {
          this.apiLoading = false;
        }
      },
      // 滚动加载逻辑
      handleApiPluginScroll(e) {
        if (this.apiLoading || this.pagination.count === this.apiList.length) {
          return;
        }
        const { scrollTop, clientHeight, scrollHeight } = e.target;
        if (scrollHeight - scrollTop - clientHeight < 10) {
          this.pagination.current += 1;
          this.getUniformApiList(false);
        }
      },
      onSelectCategory(categoryId) {
        this.categoryActive = categoryId;
        this.pagination.current = 1;
        this.getUniformApiList();
      },
      onSelectApiPlugin(plugin) {
        const category = this.categoryList.find(item => item.id === this.categoryActive);
        this.$emit('select', {
          id: plugin.id,
          code: 'uniform_api',
          name: plugin.name,
          group_id: this.categoryActive,
          group_name: category.name,
          metaUrl: plugin.meta_url,
          apiKey: this.crtApiKey,
        });
      },
      escapeRegExp(str) {
        if (typeof str !== 'string') {
          return '';
        }
        return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
      },
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../../../scss/mixins/scrollbar.scss';
.api-plugin-panel {
  .api-list {
    height: 100%;
    font-size: 12px;
    color: #63656e;
    overflow: auto;
    @include scrollbar;
    .plugin-item {
      position: relative;
      padding: 0 40px 0 20px;
      height: 42px;
      line-height: 42px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      cursor: pointer;
      &:hover {
        background: #e1ecff;
        color: #3a84ff;
      }
      &.is-active {
        background: #e1ecff;
        & > .plugin-name {
          color: #3a84ff;
        }
      }
    }
  }
}
</style>
