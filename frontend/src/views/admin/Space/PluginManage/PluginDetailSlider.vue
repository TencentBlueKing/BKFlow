<template>
  <bk-sideslider
    :is-show="visible"
    :transfer="true"
    :width="960"
    ext-cls="plugin-detail-slider"
    :quick-close="true"
    @update:isShow="handleVisibleChange">
    <template slot="header">
      <div class="detail-header">
        <span class="header-title">{{ $t('插件详情') }}</span>
      </div>
    </template>
    <div
      slot="content"
      v-bkloading="{ isLoading: loading }"
      class="detail-content">
      <template v-if="detail">
        <div class="detail-hero">
          <div class="hero-row">
            <div class="hero-message">
              <div class="plugin-logo">
                {{ logoText }}
              </div>
              <div class="hero-title">
                <div class="title-line">
                  <span class="plugin-name">{{ detail.plugin.name }}</span>
                  <span :class="['status-tag', `is-${detail.plugin.status}`]">
                    {{ statusInfo.label }}
                  </span>
                </div>
                <p class="plugin-desc">
                  {{ detail.plugin.desc || '--' }}
                </p>
              </div>
            </div>
            <div class="hero-stats">
              <div class="stats-row">
                <div class="stats-item">
                  <p class="stats-label">
                    {{ $t('当前引用流程') }}
                  </p>
                  <p class="stats-value">
                    {{ detail.refs.flowCount }}
                  </p>
                </div>
                <div class="stats-item">
                  <p class="stats-label">
                    {{ $t('线上版引用') }}
                  </p>
                  <p class="stats-value">
                    {{ detail.refs.versionCount }}
                  </p>
                </div>
                <div class="stats-item">
                  <p class="stats-label">
                    {{ $t('仅草稿引用') }}
                  </p>
                  <p class="stats-value">
                    {{ detail.refs.draftOnlyCount }}
                  </p>
                </div>
              </div>
              <p class="stats-tips">
                <bk-icon type="info-circle" />
                {{ $t('按流程去重；仅统计线上版和草稿，不累计历史版本') }}
              </p>
            </div>
          </div>
          <div class="detail-tabbar">
            <div
              v-for="item in tabs"
              :key="item.value"
              :class="['tabbar-item', { 'is-active': activeTab === item.value }]"
              @click="handleTabChange(item.value)">
              <i :class="item.icon" />
              <span class="tabbar-label">{{ item.label }}</span>
            </div>
          </div>
        </div>

        <!-- 基本信息 -->
        <div
          v-if="activeTab === 'basic'"
          class="detail-panel basic-panel">
          <div class="info-row">
            <span class="info-label">{{ $t('插件类型：') }}</span>
            <span class="info-value">{{ typeText }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('插件来源：') }}</span>
            <span class="info-value">{{ sourceText }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('所属分类：') }}</span>
            <span class="info-value with-icon">
              {{ categoryText }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('插件身份：') }}</span>
            <span class="info-value">{{ detail.plugin.identity || detail.plugin.code || '--' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('最近更新人：') }}</span>
            <span class="info-value">{{ detail.plugin.updatedBy || '--' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('最近更新时间：') }}</span>
            <span class="info-value">{{ detail.plugin.updateTime || '--' }}</span>
          </div>
        </div>

        <!-- 当前引用 -->
        <div
          v-else
          class="detail-panel reference-panel">
          <bk-alert
            class="reference-alert"
            type="info">
            <template slot="title">
              {{ $t('下架后，现有流程的编辑和执行不受空间下架状态影响。') }}
            </template>
          </bk-alert>
          <div class="reference-toolbar">
            <div class="scope-segmented">
              <div
                v-for="item in scopeOptions"
                :key="item.value"
                :class="['segment-item', { 'is-active': scope === item.value }]"
                @click="scope = item.value">
                {{ item.label }}
              </div>
            </div>
            <bk-input
              v-model="keyword"
              class="reference-search"
              :placeholder="$t('搜索流程名称、维护人')"
              :clearable="true"
              right-icon="bk-icon icon-search"
              @enter="handleSearch"
              @right-icon-click="handleSearch" />
            <bk-button
              class="export-btn"
              @click="handleExportCsv">
              <i class="bk-icon icon-download" />
              {{ $t('导出 CSV') }}
            </bk-button>
          </div>

          <bk-table
            :data="references"
            :size="'small'"
            row-key="id"
            :pagination="referencePagination"
            ext-cls="reference-table"
            @page-change="handlePageChange"
            @page-limit-change="handlePageLimitChange">
            <bk-table-column
              :label="$t('流程')"
              prop="flowName"
              width="200"
              show-overflow-tooltip />
            <bk-table-column
              :label="$t('线上版')"
              width="200">
              <template slot-scope="{ row }">
                <bk-popover
                  v-if="row.publishedNodes > 0"
                  placement="top"
                  theme="light"
                  ext-cls="reference-node-popover">
                  <div class="version-cell">
                    <div class="version-count">
                      <span class="node-count">{{ row.publishedNodes }}</span>
                      {{ $t('个节点') }}
                    </div>
                    <div class="version-no">
                      {{ row.publishedVersion }}
                    </div>
                  </div>
                  <div
                    slot="content"
                    class="node-popover">
                    <p class="popover-title">
                      {{ $t('线上版') }} · {{ $t('引用节点') }}
                    </p>
                    <ul class="popover-node-list">
                      <li
                        v-for="(name, index) in publishedNodeNames(row)"
                        :key="`pop-p-${index}`">
                        {{ name }}
                      </li>
                    </ul>
                    <div
                      class="popover-link"
                      @click="$emit('viewFlow', { row, type: 'published' })">
                      {{ $t('查看流程') }}
                      <i class="common-icon-jump-link" />
                    </div>
                  </div>
                </bk-popover>
                <span
                  v-else
                  class="empty-text">{{ $t('尚未发布') }}</span>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('当前草稿')"
              width="130">
              <template slot-scope="{ row }">
                <bk-popover
                  v-if="row.draftNodes > 0"
                  placement="bottom"
                  theme="light"
                  ext-cls="reference-node-popover">
                  <div class="version-cell">
                    <p class="version-count">
                      <span class="node-count">{{ row.draftNodes }}</span>
                      {{ $t('个节点') }}
                    </p>
                  </div>
                  <div
                    slot="content"
                    class="node-popover">
                    <p class="popover-title">
                      {{ $t('草稿') }} · {{ $t('引用节点') }}
                    </p>
                    <ul class="popover-node-list">
                      <li
                        v-for="(name, index) in draftNodeNames(row)"
                        :key="`pop-d-${index}`">
                        {{ name }}
                      </li>
                    </ul>
                    <div
                      class="popover-link"
                      @click="$emit('viewFlow', { row, type: 'draft' })">
                      {{ $t('编辑草稿') }}
                      <i class="common-icon-jump-link" />
                    </div>
                  </div>
                </bk-popover>
                <span
                  v-else
                  class="empty-text">{{ $t('未引用') }}</span>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('维护人')"
              prop="maintainer"
              width="120"
              show-overflow-tooltip />
            <bk-table-column
              :label="$t('操作')"
              width="100">
              <template>
                <bk-button
                  text
                  theme="primary"
                  ext-cls="expand-btn">
                  {{ $t('查看流程') }}
                </bk-button>
              </template>
            </bk-table-column>
          </bk-table>
        </div>
      </template>
    </div>
  </bk-sideslider>
</template>

<script>
import {
  getStatusMap,
  getTypeText,
  getSourceText,
  getCategoryPath,
} from './shared';
import {
  getPluginDetail,
  getPluginReferences,
  getPluginSummary,
} from './api';

export default {
  name: 'PluginDetailSlider',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    plugin: {
      type: Object,
      default: () => null,
    },
    spaceId: {
      type: [String, Number],
      default: '',
    },
    categoryTree: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      loading: false,
      detail: null,
      activeTab: 'basic',
      references: [],
      scope: 'all',
      keyword: '',
      referencePagination: {
        current: 1,
        count: 0,
        limit: 10,
      },
      expandedRowId: null,
    };
  },
  computed: {
    tabs() {
      return [
        { value: 'basic', label: this.$t('基本信息'), icon: 'commonicon-icon common-icon-overview-table' },
        { value: 'reference', label: this.$t('当前引用'), icon: 'bk-icon common-icon-link-guanlian' },
        // { value: 'history', label: this.$t('历史引用'), icon: 'commonicon-icon common-icon-clock-reload' },
      ];
    },
    scopeOptions() {
      return [
        { value: 'all', label: this.$t('全部引用范围') },
        { value: 'published', label: this.$t('线上版') },
        { value: 'draft', label: this.$t('草稿') },
      ];
    },
    statusInfo() {
      const status = this.detail ? this.detail.plugin.status : '';
      return getStatusMap(key => this.$t(key))[status] || { label: '--', icon: '' };
    },
    logoText() {
      const name = this.detail ? this.detail.plugin.name : '';
      return name ? name.charAt(0) : '';
    },
    typeText() {
      return this.detail ? getTypeText(this.detail.plugin.type, key => this.$t(key)) : '--';
    },
    sourceText() {
      return this.detail ? getSourceText(this.detail.plugin.source, key => this.$t(key)) : '--';
    },
    categoryText() {
      if (!this.detail) return '--';
      return getCategoryPath(this.flatCategories, this.detail.plugin.category);
    },
    flatCategories() {
      return this.detail && this.detail.categories ? this.detail.categories : this.categoryTree;
    },
    expandedRowKeys() {
      return this.expandedRowId ? [this.expandedRowId] : [];
    },
    expandedRow() {
      if (!this.expandedRowId) return null;
      return this.references.find(item => item.id === this.expandedRowId) || null;
    },
  },
  watch: {
    visible(val) {
      if (val) {
        this.initPanel();
      }
    },
    // 切入「当前引用」Tab 时主动加载引用列表，避免首次进入时表格为空
    activeTab(val) {
      if (val === 'reference') {
        this.fetchReferences();
      }
    },
    scope() {
      this.resetAndFetchReferences();
    },
    keyword(val) {
      if (!val) this.resetAndFetchReferences();
    },
  },
  methods: {
    isExpanded(row) {
      return this.expandedRowId === row.id;
    },
    handleVisibleChange(val) {
      this.$emit('update:visible', val);
    },
    handleTabChange(value) {
      this.activeTab = value;
    },
    handleSearch() {
      this.resetAndFetchReferences();
    },
    async initPanel() {
      this.activeTab = 'basic';
      this.scope = 'all';
      this.keyword = '';
      this.expandedRowId = null;
      this.references = [];
      this.referencePagination.current = 1;
      this.referencePagination.count = 0;
      await this.fetchDetail();
    },
    async fetchDetail() {
      if (!this.plugin) return;
      this.loading = true;
      try {
        const detail = await getPluginDetail({ spaceId: this.spaceId, plugin: this.plugin });
        if (!detail.categories) {
          detail.categories = await this.fetchCategories();
        }
        this.detail = detail;
      } finally {
        this.loading = false;
      }
    },
    async fetchCategories() {
      try {
        const { categories } = await getPluginSummary({ spaceId: this.spaceId });
        return categories || [];
      } catch (e) {
        return [];
      }
    },
    async fetchReferences() {
      if (!this.plugin) return;
      this.loading = true;
      try {
        const { count, results } = await getPluginReferences({
          spaceId: this.spaceId,
          pluginId: this.plugin.id,
          scope: this.scope,
          keyword: this.keyword.trim(),
          page: this.referencePagination.current,
          page_size: this.referencePagination.limit,
        });
        this.references = results;
        this.referencePagination.count = count;
      } finally {
        this.loading = false;
      }
    },
    resetAndFetchReferences() {
      this.expandedRowId = null;
      this.referencePagination.current = 1;
      this.fetchReferences();
    },
    handlePageChange(page) {
      this.referencePagination.current = page;
      this.expandedRowId = null;
      this.fetchReferences();
    },
    handlePageLimitChange(limit) {
      this.referencePagination.limit = limit;
      this.referencePagination.current = 1;
      this.expandedRowId = null;
      this.fetchReferences();
    },
    fallbackNodeNames(count) {
      return Array.from({ length: count || 0 }, (item, index) => this.$t('节点 {index}', { index: index + 1 }));
    },
    publishedNodeNames(row) {
      return (row.publishedNodeNames && row.publishedNodeNames.length)
        ? row.publishedNodeNames
        : this.fallbackNodeNames(row.publishedNodes);
    },
    draftNodeNames(row) {
      return (row.draftNodeNames && row.draftNodeNames.length)
        ? row.draftNodeNames
        : this.fallbackNodeNames(row.draftNodes);
    },
    handleExportCsv() {
      const header = [
        this.$t('流程'),
        this.$t('线上版'),
        this.$t('当前草稿'),
        this.$t('维护人'),
      ];
      const rows = this.references.map(row => [
        row.flowName,
        row.publishedNodes > 0 ? `${row.publishedNodes} ${this.$t('个节点')} ${row.publishedVersion}` : this.$t('尚未发布'),
        row.draftNodes > 0 ? `${row.draftNodes} ${this.$t('个节点')}` : (row.draftNodes === 0 ? this.$t('未引用') : this.$t('无草稿')),
        row.maintainer,
      ]);
      const csv = [header, ...rows]
        .map(cols => cols.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\n');
      const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${this.plugin ? this.plugin.name : 'plugin'}-${this.$t('当前引用')}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    },
  },
};
</script>

<style lang="scss" scoped>
.plugin-detail-slider {
    .detail-header {
        display: flex;
        align-items: center;
        height: 100%;

        .header-title {
            font-size: 16px;
            line-height: 24px;
            color: #313238;
        }
    }

    .detail-content {
        height: 100%;
        overflow-y: auto;
    }
    .detail-hero {
        padding: 16px 40px 0;
        background: #f2f6fc;

        .hero-row {
            display: flex;
            align-items: flex-start;
            gap: 16px;
            position: relative;
        }

        .hero-message {
            display: flex;
            flex: 1;
            gap: 12px;
            min-width: 0;
        }

        .plugin-logo {
            display: flex;
            flex-shrink: 0;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            background: linear-gradient(135deg, #3a84ff 0%, #3269fe 100%);
            box-shadow: 0 10px 15px rgba(21, 75, 252, 0.2);
            font-family: "PingFang SC";
            font-size: 20px;
            font-weight: 600;
            line-height: 28px;
            color: #fff;
        }

        .hero-title {
            display: flex;
            flex: 1;
            flex-direction: column;
            gap: 2px;
            min-width: 0;

            .title-line {
                display: flex;
                align-items: center;
                gap: 8px;
                min-width: 0;
            }

            .plugin-name {
                font-size: 16px;
                font-weight: 700;
                line-height: 24px;
                color: #111214;
            }

            .plugin-desc {
                font-size: 12px;
                line-height: 20px;
                color: #8f9fbd;
                word-break: break-word;
            }
        }

        .status-tag {
            flex-shrink: 0;
            padding: 0 6px;
            border-radius: 8px;
            font-size: 10px;
            line-height: 16px;

            &.is-visible {
                color: #1D8F70;
                background: #E1F5F0;
            }

            &.is-review {
                color: #ff9c01;
                background: #fdf4e8;
            }

            &.is-hidden {
                color: #63656e;
                background: #f0f1f5;
            }

            &.is-offline {
                color: #ea3636;
                background: #ffecec;
            }

            &.is-invalid {
                color: #979ba5;
                background: #f0f1f5;
            }
        }

        .hero-stats {
            flex-shrink: 0;
            width: 380px;
            padding: 8px 8px 4px;
            border: 1px solid #e4e9f2;
            border-radius: 6px;
            background: #fff;
            position: absolute;
            top: 0;
            right: 0;
            .stats-row {
                display: flex;
                align-items: center;
            }

            .stats-item {
                flex: 1;
                min-width: 0;
                padding: 0 12px;

                & + .stats-item {
                    border-left: 1px solid #e4e9f2;
                }
            }

            .stats-label {
                font-size: 12px;
                line-height: 20px;
                color: #4e5e7a;
            }

            .stats-value {
                font-family: Arial;
                font-size: 20px;
                font-weight: 700;
                line-height: 28px;
                color: #313238;
            }

            .stats-tips {
                display: flex;
                align-items: center;
                gap: 3px;
                padding-left: 12px;
                font-size: 12px;
                line-height: 20px;
                color: #8f9fbd;

                .bk-icon {
                    font-size: 14px !important;
                }
            }
        }

        .detail-tabbar {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-top: 16px;
        }

        .tabbar-item {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 10px 24px;
            border-radius: 8px 8px 0 0;
            background: #e4e9f2;
            cursor: pointer;

            .bk-icon {
                font-size: 16px;
                color: #4e5e7a;
            }

            .tabbar-label {
                font-family: "PingFang SC";
                font-size: 14px;
                font-weight: 500;
                line-height: 22px;
                color: #4e5e7a;
            }

            &.is-active {
                background: #fff;
                box-shadow: 0 1px 2px rgba(25, 25, 41, 0.02);
                color: #3A84FF;
                .tabbar-label {
                    color: #3A84FF !important;
                }
            }
        }
    }

    .detail-panel {
        padding: 16px 40px;
    }

    .basic-panel {
        display: flex;
        flex-direction: column;
        gap: 12px;

        .info-row {
            display: flex;
            align-items: center;
            font-size: 12px;
            line-height: 20px;
        }

        .info-label {
            flex-shrink: 0;
            color: #8f9fbd;
        }

        .info-value {
            color: #4d4f56;

            &.with-icon {
                display: flex;
                align-items: center;
                gap: 4px;

                .commonicon-icon {
                    padding: 2px;
                    border-radius: 4px;
                    background: #f0f4fa;
                    font-size: 12px;
                }
            }
        }
    }

    .reference-panel {
        display: flex;
        flex-direction: column;
        gap: 12px;

        ::v-deep .reference-alert {
            border-color: #a3c5fd;
            background-color: #f0f5ff;

            .bk-alert-wraper {
                padding: 6px 8px;
                display: flex;
                align-items: center;
            }

            .bk-alert-title {
                font-size: 12px;
                line-height: 20px;
                color: #4d4f56;
            }
        }

        .reference-toolbar {
            display: flex;
            align-items: center;
            gap: 12px;

            .scope-segmented {
                display: flex;
                align-items: center;
                padding: 2px;
                background: #f0f1f5;
                border-radius: 4px;

                .segment-item {
                    position: relative;
                    display: flex;
                    align-items: center;
                    height: 28px;
                    padding: 0 12px;
                    font-size: 12px;
                    color: #63656e;
                    border-radius: 3px;
                    cursor: pointer;
                    user-select: none;
                    white-space: nowrap;
                    transition: color .15s ease, background-color .15s ease;

                    &:not(.is-active) + .segment-item:not(.is-active)::before {
                        content: '';
                        position: absolute;
                        top: 50%;
                        left: 0;
                        width: 1px;
                        height: 14px;
                        background: #dcdee5;
                        transform: translateY(-50%);
                    }

                    &.is-active {
                        font-weight: 500;
                        color: #3a84ff;
                        background: #fff;
                        box-shadow: 0 0 0 1px #dcdee5;
                    }
                }
            }

            .reference-search {
                flex: 1;
                border-radius: 6px;
                ::v-deep .bk-form-input {
                    border: 1px solid #c1cde5;
                    border-radius: 6px;
                    &:focus {
                        border-color: #3a84ff;
                    }
                }
            }

            .export-btn {
                display: flex;
                align-items: center;
                border-radius: 6px;
                border: 1px solid #C1CDE5;

                .bk-icon {
                    margin-right: 6px;
                    font-size: 14px;
                    line-height: 30px;
                    top: -1px;
                    color: #4D4F56;
                }
            }
        }

        ::v-deep .reference-table {
            .bk-table-header-label {
                color: #313238;
                font-weight: 500;
                font-family: "PingFang SC";
            }

            .bk-table-expanded-cell {
                padding: 0;
            }

            .bk-table-body .bk-table-row {
                cursor: pointer;
                color: #4E5E7A;
            }
            .expand-btn {
                pointer-events: none;
            }
            .bk-table-column-expand {
                width: 0 !important;
                padding: 0 !important;
                border: none !important;

                .bk-table-expand-icon {
                    display: none;
                }
            }
            .version-cell {
                display: flex;
                gap: 4px;
                line-height: 20px;
                color: #4E5E7A;
                font-family: "Noto Sans SC";
                font-size: 12px;
                align-items: center;

                .node-count {
                    font-weight: 700 !important;
                    color: #3974FF;
                }
                .version-no {
                    font-size: 12px;
                    color: #8F9FBD;
                    display: flex;
                    height: 16px;
                    padding: 0 6px;
                    border-radius: 4px;
                    align-items: center;
                    align-content: center;
                    background: #F0F4FA;
                    gap: 0 4px;
                }
            }

            .empty-text {
                color: #8F9FBD !important;
            }

            .bk-table-body .bk-table-row:last-child td {
                border-bottom: none;
            }
            .expand-btn {
                .bk-icon {
                    font-size: 16px !important;
                }
            }
        }
        .expand-cell {
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 12px 24px;
            background: #f5f7fa;
        }

        .expand-row {
            display: flex;
            align-items: center;
            gap: 8px;
            min-height: 44px;
            padding: 8px 88px 10px 8px;
            border-radius: 4px;
            background: #fff;

            .expand-label {
                flex-shrink: 0;
                width: 180px;
                font-family: "PingFang SC";
                font-size: 12px;
                font-weight: 500;
                line-height: 20px;
                color: #303338;
            }

            .expand-nodes {
                display: flex;
                flex: 1;
                align-items: center;
                flex-wrap: wrap;
                gap: 2px;
                min-width: 0;
                font-size: 12px;
                line-height: 20px;
                color: #4d4f56;

                .expand-nodes-label {
                    flex-shrink: 0;
                    font-family: "PingFang SC";
                    font-weight: 500;
                }

                .node-tag {
                    padding: 1px 8px;
                    border-radius: 2px;
                    background: #f0f1f5;
                    word-break: break-word;
                }

                .empty-text {
                    color: #979ba5;
                }
            }

            .expand-link {
                flex-shrink: 0;
                font-family: "PingFang SC";
                font-size: 12px;
                line-height: 20px;
                color: #3a84ff;
                cursor: pointer;
            }
        }
    }
}
</style>

<style lang="scss">
.reference-node-popover {
    width: 278px;
    .node-popover {
        .popover-title {
            margin: 0 0 8px;
            font-size: 14px;
            font-weight: 500;
            line-height: 22px;
            color: #111214;
            font-family: "PingFang SC";
        }

        .popover-node-list {
            font-family: "PingFang SC";
            margin-left: 20px;
            font-size: 12px;
            line-height: 20px;
            color: #4e5e7a;
            li {
                list-style: disc;
            }
        }

        .popover-link {
            display: flex;
            align-items: center;
            gap: 4px;
            margin-top: 8px;
            font-size: 12px;
            line-height: 20px;
            font-family: "PingFang SC";
            color: #3974ff;
            cursor: pointer;
            .common-icon-jump-link {
                font-size: 14px;
            }
        }
    }
}
</style>
