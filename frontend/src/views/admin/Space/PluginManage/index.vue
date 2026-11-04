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
      :strategy="strategy"
      :categories="categories"
      @save="handleStrategySave" />
    <div class="page-body">
      <CategorySidebar
        :categories="categories"
        :counts="counts"
        :selected="selectedCategory"
        @select="handleCategorySelect"
        @init="handleInitCategory"
        @batch-manage="handleBatchManage" />
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
        @edit-saved="handleEditSaved"
        @recommend-changed="handleRecommendChanged"
        @status-change="handleStatusChange"
        @category-change="handleCategoryQuickChange"
        @batch-category-change="handleBatchCategoryChange"
        @batch-status-change="handleBatchStatusChange"
        @delete="handleDeletePlugins"
        @clean="handleCleanPlugins" />
    </div>
  </div>
</template>

<script>
import CategorySidebar from './CategorySidebar.vue';
import PluginList from './PluginList.vue';
import PluginManageHeader from './PluginManageHeader.vue';
import { CATEGORY_ICONS, buildCategoryNameMap, createDefaultStrategy, flattenCategories, getStatusChangeMessage } from './shared';
import {
  getPluginSummary,
  updatePlugin,
  updatePluginStatus,
  batchUpdatePluginStatus,
  batchUpdatePluginCategory,
  deletePlugins,
  cleanPlugins,
  savePluginStrategy,
  initCategories,
} from './api';

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
      strategy: createDefaultStrategy(),
      plugins: [],
      selectedCategory: 'all',
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
  created() {
    this.loadSummary();
  },
  methods: {
    async loadSummary() {
      const { categories, counts, strategy, plugins } = await getPluginSummary({
        spaceId: this.spaceId,
      });
      this.categories = categories;
      this.counts = counts;
      this.strategy = strategy;
      this.plugins = plugins;
    },
    handleCategorySelect(id) {
      this.selectedCategory = id;
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
    async handleCategoryQuickChange({ row, categoryId, followSource }) {
      try {
        await updatePlugin({
          spaceId: this.spaceId,
          pluginId: row.id,
          data: {
            category: categoryId,
            followSource: !!followSource,
            recommended: !!row.recommended,
            offlineReason: row.offlineReason || '',
            replacePluginId: row.replacePluginId || '',
          },
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
    async handleBatchCategoryChange({ rows, categoryId, followSource }) {
      try {
        await batchUpdatePluginCategory({
          spaceId: this.spaceId,
          ids: rows.map(item => item.id),
          category: categoryId,
          followSource: !!followSource,
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
    async handleStatusChange({ row, status, category, offlineReason, replacePluginId, message }) {
      try {
        await updatePluginStatus({
          spaceId: this.spaceId,
          pluginId: row.id,
          status,
          category,
          offlineReason,
          replacePluginId,
        });
        await this.loadSummary();
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
        await batchUpdatePluginStatus({
          spaceId: this.spaceId,
          ids: rows.map(item => item.id),
          status,
        });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: message || getStatusChangeMessage(status, key => this.$t(key)),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleDeletePlugins(rows) {
      try {
        await deletePlugins({
          spaceId: this.spaceId,
          ids: rows.map(item => item.id),
        });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: this.$t('删除成功'),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleCleanPlugins(rows) {
      try {
        await cleanPlugins({
          spaceId: this.spaceId,
          ids: rows.map(item => item.id),
        });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: this.$t('清理成功'),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    async handleStrategySave(strategyConfig) {
      try {
        await savePluginStrategy({ spaceId: this.spaceId, strategy: strategyConfig });
        await this.loadSummary();
        this.reloadPluginList();
        this.$bkMessage({
          message: this.$t('新插件策略保存成功'),
          theme: 'success',
        });
      } catch (e) {
        console.log(e);
      }
    },
    handleInitCategory() {
      this.$bkInfo({
        title: this.$t('确认初始化插件分类目录？'),
        subTitle: this.$t('初始化后将恢复为默认分类目录，自定义分类将被清除'),
        maskClose: false,
        width: 450,
        confirmFn: async () => {
          try {
            await initCategories({ spaceId: this.spaceId });
            await this.loadSummary();
            this.reloadPluginList();
            this.$bkMessage({
              message: this.$t('初始化成功'),
              theme: 'success',
            });
          } catch (e) {
            console.log(e);
          }
        },
      });
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
