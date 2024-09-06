<template>
  <div
    ref="apiListPanel"
    class="api-plugin-panel">
    <div class="search-wrap">
      <!-- 公共流程没有标签搜索 -->
      <template v-if="isSelectGroupMode && categoryList.length">
        <bk-select
          v-model="category"
          ext-cls="label-select"
          ext-popover-cls="label-select node-menu-panel-popover"
          :placeholder="$t('请选择标签')"
          :display-tag="true"
          :clearable="true"
          :searchable="true"
          :loading="categoryLoading"
          @clear="handleSearch"
          @change="handleSearch">
          <bk-option
            v-for="(item, index) in categoryList"
            :id="item.id"
            :key="index"
            :name="item.name" />
        </bk-select>
        <div
          class="thumb-icon"
          @click="handleChangeGroupMode(false)">
          <i class="common-icon-search" />
        </div>
      </template>
      <template v-else>
        <div
          v-if="categoryLoading || categoryList.length"
          class="thumb-icon"
          @click="handleChangeGroupMode(true)">
          <i class="common-icon-arrow-down" />
        </div>
        <bk-input
          v-model.trim="searchStr"
          :style="`width: ${!categoryLoading && !categoryList.length ? '100%' : '263px'};`"
          right-icon="bk-icon icon-search"
          :placeholder="$t('请输入插件名称')"
          :clearable="true"
          @change="handleSearchChange"
          @clear="handleSearchClear"
          @enter="handleSearch" />
      </template>
    </div>
    <div
      v-bkloading="{ isLoading: apiLoading }"
      class="plugin-list-wrap">
      <div class="plugin-list">
        <node-item
          v-for="plugin in pluginList"
          :key="plugin.id"
          class="node-item"
          type="task"
          :node="getNodeInfo(plugin)" />
        <NoData
          v-if="pluginList.length === 0"
          class="exception-part"
          :type="(categoryList.length || searchStr) ? 'search-empty' : 'empty'"
          :message="(categoryList.length || searchStr) ? $t('搜索结果为空') : ''"
          @searchClear="handleSearchClear" />
      </div>
    </div>
  </div>
</template>
<script>
  import { mapState, mapActions } from 'vuex';
  import NodeItem from './NodeItem.vue';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'ApiPluginList',
    components: {
      NodeItem,
      NoData,
    },
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        isSelectGroupMode: true,
        categoryList: [],
        category: '',
        searchStr: '',
        pluginList: [],
        categoryLoading: false,
        apiLoading: false,
        pagination: {
          current: 1,
          count: 0,
          limit: 30,
        },
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
        scopeInfo: state => state.template.scopeInfo,
      }),
    },
    beforeDestroy() {
      const listWrapEl = this.$el.querySelector('.plugin-list');
      listWrapEl.removeEventListener('scroll', this.handleApiPluginScroll, false);
    },
    mounted() {
      this.getUniformCategoryList();
    },
    methods: {
      ...mapActions('template', [
        'loadUniformCategoryList',
        'loadUniformApiList',
      ]),
      getNodeInfo(plugin) {
        const category = this.categoryList.find(item => item.id === this.category);
        const { id, name, meta_url } = plugin;
        const apiMeta = {
          id,
          name,
          meta_url,
          category: {
            id: this.category,
            name: category.name,
          },
        };
        return {
          id,
          code: 'uniform_api',
          name,
          nodeName: plugin.name,
          group_name: category.name,
          apiMeta: JSON.stringify(apiMeta),
        };
      },
      async getUniformCategoryList() {
        try {
          this.categoryLoading = true;
          const resp = await this.loadUniformCategoryList({
            ...this.scopeInfo,
            spaceId: this.spaceId,
          });
          if (!resp.result) return;
          this.categoryList = resp.data;
          if (!this.category) {
            this.category = this.categoryList[0]?.id;
          }
          this.getUniformApiList();
          this.$nextTick(() => {
            const listWrapEl = this.$el.querySelector('.plugin-list');
            listWrapEl.addEventListener('scroll', this.handleApiPluginScroll, false);
          });
        } catch (error) {
          console.warn(error);
        } finally {
          this.categoryLoading = false;
        }
      },
      async getUniformApiList(reset = true) {
        try {
          if (this.apiLoading) return;
          this.apiLoading = true;
          const { current, limit } = this.pagination;
          const resp = await this.loadUniformApiList({
            offset: (current - 1) * limit,
            limit,
            spaceId: this.spaceId,
            ...this.scopeInfo,
            category: this.category,
            key: this.searchStr || undefined,
          });
          if (!resp.result) return;
          const pluginList = resp.data.apis;
          if (reset) {
            this.pluginList = pluginList;
          } else {
            this.pluginList.push(...pluginList);
          }
          this.pagination.count = resp.data.total;
        } catch (error) {
          console.warn(error);
        } finally {
          this.apiLoading = false;
        }
      },
      // 切换分组搜索和文本搜索
      handleChangeGroupMode(val) {
        this.isSelectGroupMode = val;
      },
      // 滚动加载逻辑
      handleApiPluginScroll(e) {
        if (this.apiLoading || this.pagination.count === this.pluginList.length) {
          return;
        }
        const { scrollTop, clientHeight, scrollHeight } = e.target;
        if (scrollHeight - scrollTop - clientHeight < 10) {
          this.pagination.current += 1;
          this.getUniformApiList(false);
        }
      },
      handleSearchChange(val) {
        if (val === '') {
          this.handleSearchClear();
        }
      },
      handleSearchClear() {
        this.searchStr = '';
        this.handleSearch();
      },
      handleSearch() {
        this.pagination.current = 1;
        this.getUniformApiList();
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '../../../../../scss/mixins/scrollbar.scss';
  .api-plugin-panel {
    height: 100%;
    .search-wrap {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 11px 14px 12px;
      border-bottom: 1px solid #ccd0dd;
      background: #ffffff;
      .label-select {
        width: 263px;
      }
      .thumb-icon {
        width: 32px;
        height: 32px;
        flex-shrink: 0;
        border: 1px solid #c4c6cc;
        border-radius: 3px;
        font-size: 14px;
        color: #979ba5;
        text-align: center;
        line-height: 28px;
        cursor: pointer;
      }
    }
    .plugin-list-wrap {
      height: calc(100% - 60px);
      .plugin-list {
        height: 100%;
        overflow: auto;
        @include scrollbar;
      }
    }
    .node-item {
      height: 40px;
      line-height: 40px;
      padding: 0 14px;
      color: #63656e;
      font-size: 12px;
      background: #f0f1f5;
      border-top: 1px solid #e2e4ed;
      border-radius: 2px;
      overflow: hidden;
      cursor: move;
      user-select: none;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 1;
      &:first-child {
        border-top: none;
      }
      &:hover {
        background: #fafbfd;
      }
    }
  }
</style>
