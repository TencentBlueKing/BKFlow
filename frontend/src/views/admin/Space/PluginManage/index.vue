/**
 * Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
 * Edition) available.
 * Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 */
<template>
  <div class="plugin-manage">
    <plugin-manage-header
      ref="manageHeaderRef"
      :space-id="spaceId"
      :categories="categories"
      @save="handleStrategySave" />
    <div class="page-body">
      <CategorySidebar
        :categories="categories"
        :counts="counts"
        :selected="selectedCategory"
        :loading="categoriesLoading"
        @select="handleCategorySelect"
        @batchManage="handleBatchManage" />
      <PluginList
        ref="pluginListRef"
        :category="selectedCategory"
        :category-title="selectedCategoryMeta.title"
        :category-icon="selectedCategoryMeta.icon"
        :categories="flatCategories"
        :category-tree="categories"
        :space-id="spaceId"
        :plugins="plugins"
        :recommend-total="counts.recommend || 0"
        :strategy-mode="strategyMode"
        @editSaved="handleEditSaved"
        @recommendChanged="handleRecommendChanged"
        @statusChange="handleStatusChange"
        @categoryChange="handleCategoryQuickChange"
        @batchCategoryChange="handleBatchCategoryChange"
        @batchStatusChange="handleBatchStatusChange"
        @openStrategy="handleOpenStrategy" />
    </div>
  </div>
</template>

<script>
import CategorySidebar from './CategorySidebar.vue';
import PluginList from './PluginList.vue';
import PluginManageHeader from './PluginManageHeader.vue';
import { CATEGORY_ICONS, buildCategoryNameMap, flattenCategories, getStatusChangeMessage, mapBackendStatus } from './shared';
import { mapActions } from 'vuex';

export default {
  name: 'PluginManage',
  components: {
    CategorySidebar,
    PluginList,
    PluginManageHeader,
  },
  props: {
    spaceId: { type: [String, Number], default: '' },
  },
  data() {
    return {
      categories: [],
      counts: {},
      plugins: [],
      strategyMode: 'review',
      selectedCategory: 'all',
      categoriesLoading: false,
    };
  },
  computed: {
    flatCategories() {
      return flattenCategories(this.categories);
    },
    categoryNameMap() {
      return buildCategoryNameMap(this.categories);
    },
    // 列表标题与图标
    selectedCategoryMeta() {
      const fixedMeta = {
        all: { title: this.$t('全部插件'), icon: CATEGORY_ICONS.all },
        recommend: { title: this.$t('空间推荐'), icon: '' },
        uncategorized: { title: this.$t('未分类插件'), icon: CATEGORY_ICONS.uncategorized },
      };
      return fixedMeta[this.selectedCategory]
        || { title: this.categoryNameMap[this.selectedCategory] || this.$t('全部插件'), icon: '' };
    },
  },
  watch: {
    spaceId() {
      this.selectedCategory = 'all';
      this.$nextTick(() => {
        this.loadSummary();
        this.reloadPluginList();
      });
    },
  },
  created() {
    this.loadSummary();
  },
  methods: {
      ...mapActions('pluginManage', [
        'getPluginSummary',
        'getPluginList',
      'updatePlugin',
      'updateDisableConfig',
      'updatePluginStatus',
      'batchUpdatePluginStatus',
      'batchUpdatePluginCategory',
      'savePluginStrategy',
      'getDirectoryManagePage',
      'saveDirectoryManage',
    ]),
    // summary + 全量插件
    async loadSummary() {
      this.categoriesLoading = true;
      try {
        const [summary, allPlugins] = await Promise.all([
        // 插件概要：目录树 / 三态计数 / 策略摘要 / 推荐计数
        this.getPluginSummary({ space_id: this.spaceId }),
        this.getPluginList({
          space_id: this.spaceId,
          page: 1,
          page_size: 200,
         }),
      ]);
      // ready=false：该空间尚未启用插件目录，避免把空数据展示成「没有插件」
      if (summary.ready === false) {
        this.categories = [];
        this.counts = { all: 0, recommend: 0, uncategorized: 0, tree: {} };
        this.plugins = [];
        this.$bkMessage({
          message: this.$t('本空间尚未启用插件目录，请联系负责人执行初始化命令'),
          theme: 'warning',
        });
        return;
      }
      const plugins = allPlugins.results || [];
      const treeCounts = {};
      const normalizeTree = nodes => (nodes || []).map((node) => {
        treeCounts[String(node.id)] = node.count || 0;
        return {
          ...node,
          id: String(node.id),
          children: normalizeTree(node.children),
        };
      });
      this.categories = normalizeTree(summary.directory_tree || []);
      this.strategyMode = (summary.strategy_summary || {}).mode || 'review';
      this.counts = {
        all: summary.total_count || plugins.length,
        recommend: summary.recommend_count || 0,
        uncategorized: summary.uncategorized_count || 0,
        tree: treeCounts,
      };
      this.plugins = plugins;
      } catch (e) {
        console.log(e);
      } finally {
        this.categoriesLoading = false;
      }
    },
    handleCategorySelect(id) {
      this.selectedCategory = id;
    },
    handleOpenStrategy() {
      if (this.$refs.manageHeaderRef) {
        this.$refs.manageHeaderRef.openStrategy();
      }
    },
    reloadPluginList() {
      if (this.$refs.pluginListRef) {
        this.$refs.pluginListRef.reload();
      }
    },
    handleRecommendChanged() {
      this.loadSummary();
    },
    handleEditSaved() {
      this.loadSummary();
    },
    async handleCategoryQuickChange({ row, categoryId }) {
      try {
        await this.updatePlugin({
          plugin_id: row.id,
          space_id: this.spaceId,
          directory_id: categoryId,
          recommended: !!row.recommended,
        });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: this.$t('保存成功'),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleBatchCategoryChange({ rows, categoryId }) {
      try {
        await this.batchUpdatePluginCategory({
          space_id: this.spaceId,
          ids: rows.map(item => item.id),
          directory_id: categoryId,
        });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: this.$t('已移动 {count} 个插件', { count: rows.length }),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleStatusChange({ row, status, targetDirectoryId, disableReason, replacePluginId, message }) {
      try {
        const data = {
          plugin_id: row.id,
          space_id: this.spaceId,
          status: mapBackendStatus(row.status, status),
        };
        if (data.status === 'enable') {
          Object.assign(data, {
            target_directory_id: targetDirectoryId === undefined ? '' : targetDirectoryId,
          });
        }
        if (data.status === 'disabled') {
          Object.assign(data, {
            disable_reason: disableReason || '',
            replace_plugin_id: replacePluginId || undefined,
          });
        }
        await this.updatePluginStatus(data);
        // 状态变更不影响目录树 / 推荐计数 / 插件总数，无需刷新概要
        this.reloadPluginList();
        this.$bkMessage({
          message: message || getStatusChangeMessage(status, key => this.$t(key)),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleBatchStatusChange({ rows, status, message }) {
      try {
        await this.batchUpdatePluginStatus({
          space_id: this.spaceId,
          ids: rows.map(item => item.id),
          status: mapBackendStatus(rows.length ? rows[0].status : '', status),
        });
        this.reloadPluginList();
        this.$bkMessage({
          message: message || getStatusChangeMessage(status, key => this.$t(key)),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleStrategySave(strategyBody) {
      try {
        const saved = await this.savePluginStrategy({
          space_id: this.spaceId,
          ...strategyBody,
        });
        if (saved && saved.mode) {
          this.strategyMode = saved.mode;
        }
        this.$bkMessage({
          message: this.$t('新插件策略保存成功'),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    handleBatchManage() {
      this.$router.push({
        name: 'categoryManage',
        query: { ...this.$route.query, activeTab: 'pluginManage' },
      });
    },
  },
};
</script>

<style lang="scss" scoped>
.plugin-manage {
    height: 100%;
    display: flex;
    flex-direction: column;
    .page-body {
        flex: 1;
        display: flex;
        gap: 10px;
        min-height: 0;
    }
}
</style>
