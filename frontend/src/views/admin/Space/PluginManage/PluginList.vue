<template>
  <div class="plugin-list">
    <div
      v-if="isRecommend"
      class="recommend-header">
      <div class="recommend-title">
        <i class="bk-icon icon-star" />
        <span>{{ $t('空间推荐') }}</span>
      </div>
      <span class="recommend-divider" />
      <span class="recommend-count">
        {{ $t('已推荐') }}
        <span>{{ pluginList.length }} / {{ maxRecommend }}</span>
      </span>
    </div>
    <div
      v-else
      class="list-title">
      <i
        v-if="categoryIcon"
        :class="['list-title-icon', categoryIcon]" />
      <span>{{ categoryTitle }}</span>
    </div>
    <bk-search-select
      class="plugin-search-select"
      :data="searchData"
      :values="searchValues"
      :show-condition="false"
      clearable
      :popover-zindex="2300"
      :placeholder="$t('搜索 插件名称、类型、来源、目录、最近修改人')"
      @change="handleSearchChange" />
    <div
      v-if="!isRecommend"
      class="status-tabs">
      <template v-for="(tab, index) in statusTabs">
        <div
          v-if="tab.divider"
          :key="`divider-${index}`"
          class="tab-divider" />
        <div
          v-else
          :key="tab.value"
          :class="['status-tab', { 'is-active': activeTab === tab.value }]"
          @click="handleTabChange(tab.value)">
          <i :class="['tab-icon', tab.icon]" />
          <span class="tab-label">{{ tab.label }}</span>
          <span :class="['tab-count', tab.badgeClass]">{{ tab.count }}</span>
        </div>
      </template>
    </div>

    <bk-alert
      v-if="isReviewTab"
      class="legacy-alert review-alert"
      type="warning">
      <template slot="title">
        <ul class="review-alert-tips">
          <li>
            {{ $t('当前新插件策略为「{mode}」，如需调整，请前往', { mode: strategyModeText }) }}
            <span
              class="strategy-link"
              @click="$emit('openStrategy')">{{ $t('新插件策略') }}</span>
          </li>
          <li>
            {{ $t('通过之前，请确认「目标目录」，默认是「未分类」，可手动「修改目标目录」') }}
          </li>
        </ul>
      </template>
    </bk-alert>

    <div
      v-if="hasSelection"
      class="list-toolbar">
      <div class="toolbar-left">
        <template v-if="isReviewTab">
          <bk-popconfirm
            trigger="click"
            placement="bottom-start"
            width="320"
            ext-cls="review-popconfirm"
            :disabled="!selection.length"
            :confirm-text="$t('启用')"
            :cancel-text="$t('取消')"
            @confirm="handleBatchReviewPass">
            <template slot="content">
              <div class="clean-pop-main">
                <span class="clean-pop-icon is-info">
                  <i class="bk-icon icon-info-circle-shape" />
                </span>
                <div class="clean-pop-texts">
                  <p class="clean-pop-title">
                    {{ $t('确定批量启用插件？') }}
                  </p>
                  <p class="clean-pop-name">
                    {{ $t('插件状态') }}：<span>{{ reviewSelectedNames }}</span>
                  </p>
                  <p class="clean-pop-desc">
                    {{ $t('启用后，将自动绑定到对应分类并设为启用') }}
                  </p>
                </div>
              </div>
            </template>
            <bk-button
              theme="primary"
              :disabled="!selection.length">
              {{ $t('批量启用') }}
            </bk-button>
          </bk-popconfirm>
          <bk-button
            :disabled="!selection.length"
            @click="handleBatchStatus('not_enable')">
            {{ $t('批量不启用') }}
          </bk-button>
          <bk-popover
            v-if="selection.length"
            ref="batchMovePopover"
            trigger="click"
            placement="bottom-start"
            theme="light"
            ext-cls="category-select-popover"
            :width="280"
            :arrow="false"
            :transfer="true">
            <bk-button
              icon-right="icon-angle-down">
              {{ $t('修改目标目录') }}
            </bk-button>
            <template slot="content">
              <category-select-panel
                :category-tree="categoryTree"
                :ai-recommend-ids="batchAiRecommendIds"
                :ai-recommend-loading="aiRecommendLoading"
                @select="handleBatchMoveCategory" />
            </template>
          </bk-popover>
          <bk-button
            v-else
            disabled
            icon-right="icon-angle-down">
            {{ $t('修改目标目录') }}
          </bk-button>
        </template>
        <template v-else-if="isAvailableTab">
          <bk-popover
            ref="batchMovePopover"
            trigger="click"
            placement="bottom-start"
            theme="light"
            ext-cls="category-select-popover"
            :width="280"
            :arrow="false"
            :transfer="true">
            <bk-button
              icon-right="icon-angle-down"
              :disabled="!selection.length"
              :theme="'primary'">
              {{ $t('批量移动') }}
            </bk-button>
            <template slot="content">
              <category-select-panel
                :category-tree="categoryTree"
                :ai-recommend-ids="batchAiRecommendIds"
                :ai-recommend-loading="aiRecommendLoading"
                @select="handleBatchMoveCategory" />
            </template>
          </bk-popover>
        </template>
        <template v-else-if="isUnusedTab">
          <bk-popconfirm
            trigger="click"
            placement="bottom-start"
            width="330"
            ext-cls="review-popconfirm"
            :disabled="!selection.length"
            :confirm-text="$t('启用')"
            :cancel-text="$t('取消')"
            @confirm="handleBatchReviewPass">
            <template slot="content">
              <div class="clean-pop-main">
                <span class="clean-pop-icon is-info">
                  <i class="bk-icon icon-info-circle-shape" />
                </span>
                <div class="clean-pop-texts">
                  <p class="clean-pop-title">
                    {{ $t('确定批量启用插件？') }}
                  </p>
                  <p class="clean-pop-name">
                    {{ $t('插件状态') }}：<span>{{ reviewSelectedNames }}</span>
                  </p>
                  <p class="clean-pop-desc">
                    {{ $t('启用后，将自动绑定到对应分类并设为启用') }}
                  </p>
                </div>
              </div>
            </template>
            <bk-button
              theme="primary"
              :disabled="!selection.length">
              {{ $t('批量启用') }}
            </bk-button>
          </bk-popconfirm>
        </template>
      </div>
    </div>

    <bk-table
      ref="pluginTable"
      v-bkloading="{ isLoading: loading || submitting, immediate: true }"
      :data="pluginList"
      :size="'small'"
      :pagination="pagination"
      :ext-cls="isRecommend ? 'plugin-list-table recommend-table' : 'plugin-list-table'"
      :max-height="tableMaxHeight"
      @selection-change="handleSelectionChange"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange">
      <bk-table-column
        v-if="!isRecommend && hasSelection"
        type="selection"
        :selectable="selectionSelectable"
        width="42" />
      <bk-table-column
        v-for="col in tableColumns"
        :key="col.id"
        :label="col.label"
        :prop="col.id"
        :width="col.width"
        :min-width="col.minWidth"
        :sortable="col.sortable"
        :filters="col.filters"
        :filter-method="col.filterMethod"
        :filter-multiple="false"
        :render-header="col.renderHeader"
        show-overflow-tooltip>
        <template slot-scope="{ row }">
          <div
            v-if="col.id === 'name'"
            class="plugin-name-cell">
            <span
              v-if="isRecommend || row.recommended"
              class="plugin-tag is-recommend">{{ $t('推荐') }}</span>
            <span
              class="plugin-name"
              @click="handleNameClick(row)">{{ row.plugin_name }}</span>
          </div>
          <span v-else-if="col.id === 'type'">{{ row.plugin_type_name || typeText(row.plugin_type) }}</span>
          <span v-else-if="col.id === 'source'">{{ row.source_name || sourceText(row.source_key) }}</span>
          <div
            v-else-if="col.id === 'category'"
            class="category-cell">
            <bk-popover
              :ref="`categoryPop-${row.id}`"
              trigger="click"
              placement="bottom-start"
              theme="light"
              ext-cls="category-select-popover"
              :width="280"
              :arrow="false"
              :transfer="true"
              @show="activeCategoryPopId = row.id; quickAiRecommendRowId = ''; quickAiRecommendIds = []"
              @hide="activeCategoryPopId === row.id && (activeCategoryPopId = '')">
              <div
                :class="['category-chip', { 'is-active': activeCategoryPopId === row.id }]">
                <span>{{ categoryPath(row.directory_id) }}</span>
              </div>
              <template slot="content">
                <category-select-panel
                  :category-tree="categoryTree"
                  :active-id="row.directory_id"
                  :follow-source="!row.directory_id"
                  :ai-recommend-ids="row.id === quickAiRecommendRowId ? quickAiRecommendIds : []"
                  :ai-recommend-loading="aiRecommendLoading"
                  @select="payload => handleQuickCategorySelect(row, payload)" />
              </template>
            </bk-popover>
          </div>
          <!-- 状态 -->
          <span
            v-else-if="col.id === 'status'"
            :class="['status-badge', `is-${statusGroup(row.status)}`]">
            <i :class="['bk-icon', (statusMap[statusGroup(row.status)] || {}).icon]" />
            {{ (statusMap[statusGroup(row.status)] || {}).label }}
          </span>
          <!-- 引用流程数 -->
          <span
            v-else-if="col.id === 'ref_count'"
            class="ref-count">
            {{ row.ref_count }}
          </span>
          <span v-else>{{ row[col.id] || "--" }}</span>
        </template>
      </bk-table-column>
      <!-- 空间推荐：取消推荐 + 更多（编辑 / 状态变更 / 停用配置） -->
      <bk-table-column
        v-if="isRecommend"
        :label="$t('操作')"
        width="150"
        fixed="right">
        <template slot-scope="{ row }">
          <div class="operate-column">
            <bk-button
              text
              theme="primary"
              @click="handleCancelRecommend(row)">
              {{ $t('取消推荐') }}
            </bk-button>
            <bk-popover
              :ref="`rowMore-${row.id}`"
              theme="light"
              placement="bottom-start"
              :width="84"
              :distance="4"
              :arrow="false">
              <i class="bk-icon icon-more row-more-icon" />
              <template slot="content">
                <ul class="dropdown-list">
                  <li
                    v-for="action in rowActions(row)"
                    :key="`${action.type}-${action.status || ''}`"
                    class="dropdown-item"
                    @click="handleRowAction(row, action)">
                    {{ action.label }}
                  </li>
                </ul>
              </template>
            </bk-popover>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        v-else
        :label="$t('操作')"
        :width="isReviewTab ? 110 : 150"
        fixed="right">
        <template slot-scope="{ row }">
          <div class="operate-column">
            <!-- 可用：编辑 / 停用 -->
            <template v-if="isAvailableTab">
              <bk-button
                text
                theme="primary"
                @click="openEditDialog(row)">
                {{ $t('编辑') }}
              </bk-button>
              <bk-button
                text
                theme="primary"
                @click="openDisabledDialog(row)">
                {{ $t('停用') }}
              </bk-button>
            </template>
            <template v-else-if="isReviewTab || isUnusedTab">
              <bk-popconfirm
                v-if="isReviewTab || row.status === 'disabled'"
                trigger="click"
                placement="bottom"
                width="360"
                ext-cls="review-pass-popconfirm"
                :confirm-text="$t('确定')"
                :cancel-text="$t('取消')"
                :tippy-options="passTippyOptions"
                @show="handlePassClick(row)"
                @confirm="handleReviewPassConfirm(row)">
                <template slot="content">
                  <div class="review-pass-pop">
                    <p class="pop-title">
                      {{ $t('启用') }}
                    </p>
                    <div class="pop-label">
                      <span>{{ $t('启用至目录') }}</span>
                      <span class="required">*</span>
                    </div>
                    <bk-popover
                      ref="passCategoryPopover"
                      trigger="click"
                      placement="bottom-start"
                      theme="light"
                      ext-cls="pass-category-popover"
                      :width="315"
                      :arrow="false"
                      :transfer="true"
                      :tippy-options="{ zIndex: 10002 }"
                      @show="activePassCategoryPop = true"
                      @hide="activePassCategoryPop = false">
                      <div :class="['pass-category-select', { 'is-active': activePassCategoryPop }]">
                        <span>{{ passCategoryLabel || $t('未分类') }}</span>
                        <i class="bk-icon icon-angle-down" />
                      </div>
                      <template slot="content">
                        <category-select-panel
                          :category-tree="categoryTree"
                          :active-id="passCategory"
                          :ai-recommend-ids="passAiRecommendIds"
                          :ai-recommend-loading="aiRecommendLoading"
                          @select="handlePassCategorySelect" />
                      </template>
                    </bk-popover>
                  </div>
                </template>
                <bk-button
                  text
                  theme="primary"
                  @click="handlePassClick(row)">
                  {{ $t('启用') }}
                </bk-button>
              </bk-popconfirm>
              <!-- 待审核：不启用；未启用：停用配置 -->
              <bk-button
                v-if="isReviewTab"
                text
                theme="primary"
                @click="handleRowStatus(row, 'disabled')">
                {{ $t('不启用') }}
              </bk-button>
              <bk-button
                v-else-if="row.status === 'disabled'"
                text
                theme="primary"
                @click="openDisabledConfigDialog(row)">
                {{ $t('停用配置') }}
              </bk-button>
            </template>
          </div>
        </template>
      </bk-table-column>
      <div
        slot="empty"
        class="empty-data">
        <span class="empty-text">{{ isRecommend ? $t('暂无推荐插件') : $t('暂无插件') }}</span>
      </div>
    </bk-table>

    <!-- 插件详情侧滑（点击插件名打开） -->
    <plugin-detail-slider
      :visible.sync="isDetailSliderShow"
      :plugin="detailPlugin"
      :space-id="spaceId"
      :category-tree="categoryTree"
      @viewFlow="handleDetailViewFlow" />

    <!-- 停用确认弹窗 -->
    <bk-dialog
      v-model="disabledDialogVisible"
      ext-cls="disabled-confirm-dialog"
      :width="640"
      header-position="left">
      <template slot="header">
        <div class="disabled-dialog-header">
          {{ $t('确认停用 「{name}」插件？', { name: disabledRow ? disabledRow.plugin_name : '' }) }}
        </div>
      </template>
      <div
        v-if="disabledRow"
        class="disabled-dialog-body">
        <!-- 停用说明 -->
        <div class="disabled-alert">
          <bk-icon type="exclamation-circle" />
          <div class="alert-content">
            <p class="alert-title">
              {{ $t('停用只禁止新增使用：') }}
            </p>
            <ul>
              <li>{{ $t('已有流程中的') }} <b>{{ disabledRow.node_count || 0 }}</b> {{ $t('个节点照常编辑、执行，画布上标记「已停用」；') }}</li>
              <li>{{ $t('在已有流程里新增该插件的节点将无法保存，新建、复制、导入流程不受限制。') }}</li>
            </ul>
          </div>
        </div>
        <!-- 停用原因 -->
        <div class="form-item">
          <div class="form-label">
            {{ $t('停用原因（选填）') }}
          </div>
          <bk-input
            v-model="disabledForm.disable_reason"
            type="textarea"
            :rows="3"
            :maxlength="200"
            :show-word-limit="true"
            :placeholder="$t('请输入')" />
        </div>
        <!-- 替换插件 -->
        <div class="form-item">
          <div class="form-label">
            {{ $t('替换插件（选填）') }}
          </div>
          <bk-cascade
            v-model="replacePluginPath"
            class="replace-cascade"
            ext-popover-cls="disabled-cascade-popover"
            :list="disabledCascadeList"
            :clearable="true"
            :placeholder="$t('请选择')">
            <template
              slot="option"
              slot-scope="{ node }">
              <i
                v-if="node.divider"
                class="cascade-cate-divider" />
              <i
                v-if="node.icon"
                :class="['cascade-cate-icon', node.icon]" />
              <span class="cascade-cate-name">{{ node.name }}</span>
            </template>
          </bk-cascade>
        </div>
        <p class="dialog-tips">
          {{ $t('原因与替换插件会显示在画布节点提示与保存拦截提示中。') }}
          <br>
          {{ $t('不填原因时，画布/拦截统一显示「该插件已被空间管理员停用」。') }}
        </p>
      </div>
      <template slot="footer">
        <bk-button
          theme="danger"
          :outline="true"
          @click="handleDisabledConfirm">
          {{ $t('确认停用') }}
        </bk-button>
        <bk-button
          theme="default"
          @click="handleDisabledCancel">
          {{ $t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>

    <bk-dialog
      v-model="editDialogVisible"
      :width="640"
      :transfer="true"
      render-directive="if"
      header-position="left"
      ext-cls="plugin-edit-dialog"
      :title="editDialogTitle">
      <div
        v-if="editingPlugin"
        class="plugin-edit-content">
        <section class="plugin-info">
          <div class="info-main">
            <div class="plugin-logo">
              {{ editingLogoText }}
            </div>
            <div class="info-basic">
              <div class="info-name-row">
                <span
                  v-bk-overflow-tips
                  class="info-name">{{ editingPlugin.plugin_name }}</span>
                <span
                  v-if="editingPlugin.recommended"
                  class="recommend-tag">推荐</span>
                <span :class="['status-badge', `is-${editingPlugin.status}`]">
                  <bk-icon
                    v-if="['expired', 'not_enable', 'disabled'].includes(editingPlugin.status)"
                    type="exclamation-triangle-shape" />
                  {{ editingStatusInfo.label }}</span>
              </div>
              <p class="info-desc">
                {{ editingPlugin.plugin_desc || '--' }}
              </p>
            </div>
          </div>
          <div class="info-meta">
            <div class="meta-item">
              <span class="meta-label">{{ $t('插件类型：') }}</span>
              <span
                v-bk-overflow-tips
                class="meta-value">{{ editingTypeText }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">{{ $t('来源分类：') }}</span>
              <span
                v-bk-overflow-tips
                class="meta-value">{{ editingSourceText }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">{{ $t('插件身份：') }}</span>
              <span
                v-bk-overflow-tips
                class="meta-value is-code">{{ editingPlugin.plugin_code || '--' }}</span>
            </div>
          </div>
        </section>

        <div
          v-if="isDisabledConfigMode"
          class="edit-form-area disabled-config-form">
          <div class="edit-form-item">
            <div class="edit-form-label">
              {{ $t('停用原因（选填）') }}
            </div>
            <bk-input
              v-model="editForm.disable_reason"
              type="textarea"
              :rows="3"
              :maxlength="200"
              :show-word-limit="true"
              :placeholder="$t('已统一迁移到「发送通知」插件，旧机器人即将停用')" />
          </div>
          <div class="edit-form-item">
            <div class="edit-form-label">
              {{ $t('替换插件（选填）') }}
            </div>
            <bk-cascade
              v-model="replacePluginPath"
              class="replace-cascade"
              ext-popover-cls="disabled-cascade-popover"
              :list="disabledCascadeList"
              :clearable="true"
              :placeholder="$t('请选择')">
              <template
                slot="option"
                slot-scope="{ node }">
                <i
                  v-if="node.divider"
                  class="cascade-cate-divider" />
                <i
                  v-if="node.icon"
                  :class="['cascade-cate-icon', node.icon]" />
                <span class="cascade-cate-name">{{ node.name }}</span>
              </template>
            </bk-cascade>
          </div>
          <p class="dialog-tips">
            {{ $t('原因与替换插件会显示在画布节点提示与保存拦截提示中。') }}
            <br>
            {{ $t('不填原因时，画布/拦截统一显示「该插件已被空间管理员停用」。') }}
          </p>
        </div>
        <div
          v-else
          class="edit-form-area">
          <div class="edit-form-item">
            <div class="edit-form-label">
              {{ $t('所属目录') }}
              <span class="required">*</span>
            </div>
            <bk-select
              v-model="editForm.category"
              :searchable="true">
              <bk-option-group
                v-if="editAiRecommendations.length"
                :name="$t('AI 推荐')">
                <bk-option
                  v-for="item in editAiRecommendations"
                  :id="item.id"
                  :key="item.id"
                  :name="item.name" />
              </bk-option-group>
              <bk-option
                v-for="item in editCategoryOptions"
                :id="item.id"
                :key="item.id"
                :name="item.name"
                :class="{ 'category-option-divider': item.divider }">
                <span
                  v-if="item.special === 'ai'"
                  class="category-ai-option">
                  <img
                    :src="item.icon"
                    class="ai-icon"
                    alt="">
                  <span class="ai-name">{{ item.label }}</span>
                </span>
                <span
                  v-else-if="item.special === 'uncategorized'"
                  class="category-uncat-option">
                  <i class="bk-icon icon-question-circle" />
                  <span>{{ item.label }}</span>
                </span>
                <span
                  v-else
                  :class="item.isSub ? 'category-sub-option' : 'category-top-option'">
                  {{ item.isSub ? item.subName : item.label }}
                </span>
              </bk-option>
            </bk-select>
          </div>
          <div class="edit-form-item">
            <div class="edit-form-label">
              <span>{{ $t('空间推荐') }}</span>
              <span class="label-divider" />
              <span class="label-tips">{{ $t('显示在画布插件面板顶部的「空间推荐」中') }}</span>
            </div>
            <bk-switcher
              v-model="editForm.recommended"
              v-bk-tooltips="editSwitcherTips"
              theme="primary"
              :disabled="editRecommendDisabled" />
          </div>
        </div>
      </div>
      <template slot="footer">
        <bk-button
          theme="primary"
          :loading="editSaving"
          @click="handleEditSave">
          {{ $t('保存') }}
        </bk-button>
        <bk-button
          theme="default"
          :disabled="editSaving"
          @click="handleEditCancel">
          {{ $t('取消') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script>
import PluginDetailSlider from './PluginDetailSlider.vue';
import CategorySelectPanel from './CategorySelectPanel.vue';
import bkCascade from 'bk-magic-vue/lib/cascade';
import 'bk-magic-vue/lib/ui/cascade.css';
import aiBluekingIcon from '@/assets/images/ai-blueking.svg';
import { mapActions } from 'vuex';
import {
  getStatusMap,
  getStatusTabs,
  normalizePluginStatus,
  getTypeOptions,
  getSourceOptions,
  getTypeText,
  getSourceText,
  matchPluginSource,
  getCategoryPath,
  buildCategoryNameMap,
  getRowActions,
  getStatusChangeMessage,
  mapBackendStatus,
  renderCategoryHeader as renderCategoryHeaderCell,
  MAX_RECOMMEND,
  CATEGORY_ICONS,
} from './shared';

const EDIT_AI_RECOMMEND = '__ai_recommend__';
const EDIT_UNCATEGORIZED = '__uncategorized__';

export default {
  name: 'PluginList',
  components: {
    PluginDetailSlider,
    CategorySelectPanel,
    bkCascade,
  },
  props: {
    category: {
      type: String,
      default: 'all',
    },
    categoryTitle: {
      type: String,
      default: '',
    },
    categoryIcon: {
      type: String,
      default: '',
    },

    categories: {
      type: Array,
      default: () => [],
    },
    spaceId: {
      type: [String, Number],
      default: '',
    },
    // 全量插件（用于停用确认弹窗的替换插件选项）
    plugins: {
      type: Array,
      default: () => [],
    },
    // 分类原始树（用于停用确认弹窗的替换插件级联分组）
    categoryTree: {
      type: Array,
      default: () => [],
    },
    // 已推荐数量（空间推荐名额上限校验用）
    recommendTotal: {
      type: Number,
      default: 0,
    },
    strategyMode: {
      type: String,
      default: 'review',
    },
  },
  data() {
    return {
      activeTab: 'enable',
      searchValues: [],
      total: 0,
      pagination: {
        current: 1,
        count: 0,
        limit: 10,
      },
      pluginList: [],
      loading: false,
      statusCounts: {},
      pendingLocateTab: false,  // 仅「搜索条件变化」触发的那次请求才自动定位 Tab，避免覆盖用户手动切换的选择
      skipAutoFetch: false,
      selection: [],
      isDetailSliderShow: false,
      detailPlugin: null,
      disabledDialogVisible: false,
      disabledRow: null,
      disabledForm: {
        disable_reason: '',
      },
      replacePluginPath: [], // 级联选中路径（分类 → 子分类 → 插件），末级即替换插件 id
      activeCategoryPopId: '',
      editDialogVisible: false,
      editMode: 'edit',
      editingPlugin: null,
      editSaving: false,
      editForm: {
        category: '',
        recommended: false,
        disable_reason: '',
      },
      passRow: null,
      passCategory: '',
      // 编辑弹窗 AI 推荐
      editAiRecommendIds: [],
      // 列表行内快捷分类的 AI 推荐建议
      quickAiRecommendRowId: '',
      quickAiRecommendIds: [],
      // AI 推荐
      batchAiRecommendIds: [],
      passAiRecommendIds: [],
      aiRecommendLoading: false,
      activePassCategoryPop: false,
      passTippyOptions: {
        hideOnClick: false,
        onCreate: (instance) => {
          instance.tooltip && instance.tooltip.classList.add('review-pass-tooltip');
        },
      },
      submitting: false, // 空间推荐的写操作（取消推荐 / 状态变更）进行中
    };
  },
  computed: {
    // 搜索条件转查询参数
    searchParams() {
      const params = {
        searchType: [],
        searchSource: [],
        searchCategory: [],
        searchName: '',
        searchUpdatedBy: '',
        keyword: [],
      };
      const fieldMap = {
        type: 'searchType',
        source: 'searchSource',
        category: 'searchCategory',
      };
      (this.searchValues || []).forEach((chip) => {
        const { id, name, values } = chip || {};
        // 模糊匹配插件名称 / 最近修改人
        if (!fieldMap[id]) {
           if (Array.isArray(values)) {
            params.keyword.push(values[0].id);
           } else {
            params.keyword.push(name);
           }
        } else {
          params[fieldMap[id]].push(values[0].id);
        }
      });
      return params;
    },
    queryParams() {
      const search = this.searchParams;
      console.log('search', search);
      // 「未启用」Tab 聚合 disabled + expired 两态
      const statusMap = { not_enable: ['disabled', 'expired'] };
      const status = statusMap[this.activeTab] || (this.activeTab ? [this.activeTab] : []);
      const pluginTypes = Array.isArray(search.searchType) ? search.searchType : [];
      const keyword = [
        ...(Array.isArray(search.keyword) ? search.keyword : [search.keyword]),
        search.searchName,
        search.searchUpdatedBy,
      ].map(item => String(item || '').trim()).filter(Boolean);
      const params = {
        space_id: this.spaceId,
        directory_id: this.category || 'all',
        page: this.pagination.current,
        page_size: this.pagination.limit,
      };
      if (status.length) params.status = status.join(',');
      if (pluginTypes.length) params.plugin_type = pluginTypes.join(',');
      if ((search.searchSource || []).length) params.source_key = search.searchSource.join(',');
      if (keyword.length) params.keyword = keyword.join(',');
      if (search.searchCategory.length > 0) params.directory_id = search.searchCategory.join(',');
      return params;
    },
    isRecommend() {
      return this.category === 'recommend';
    },
    editAiRecommendations() {
      const ids = new Set((this.editAiRecommendIds || []).map(id => String(id)));
      const options = [];
      (this.categoryTree || []).forEach((group) => {
        if (ids.has(String(group.id))) {
          options.push({ id: group.id, name: group.name });
        }
        (group.children || []).forEach((sub) => {
          if (ids.has(String(sub.id))) {
            options.push({ id: sub.id, name: `${group.name}/${sub.name}` });
          }
        });
      });
      return options;
    },
    editCategoryOptions() {
      const options = [
        {
          id: EDIT_AI_RECOMMEND,
          name: this.$t('AI 推荐'),
          label: this.$t('AI 推荐'),
          special: 'ai',
          icon: aiBluekingIcon,
        },
        {
          id: EDIT_UNCATEGORIZED,
          name: this.$t('未分类'),
          label: this.$t('未分类'),
          special: 'uncategorized',
          divider: (this.categoryTree || []).length > 0,
        },
      ];
      (this.categoryTree || []).forEach((group) => {
        options.push({ id: group.id, name: group.name, label: group.name, isSub: false });
        (group.children || []).forEach((sub) => {
          options.push({ id: sub.id, name: `${group.name}/${sub.name}`, label: sub.name, subName: sub.name, isSub: true });
        });
      });
      return options;
    },
    maxRecommend() {
      return MAX_RECOMMEND;
    },
    strategyModeText() {
      const map = {
        review: this.$t('全部需要审核'),
        visible: this.$t('全部直接通过'),
        conditional: this.$t('设条件自动通过'),
      };
      return map[this.strategyMode] || map.review;
    },
    statusMap() {
      return getStatusMap(key => this.$t(key));
    },
    // 状态 Tab 及数量
    statusTabs() {
      return getStatusTabs(this.statusCounts, key => this.$t(key));
    },
    // 当前是否为「启用」Tab（行内：编辑 / 停用）
    isAvailableTab() {
      return this.activeTab === 'enable';
    },
    // 当前是否为「待审核」Tab（批量通过 / 批量停用 / 批量移动）
    isReviewTab() {
      return this.activeTab === 'pending_review';
    },
    // 当前是否为「未启用」Tab（聚合 disabled+expired 两态；行内：启用 / 停用配置）
    isUnusedTab() {
      return this.activeTab === 'not_enable';
    },
    // 非推荐 Tab 均有勾选列与批量操作工具栏（expired 终态行由 selectable 禁用勾选）
    hasSelection() {
      return !this.isRecommend;
    },
    typeOptions() {
      return getTypeOptions(key => this.$t(key));
    },
    sourceOptions() {
      return getSourceOptions(key => this.$t(key));
    },
    searchData() {
      return [
        { id: 'name', name: this.$t('插件名称') },
        // { id: 'desc', name: this.$t('描述') },
        { id: 'updated_by', name: this.$t('最近修改人') },
        {
          id: 'type',
          name: this.$t('类型'),
          children: this.typeOptions
            .filter(item => item.value !== 'all')
            .map(item => ({ id: item.value, name: item.label })),
        },
        {
          id: 'source',
          name: this.$t('来源'),
          children: this.sourceOptions
            .filter(item => item.value !== 'all')
            .map(item => ({ id: item.value, name: item.label })),
        },
        {
          id: 'category',
          name: this.$t('目录'),
          children: (this.categoryTree || []).reduce((acc, cate) => {
            acc.push({ id: cate.id, name: cate.name });
            (cate.children || []).forEach(child => acc.push({ id: child.id, name: child.name }));
            return acc;
          }, []),
        },
      ];
    },
    tableColumns() {
      const typeCol = { id: 'type', label: this.$t('类型'), width: 200, filters: this.typeFilters, filterMethod: this.filterMethod };
      const sourceCol = { id: 'source', label: this.$t('来源'), width: 200, filters: this.sourceFilters, filterMethod: this.filterMethod };
      const statusCol = { id: 'status', label: this.$t('状态'), width: 150, filters: this.statusFilters, filterMethod: this.filterMethod };
      const incomeCol = { id: 'update_at', label: this.$t('来源入库时间'), width: 200, sortable: true };
      if (this.isRecommend) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('目录'), width: 250 },
          { id: 'ref_count', label: this.$t('当前引用流程'), width: 130, sortable: true },
          { id: 'updated_by', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
          { id: 'update_at', label: this.$t('最近修改时间'), width: 200, sortable: true },
          statusCol,
        ];
      }
      if (this.isReviewTab) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('目标目录'), width: 250 },
          incomeCol,
          statusCol,
        ];
      }
      if (this.isUnusedTab) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('原目录'), width: 250 },
          { id: 'ref_count', label: this.$t('当前引用流程'), width: 130, sortable: true },
          { id: 'updated_by', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
          { id: 'update_at', label: this.$t('最近修改时间'), width: 200, sortable: true },
          // incomeCol,
          statusCol,
        ];
      }
      return [
        { id: 'name', label: this.$t('插件'), width: 250 },
        typeCol,
        sourceCol,
        { id: 'category', label: this.$t('目录'), width: 250 },
        { id: 'ref_count', label: this.$t('当前引用流程'), width: 130, sortable: true },
        { id: 'updated_by', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
        { id: 'update_at', label: this.$t('最近修改时间'), width: 200, sortable: true },
        statusCol,
      ];
    },
    tableMaxHeight() {
      return this.isRecommend ? window.innerHeight - 200 : Math.max(window.innerHeight - 460, 300);
    },
    // 列筛选选项
    typeFilters() {
      return this.typeOptions
        .filter(item => item.value !== 'all')
        .map(item => ({ text: item.label, value: item.value }));
    },
    sourceFilters() {
      return this.sourceOptions
        .filter(item => item.value !== 'all')
        .map(item => ({ text: item.label, value: item.value }));
    },
    // 状态列筛选选项
    statusFilters() {
      return Object.keys(this.statusMap)
        .map(value => ({ text: this.statusMap[value].label, value }));
    },
    // 最近修改人筛选选项
    updatedByFilters() {
      return [...new Set(this.pluginList.map(row => row.updated_by).filter(Boolean))]
        .map(name => ({ text: name, value: name }));
    },
    // 启用至目录：当前选中分类的显示名（空串回落「未分类」占位）
    passCategoryLabel() {
      return buildCategoryNameMap(this.categoryTree)[this.passCategory] || '';
    },
    // 待审核确认气泡中的选中插件文案
    reviewSelectedNames() {
      if (this.selection.length === 1) return this.selection[0].plugin_name;
      return this.$t('已选 {count} 项', { count: this.selection.length });
    },
    cascadeSourcePlugin() {
      if (this.editDialogVisible && this.isDisabledConfigMode) return this.editingPlugin;
      return this.disabledRow;
    },
    disabledCascadeList() {
      const self = this.cascadeSourcePlugin;
      if (!self) return [];
      const candidates = (this.plugins || []).filter(item => item.id !== self.id && item.status === 'enable');
      const toLeaf = item => ({ id: item.id, name: item.plugin_name });
      const byCategory = {};
      candidates.forEach((item) => {
        const key = item.directory_id || '';
        byCategory[key] = byCategory[key] || [];
        byCategory[key].push(item);
      });
      const result = [
        { id: 'all', name: this.$t('全部插件'), icon: CATEGORY_ICONS.all, children: candidates.map(toLeaf) },
        {
          id: 'recommend',
          name: this.$t('空间推荐'),
          icon: CATEGORY_ICONS.recommend,
          children: candidates.filter(item => item.recommended).map(toLeaf),
        },
        {
          id: 'uncategorized',
          name: this.$t('未分类插件'),
          icon: CATEGORY_ICONS.uncategorized,
          children: (byCategory[''] || []).map(toLeaf),
        },
        ...(this.categoryTree || []).map(cate => this.buildCategoryNode(cate, byCategory, toLeaf)),
      ];
      // 只允许选末级插件
      const fixedIds = new Set(['all', 'recommend', 'uncategorized']);
      const withDivider = result.filter(node => node.children.length);
      const firstCate = withDivider.find(node => !fixedIds.has(node.id));
      if (firstCate) firstCate.divider = true;
      return withDivider;
    },
    // 级联末级即替换插件 id；选中项是目录时按未选择处理，避免把目录 id 当插件提交
    replacePluginId() {
      const last = this.replacePluginPath.length
        ? this.replacePluginPath[this.replacePluginPath.length - 1]
        : '';
      if (!last) return '';
      return (this.plugins || []).some(item => item.id === last) ? last : '';
    },
    // 编辑弹窗
    editingStatusInfo() {
      return this.editingPlugin ? (this.statusMap[this.statusGroup(this.editingPlugin.status)] || {}) : {};
    },
    editingTypeText() {
      return this.editingPlugin ? getTypeText(this.editingPlugin.plugin_type, key => this.$t(key)) : '--';
    },
    editingSourceText() {
      return this.editingPlugin ? getSourceText(this.editingPlugin.source_key, key => this.$t(key)) : '--';
    },
    editingLogoText() {
      return this.editingPlugin && this.editingPlugin.plugin_name ? this.editingPlugin.plugin_name.trim().charAt(0) : '';
    },
    isDisabledConfigMode() {
      return this.editMode === 'disabledConfig';
    },
    editDialogTitle() {
      return this.isDisabledConfigMode ? this.$t('停用配置') : this.$t('编辑插件');
    },
    // 只有「启用」插件可新设为推荐
    editRecommendDisabled() {
      return !!this.editingPlugin && this.editingPlugin.status !== 'enable' && !this.editForm.recommended;
    },
    // 开关置灰原因
    editRecommendDisabledReason() {
      const status = this.editingStatusInfo.label || '';
      return this.editForm.recommended
        ? this.$t('该插件当前状态为{status}，仅可关闭推荐以释放名额', { status })
        : this.$t('{status}的插件不能新设为推荐', { status });
    },
    // 仅开关置灰时悬停提示原因
    editSwitcherTips() {
      return {
        content: this.editRecommendDisabledReason,
        disabled: !this.editRecommendDisabled,
      };
    },
  },
  watch: {
    'editForm.category'(val, oldVal) {
      if (val !== EDIT_AI_RECOMMEND) return;
      this.handleEditAiRecommend(oldVal);
    },
    total: {
      handler(val) {
        this.pagination.count = val;
        this.clampCurrentPage();
      },
      immediate: true,
    },
    // 状态 Tab 变化
    activeTab() {
      if (this.skipAutoFetch) return;
      this.resetPageAndFetch();
    },
    // 搜索条件变化
    searchValues() {
      if (this.skipAutoFetch) return;
      this.resetPageAndFetch();
    },
    'pagination.current'() {
      this.fetchList();
    },
    'pagination.limit'() {
      this.resetPageAndFetch();
    },
    // 切换分类：清空搜索框内容并把状态 Tab 归位到「可用」
    category() {
      this.skipAutoFetch = true;
      this.searchValues = [];
      this.activeTab = 'enable';
      this.$nextTick(() => {
        if (this.skipAutoFetch) {
          this.skipAutoFetch = false;
          this.resetPageAndFetch();
        }
      });
    },
  },
  mounted() {
    this.fetchList();
  },
  methods: {
    ...mapActions('pluginManage', [
      'getPluginList',
      'getRecommendList',
      'updatePlugin',
      'updateDisableConfig',
      'aiClassify',
      'updatePluginStatus',
      'cancelRecommend',
    ]),
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
    handleSearchChange(values) {
      this.searchValues = values || [];
      this.pendingLocateTab = true;
    },
    async fetchList() {
      if (this.isRecommend) {
        this.pendingLocateTab = false;
        await this.fetchRecommendList();
        return;
      }
      const shouldLocateTab = this.pendingLocateTab;
      this.pendingLocateTab = false;
      this.loading = true;
      try {
        const { count, results, status_counts: statusCounts } = await this.getPluginList(this.queryParams);
        this.pluginList = results;
        this.total = count;
        this.statusCounts = statusCounts || {};
        if (shouldLocateTab) {
          this.locateFirstAvailableTab();
        }
      } finally {
        this.loading = false;
      }
    },
    async fetchRecommendList() {
      this.loading = true;
      try {
        const results = await this.getRecommendList({ space_id: this.spaceId });
        this.pluginList = results;
        this.total = 0;
        this.statusCounts = {};
      } finally {
        this.loading = false;
      }
    },
    // 搜索条件变化后默认定位到第一个有数据的tab
    locateFirstAvailableTab() {
      if (!this.searchValues.length) return;
      const counts = this.statusCounts || {};
      const firstWithCount = getStatusTabs(counts, key => key)
        .find(tab => !tab.divider && (counts[tab.value] || 0) > 0);
      if (firstWithCount && firstWithCount.value !== this.activeTab) {
        this.activeTab = firstWithCount.value;
      }
    },
    handleTabChange(value) {
      this.activeTab = value;
    },
    handlePageChange(page) {
      this.pagination.current = page;
    },
    handlePageLimitChange(limit) {
      this.pagination.limit = limit;
    },
    filterMethod(value, row, column) {
      const { property } = column;
      if (property === 'status') {
        return this.statusGroup(row.status) === value;
      }
      if (property === 'source') {
        // API 类来源带子级路径（api/apidemo），按类型前缀匹配
        return matchPluginSource(row.source_key, value);
      }
      const fieldMap = { type: 'plugin_type', source: 'source_key' };
      const field = fieldMap[property] || property;
      return row[field] === value;
    },
    statusGroup(status) {
      return normalizePluginStatus(status);
    },
    // 待审核「目标目录」列头
    renderReviewCategoryHeader(h, { column }) {
      return h('div', { class: 'review-category-header' }, [
        h('span', { class: 'category-header-label' }, [column.label]),
        h('span', {
          class: 'ai-recommend-link',
          on: { click: () => this.handleAiRecommendCategory() },
        }, [this.$t('AI 推荐')]),
      ]);
    },
    // AI 推荐目标目录
    handleAiRecommendCategory() {
      const leafCategories = [];
      (this.categoryTree || []).forEach((group) => {
        leafCategories.push(group.id);
        (group.children || []).forEach(child => leafCategories.push(child.id));
      });
      if (!this.pluginList.length || !leafCategories.length) return;
      this.pluginList.forEach((row) => {
        const categoryId = leafCategories[Math.floor(Math.random() * leafCategories.length)];
        this.$emit('categoryChange', { row, categoryId, followSource: false });
      });
    },
    handleSelectionChange(selection) {
      this.selection = selection;
    },
    // 未启用 Tab：expired 为终态（来源已不存在，后端不允许人工启用），禁用勾选
    selectionSelectable(row) {
      return this.isUnusedTab ? row.status === 'disabled' : true;
    },
    categoryPath(categoryId) {
      return getCategoryPath(this.categories, categoryId);
    },
    // 快捷编辑所属分类
    handleQuickChangeCategory(row, categoryId, followSource = false) {
      const popRef = this.$refs[`categoryPop-${row.id}`];
      if (popRef && popRef[0]) {
        popRef[0].hideHandler();
      }
      this.$emit('categoryChange', { row, categoryId, followSource });
    },
    // 行内快捷分类面板
    handleQuickCategorySelect(row, { categoryId, followSource, isAiRecommend }) {
      if (isAiRecommend) {
        this.fetchAiRecommendIds([row.id]).then((ids) => {
          if (ids) {
            this.quickAiRecommendRowId = row.id;
            this.quickAiRecommendIds = ids;
          }
        });
        return;
      }
      this.quickAiRecommendRowId = '';
      this.quickAiRecommendIds = [];
      this.handleQuickChangeCategory(row, categoryId, followSource);
    },
    async fetchAiRecommendIds(pluginIds) {
      if (this.aiRecommendLoading) return null;
      if (!pluginIds.length) {
        this.$bkMessage({ message: this.$t('请先勾选插件后再使用 AI 推荐'), theme: 'warning' });
        return null;
      }
      this.aiRecommendLoading = true;
      try {
        const res = await this.aiClassify({ space_id: this.spaceId, plugin_ids: pluginIds });
        if (res && res.result === 'patch') {
          return Object.values(res.patch || {}).map(id => String(id));
        }
        const reason = res && res.result === 'error' && res.message ? res.message : '';
        this.$bkMessage({ message: reason || this.$t('AI 暂无推荐分类，请手动选择'), theme: 'warning' });
        return null;
      } catch (e) {
        this.$bkMessage({ message: this.$t('AI 推荐获取失败，请手动选择'), theme: 'error' });
        return null;
      } finally {
        this.aiRecommendLoading = false;
      }
    },
    // 批量移动
    handleBatchMoveCategory({ categoryId, followSource, isAiRecommend }) {
      if (isAiRecommend) {
        this.fetchAiRecommendIds(this.selection.map(row => row.id)).then((ids) => {
          if (ids) this.batchAiRecommendIds = ids;
        });
        return;
      }
      const popRef = this.$refs.batchMovePopover;
      if (popRef) {
        popRef.hideHandler();
      }
      this.$emit('batchCategoryChange', { rows: [...this.selection], categoryId, followSource });
    },
    handleRowStatus(row, status, message) {
      this.$emit('statusChange', { row, status, message });
    },
    handlePassClick(row) {
      this.passRow = row;
      this.passCategory = row.directory_id || '';
    },
    handlePassCategorySelect({ categoryId, isAiRecommend }) {
      if (isAiRecommend) {
        if (!this.passRow) return;
        this.fetchAiRecommendIds([this.passRow.id]).then((ids) => {
          if (ids) this.passAiRecommendIds = ids;
        });
        return;
      }
      this.passCategory = categoryId;
      this.hidePassCategoryPop();
    },
    async handleEditAiRecommend(previousVal) {
      this.$nextTick(() => {
        this.editForm.category = previousVal === undefined ? '' : previousVal;
      });
      if (this.aiRecommendLoading) return;
      const ids = await this.fetchAiRecommendIds([this.editingPlugin.id]);
      this.editAiRecommendIds = ids || [];
    },
    hidePassCategoryPop() {
      const poppers = document.querySelectorAll('.tippy-popper.pass-category-popover');
      for (const popper of poppers) {
        if (popper._tippy) {
          popper._tippy.hide();
        }
      }
      this.activePassCategoryPop = false;
    },
    handleReviewPassConfirm(row) {
      this.$emit('statusChange', {
        row,
        status: 'enable',
        targetDirectoryId: this.passCategory || '',
        message: this.$t('已启用'),
      });
    },
    buildCategoryNode(cate, byCategory, toLeaf) {
      const children = [];
      ((cate && cate.children) || []).forEach((sub) => {
        const subPlugins = (byCategory[sub.id] || []).map(toLeaf);
        // 子目录下没有插件时不渲染
        if (subPlugins.length) {
          children.push({
            id: sub.id,
            name: sub.name,
            icon: CATEGORY_ICONS.level2,
            children: subPlugins,
          });
        }
      });
      children.push(...((cate && byCategory[cate.id]) || []).map(toLeaf));
      return {
        id: cate.id,
        name: cate.name,
        // 一级目录：
        icon: CATEGORY_ICONS.level1,
        children,
      };
    },
    // 打开停用确认弹窗
    openDisabledDialog(row) {
      this.disabledRow = row;
      this.disabledForm = { disable_reason: row.disable_reason || '' };
      this.replacePluginPath = this.findCascadePath(this.disabledCascadeList, row.replace_plugin_id);
      this.disabledDialogVisible = true;
    },
    handleDisabledCancel() {
      this.disabledDialogVisible = false;
    },
    handleDisabledConfirm() {
      this.$emit('statusChange', {
        row: this.disabledRow,
        status: 'disabled',
        disableReason: this.disabledForm.disable_reason,
        replacePluginId: this.replacePluginId,
        message: this.$t('已停用'),
      });
      this.disabledDialogVisible = false;
    },

    // 批量状态变更
    handleBatchStatus(status) {
      if (!this.selection.length) return;
      this.$emit('batchStatusChange', { rows: [...this.selection], status });
    },
    // 待审核批量通过（未传目标目录，各条目沿用现有目录）
    handleBatchReviewPass() {
      if (!this.selection.length) return;
      this.$emit('batchStatusChange', {
        rows: [...this.selection],
        status: 'enable',
        message: this.$t('已通过审核'),
      });
    },
    handleOpenDetail(row) {
      this.detailPlugin = row;
      this.isDetailSliderShow = true;
    },
    // 详情侧滑-查看流程
    handleDetailViewFlow({ row }) {
      const { href } = this.$router.resolve({
        name: 'templatePanel',
        params: {
          templateId: row.template_id,
          type: 'view',
        },
        query: this.$route.query,
      });
      window.open(href, '_blank');
    },
    handleNameClick(row) {
      this.handleOpenDetail(row);
    },
    typeText(type) {
      return getTypeText(type, key => this.$t(key));
    },
    sourceText(source) {
      return getSourceText(source, key => this.$t(key));
    },
    renderCategoryHeader(h, { column }) {
      return renderCategoryHeaderCell(h, column, key => this.$t(key));
    },
    rowActions(row) {
      return getRowActions(row, key => this.$t(key));
    },
    handleRowAction(row, action) {
      const popover = this.$refs[`rowMore-${row.id}`];
      const instance = Array.isArray(popover) ? popover[0] : popover;
      if (instance && typeof instance.hideHandler === 'function') {
        instance.hideHandler();
      }
      this.handleRecommendAction(row, action);
    },
    async handleRecommendAction(row, action) {
      if (action.type === 'edit') {
        this.openEditDialog(row);
        return;
      }
      if (action.type === 'disabledConfig') {
        this.openDisabledConfigDialog(row);
        return;
      }
      const target = this.pluginList.find(item => item.id === row.id);
      const prevStatus = target ? target.status : '';
      this.submitting = true;
      try {
        await this.updatePluginStatus({
          plugin_id: row.id,
          space_id: this.spaceId,
          status: mapBackendStatus(row.status, action.status),
        });
        if (target) {
          target.status = action.status;
        }
        this.$bkMessage({
          message: action.message || getStatusChangeMessage(action.status, key => this.$t(key)),
          theme: 'success',
        });
        this.reload();
        this.$emit('recommendChanged');
      } catch (e) {
        if (target) {
          target.status = prevStatus;
        }
      } finally {
        this.submitting = false;
      }
    },
    async handleCancelRecommend(row) {
      this.submitting = true;
      try {
        await this.cancelRecommend({ space_id: this.spaceId, plugin_id: row.id });
        this.pluginList = this.pluginList.filter(item => item.id !== row.id);
        this.$bkMessage({
          message: this.$t('已取消推荐'),
          theme: 'success',
        });
        this.$emit('recommendChanged');
      } catch (e) {
        console.log(e);
      } finally {
        this.submitting = false;
      }
    },
    openEditDialog(row) {
      this.editingPlugin = row;
      this.editMode = 'edit';
      this.editAiRecommendIds = [];
      this.editForm = {
        category: row.directory_id || EDIT_UNCATEGORIZED,
        recommended: !!row.recommended,
        disable_reason: '',
      };
      this.replacePluginPath = [];
      this.editDialogVisible = true;
    },
    // 打开停用配置弹窗
    openDisabledConfigDialog(row) {
      this.editingPlugin = row;
      this.editMode = 'disabledConfig';
      this.editForm = {
        category: row.directory_id || '',
        recommended: !!row.recommended,
        disable_reason: row.disable_reason || '',
      };
      this.editDialogVisible = true;
      this.replacePluginPath = this.findCascadePath(this.disabledCascadeList, row.replace_plugin_id);
    },
    // 在替换插件级联树中反查插件 id 的完整路径（用于回显已保存的替换插件）
    findCascadePath(list, id, path = []) {
      if (!id) return [];
      for (const node of list) {
        const current = [...path, node.id];
        if (node.id === id) return current;
        if (node.children && node.children.length) {
          const found = this.findCascadePath(node.children, id, current);
          if (found.length) return found;
        }
      }
      return [];
    },
    handleEditCancel() {
      this.editDialogVisible = false;
    },
    // 保存编辑
    async handleEditSave() {
      if (this.isDisabledConfigMode) {
        this.editSaving = true;
        try {
          await this.updateDisableConfig({
            plugin_id: this.editingPlugin.id,
            space_id: this.spaceId,
            disable_reason: this.editForm.disable_reason,
            replace_plugin_id: this.replacePluginId,
          }),
          this.$bkMessage({
            message: this.$t('保存成功'),
            theme: 'success',
          });
          this.editDialogVisible = false;
          this.reload();
        } catch (e) {
          console.log(e);
        } finally {
          this.editSaving = false;
        }
        return;
      }
      if (!this.editForm.category) {
        this.$bkMessage({ message: this.$t('请选择所属目录'), theme: 'error' });
        return;
      }
      // 名额校验
      if (this.editForm.recommended && !this.editingPlugin.recommended && this.recommendTotal >= MAX_RECOMMEND) {
        this.$bkMessage({
          message: this.$t('空间推荐名额已满（共 {total} 个），请先取消其他插件的推荐', { total: MAX_RECOMMEND }),
          theme: 'error',
        });
        return;
      }
      this.editSaving = true;
      try {
        await this.updatePlugin({
          plugin_id: this.editingPlugin.id,
          space_id: this.spaceId,
          directory_id: this.editForm.category === EDIT_UNCATEGORIZED ? '' : this.editForm.category,
          recommended: this.editForm.recommended,
        });
        this.$bkMessage({
          message: this.$t('保存成功'),
          theme: 'success',
        });
        this.editDialogVisible = false;
        this.reload();
        // 推荐名额 / 分类计数可能变化，通知父组件刷新概要
        this.$emit('editSaved');
        if (this.isRecommend) {
          this.$emit('recommendChanged');
        }
      } catch (e) {
        this.$bkMessage({
          message: this.$t('操作失败，请重试'),
          theme: 'error',
        });
      } finally {
        this.editSaving = false;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.plugin-name-cell {
  display: flex;
  align-items: center;
  gap: 4px;

  .plugin-tag {
    flex-shrink: 0;
    padding: 0 6px;
    border-radius: 8px;
    font-size: 10px;
    line-height: 16px;
    color: #a04eed;
    background: #f3e8ff;

    &.is-recommend,
    &.is-plugin {
      color: #a04eed;
      background: #f3e8ff;
    }
  }

  .plugin-name {
    color: #3a84ff;
    cursor: pointer;

    &:hover {
      color: #699df4;
    }
  }
}

.category-cell {
  display: flex;
  align-items: center;
  gap: 4px;

  .category-icon {
    font-size: 14px;
    border-radius: 4px;
    padding: 1px;
    background: #F0F4FA;
    color: #4E5E7A;
    flex-shrink: 0;
  }
}

.ref-count {
  color: #3a84ff;
  font-weight: 700;
  cursor: pointer;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;

  .bk-icon {
    font-size: 14px;
    line-height: 1;
  }

  &.is-enable {
      color: #1D8F70;
      background: #E1F5F0;
  }
  &.is-pending_review {
    color: #f59500;
    background-color: #FFEDD1;
  }

  &.is-expired,
  &.is-not_enable,
  &.is-disabled {
    color: #8F9FBD;
    background-color: #F0F4FA;
  }
}

.operate-column {
  display: flex;
  align-items: center;
  gap: 12px;
}

.empty-text {
  color: #979ba5;
  font-size: 12px;
}

// 操作菜单：工具栏「更多操作」下拉 + 推荐列表行内 popover 共用
// （浮层可能挂在 body，但菜单项由本组件模板渲染、自带 scoped 属性，故这里不需要 ::v-deep）
.dropdown-list {
    margin: 0;
    padding: 4px 0;
    max-width: 87px;

    .dropdown-item {
        padding: 0 12px;
        line-height: 32px;
        font-size: 12px;
        color: #63656e;
        white-space: nowrap;
        cursor: pointer;

        &:hover {
            background: #f0f1f5;
            color: #3a84ff;
        }
    }
}

// 所属分类列头下划线
::v-deep .plugin-list-table {
  .category-header-label {
    text-decoration-line: underline;
    text-decoration-style: dotted;
    text-underline-offset: 24%;
    cursor: pointer;
    }
    .bk-table-header-label {
        font-weight: 500 !important;
        color: #111214 !important;
        font-family: "PingFang SC" !important;
    }
}

.plugin-list {
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 16px;
  background: #fff;
  border-radius: 2px;
  overflow-y: auto;

  .list-title {
    display: flex;
    align-items: center;
    color: #111214;
    font-family: "PingFang SC";
    font-size: 14px;
    font-style: normal;
    font-weight: 500;
    line-height: 22px;

    .list-title-icon {
      margin-right: 6px;
      margin-top: 2px;
    }
  }

  .recommend-header {
    display: flex;
    align-items: center;
    gap: 12px;
    .recommend-title{
      display: flex;
      align-items: center;
      gap: 4px;
      color: #111214;
      font-family: "PingFang SC";
      font-size: 14px;
      font-weight: 500;
      i {
        margin-top: 1px;
      }
    }

    .recommend-divider {
      width: 1px;
      height: 14px;
      background: #dcdee5;
    }

    .recommend-count {
      font-size: 12px;
      font-weight: 500;
      line-height: 22px;
      color: #4E5E7A;
      font-family: "PingFang SC";
      color: #4e5e7a;
    }
  }

  .recommend-alert {
    margin: 16px 0;
    border-radius: 4px;
    border: 1px solid #a3c5fd;
    background: #f0f5ff;

    .recommend-alert-list {
      margin: 0;
      padding-left: 16px;
      color: #4d4f56;

      li {
        list-style: disc;
      }
    }
  }


  .plugin-search-select {
    margin-top: 12px;
    margin-bottom: 16px;
    height: auto;
    min-height: 32px;

    ::v-deep .bk-search-select {
      width: 100%;
      border: 1px solid #c1cde5;
      border-radius: 6px;
      background: #fff;

      &.is-focus {
        border-color: #3a84ff;
      }
    }
  }

  .status-tabs {
    display: flex;
    align-items: center;
    gap: 32px;
    margin-bottom: 12px;
    background: #fff;
    border-bottom: 1px solid #e4e9f2;

    .status-tab {
      display: flex;
      align-items: center;
      gap: 4px;
      height: 36px;
      font-size: 13px;
      font-weight: 500;
      font-family: "PingFang SC";
      color: #111214;
      cursor: pointer;
      border-bottom: 2px solid transparent;

      .tab-icon {
        font-size: 16px;
        color: #4e5e7a;
        margin-top: 3px;
      }

      .tab-count {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 18px;
        height: 18px;
        padding: 0 5px;
        border-radius: 999px;
        background: #f0f4fa;
        font-size: 12px;
        font-weight: 700;
        line-height: 20px;
        font-family: "Arial";
        color: #8f9fbd;
        margin-top: 2px;

        &.is-warn {
          background: #ffedd1;
          color: #faa41e;
        }
      }

      &:hover {
        color: #3974ff;

        .tab-icon {
          color: #3974ff;
        }
      }

      &.is-active {
        color: #3974ff;
        border-bottom-color: #3974ff;

        .tab-icon {
          color: #3974ff;
        }

        .tab-count.is-active {
          background: #e5edff;
          color: #3974ff;
        }
      }
    }

    .tab-divider {
      display: flex;
      align-items: center;
      gap: 2px;

      &::before,
      &::after {
        content: '';
        width: 1px;
        height: 18px;
        background: #c1cde5;
      }
    }
  }

  ::v-deep .legacy-alert {
    border-radius: 6px;
    margin: 12px 0;
    .bk-alert-wraper {
        display: flex;
        align-items: baseline;
        padding: 6px 8px !important;
        .icon-info {
            margin-top: 2px;
        }
        .bk-alert-title {
            .bk-button-text {
                font-size: 12px;
            }
        }
    }
    &.review-alert {
      margin: 12px 0;
    }
  }
  .review-alert-tips {
    margin: 0;
    padding: 0;

    li {
      margin-left: 18px;
      font-size: 12px;
      line-height: 20px;
      color: #4e5e7a;
      word-break: break-word;
      list-style: disc;
    }

    .strategy-link {
      cursor: pointer;
      color: #3974ff;
      background-image: none;
    }
  }

  .list-toolbar {
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    .toolbar-left {
      display: flex;
      align-items: center;
      gap: 8px;

      .more-dropdown {
        .dropdown-trigger-btn {
          display: flex;
          align-items: center;
          gap: 4px;

          .icon-flip {
            transform: rotate(180deg);
          }
        }
      }
    }
    .bk-button {
      border-radius: 6px;
      font-size: 12px;
      font-family: "PingFang SC";
    }
    .bk-button.bk-primary.is-disabled,
    .bk-button.bk-primary[disabled] {
      background-color: #C1CDE5;
      border-color: #C1CDE5;
    }
  }
  .category-cell {
    .category-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      text-wrap: nowrap;
      padding: 6px 24px 6px 4px;
      border-radius: 4px;
      cursor: pointer;
      transition: background-color 0.15s ease;

      &:hover {
        background: #EAEBF0;
      }
      &.is-active {
        background: #fff;
        box-shadow: inset 0 0 0 1px #3A84FF;
      }

      &.is-plain {
        cursor: default;

        &:hover {
          background: transparent;
        }
      }
    }
  }

  .row-more-icon {
    font-size: 16px;
    color: #3a84ff;
    cursor: pointer;
  }

  ::v-deep .recommend-table {
    th:first-child .cell,
    td:first-child .cell {
      padding: 0 12px;
      overflow: visible;
      text-overflow: clip;
      white-space: nowrap;
    }
  }

}

.plugin-edit-content {
    display: flex;
    flex-direction: column;
    gap: 20px;

    .plugin-info {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      background: #f2f6fc;
      border-radius: 6px;

      .info-main {
        display: flex;
        align-items: flex-start;
        gap: 12px;

        .plugin-logo {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          flex-shrink: 0;
          border-radius: 8px;
          background: linear-gradient(135deg, #3a84ff 0%, #3269fe 100%);
          box-shadow: 0 10px 7.5px rgba(21, 75, 252, 0.2);
          color: #fff;
          font-size: 20px;
          font-weight: 600;
          line-height: 28px;
        }

        .info-basic {
          flex: 1;
          min-width: 0;

          .info-name-row {
            display: flex;
            align-items: center;
            gap: 8px;

            .info-name {
              font-size: 16px;
              font-weight: 500;
              line-height: 24px;
              color: #111214;
              white-space: nowrap;
            }
          }

          .info-desc {
            margin-top: 2px;
            font-size: 12px;
            line-height: 20px;
            color: #8f9fbd;
            word-break: break-all;
            max-width: 500px;
          }
        }
      }

      .info-meta {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .meta-item {
          display: flex;
          align-items: center;
          min-width: 0;
          font-size: 12px;
          line-height: 20px;

          .meta-label {
            flex-shrink: 0;
            color: #8f9fbd;
          }

          .meta-value {
            flex: 1;
            min-width: 0;
            color: #4e5e7a;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;

            &.is-code {
              font-family: Menlo, Consolas, monospace;
            }
          }
        }
      }

      .status-badge {
        display: inline-flex;
        align-items: center;
        height: 16px;
        padding: 0 6px;
        font-size: 10px;
        line-height: 16px;
        flex-shrink: 0;

        &.is-enable {
          color: #1d8f70;
          background: #e1f5f0;
          border-radius: 8px;
        }

        &.is-pending_review {
          background: #fff4e2;
          color: #ff9c01;
          border-radius: 8px;
        }

        &.is-expired,
        &.is-not_enable,
        &.is-disabled {
          color: #FFF;
          background-color: #FAA41E;
          border-radius: 4px;
        }

        .bk-icon {
          margin-top: 2px;
        }
      }
      .recommend-tag {
        display: inline-flex;
        align-items: center;
        height: 16px;
        padding: 0 6px;
        border-radius: 8px;
        font-size: 10px;
        line-height: 16px;
        flex-shrink: 0;
        color: #a04eed;
        background: #f3e8ff;
      }
    }

    .edit-form-area {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .edit-form-item {
      display: flex;
      flex-direction: column;
      gap: 6px;

      .edit-form-label {
        display: flex;
        gap: 2px;
        font-size: 12px;
        line-height: 20px;
        color: #4e5e7a;

        .required {
          color: #ea3636;
        }

        .label-divider {
          align-self: center;
          width: 1px;
          height: 12px;
          margin: 0 6px;
          background: #d9d9d9;
        }

        .label-tips {
          color: #8f9fbd;
        }
      }
    }
  }
</style>

<style lang="scss">
.category-header-popover {
    .tips-title {
        margin: 0 0 8px;
        font-size: 14px;
        font-weight: 700;
        line-height: 22px;
        color: #313238;
    }

    .tips-list {
        margin: 0;
        padding-left: 18px;
        list-style: disc;
    }

    .tips-item {
        list-style: disc;
        font-size: 12px;
        line-height: 20px;
        color: #313238;

        &::marker {
            color: #313238;
        }

        .tips-item-inner {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
    }

    .tips-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background: #f0f4fa;
        font-size: 14px;
        color: #4E5E7A;
    }
}
</style>

<style lang="scss">
.clean-popconfirm {
    &.bk-popconfirm-content,
    .bk-popconfirm-content {
        padding: 16px;
    }
    .popconfirm-operate {
        margin-top: 16px;
        margin-bottom: 0px;
        button {
            border-radius: 6px !important;
        }
        button.primary {
            background: #e54040 !important;
        }
    }
}

.clean-pop-main {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.clean-pop-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 6px;
    background: #fff0f0;

    .bk-icon {
        font-size: 19px !important;
        color: #e54040;
    }

    &.is-info {
        background: #f0f4ff;

        .bk-icon {
            color: #3974ff;
        }
    }

    &.is-warn {
        background: #fff3e0;

        .bk-icon {
            color: #faa41e;
        }
    }
}

.review-popconfirm {
    &.bk-popconfirm-content,
    .bk-popconfirm-content {
        padding: 16px;
    }
    .popconfirm-operate {
        margin-top: 16px;
        button {
            border-radius: 6px !important;
        }
    }
}


.review-pass-popconfirm {
    &.bk-popconfirm-content,
    .bk-popconfirm-content {
        padding: 16px 16px 0 16px;
        background: #fff;
    }
    .popconfirm-operate {
        overflow: hidden;
        margin: 16px -26px 0px -26px;
        padding: 8px 16px;
        margin-bottom: 0px !important;
        border-top: 1px solid #E9EDF5;
        background: #F7F9FC;
        button {
            border-radius: 6px !important;
        }
    }
    .tippy-tooltip {
      padding-bottom: 0px;
      overflow: hidden;
    }
}

.tippy-tooltip.review-pass-tooltip {
    padding: 0;
    background: #fff;
    overflow: hidden;
}

.pass-category-popover .tippy-tooltip {
    padding: 0;
}

.review-pass-pop {
    .pass-category-select {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 32px;
        padding: 0 10px;
        border: 1px solid #c4c6cc;
        border-radius: 2px;
        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        transition: border-color 0.15s ease;

        .bk-icon {
            font-size: 14px;
            color: #979ba5;
        }

        &:hover {
            border-color: #979ba5;
        }

        &.is-active {
            border-color: #3a84ff;

            .bk-icon {
                color: #3a84ff;
            }
        }
    }

    .pop-title {
        margin: 0 0 12px;
        font-size: 14px;
        font-weight: 700;
        line-height: 22px;
        color: #313238;
    }

    .pop-label {
        display: flex;
        align-items: center;
        margin-bottom: 6px;
        font-size: 12px;
        line-height: 20px;
        color: #4e5e7a;

        .required {
            margin: 0 2px;
            color: #ea3636;
        }

        .ai-recommend-link {
            display: inline-flex;
            align-items: center;
            gap: 2px;
            margin-left: auto;

            .commonicon-icon {
                font-size: 14px;
            }
        }
    }
    .bk-tooltip {
      width: 100%;
    }
}

.review-category-header {
    display: flex;
    align-items: center;
    gap: 4px;
}
.ai-recommend-link {
    font-size: 12px;
    line-height: 20px;
    color: #4466f3;
    background-image: linear-gradient(112deg, #4466f3 13%, #d187ea 83%);
    background-clip: text;
    -webkit-background-clip: text;
    cursor: pointer;
    user-select: none;

    &:hover {
        opacity: .8;
    }
}

.clean-pop-texts {
    flex: 1;
    min-width: 0;
    word-break: break-word;

    .clean-pop-title {
        margin: 0;
        font-size: 16px;
        font-weight: 500;
        line-height: 24px;
        color: #313238;
        font-family: "PingFang SC";
    }

    .clean-pop-name,
    .clean-pop-desc {
        margin: 8px 0 0;
        font-size: 12px;
        line-height: 20px;
        color: #4e5e7a;
    }

    .clean-pop-name span {
        color: #111214;
    }
}
</style>

<style lang="scss">
.disabled-confirm-dialog {
    .bk-dialog-header {
        padding: 0 24px;
    }
    .bk-dialog-content {
      border-radius: 6px;
      overflow: hidden;
    }
    .bk-dialog-body {
        padding: 20px 24px 24px;
        .bk-textarea-wrapper {
          border-radius: 6px;
          overflow: hidden;
        }
    }
    .disabled-alert {
      border-radius: 6px !important;
      .bk-icon {
        font-size: 14px !important;
      }
      ul {
        li {
          list-style: disc !important;
        }
      }
    }

    .bk-dialog-footer {
        height: 48px;
        padding: 8px 24px;
        background: #fafbfd;
        border-top: 1px solid #eaebf0;
        .bk-button {
          border-radius: 6px;
        }
        .bk-button + .bk-button {
            margin-left: 8px;
        }
    }
    .bk-select{
      border-radius: 6px;
      border: 1px solid #C1CDE5;
      background: #FFF;
    }
    .bk-select.is-focus {
      border-color: #3a84ff;
    }
}

.disabled-dialog-body {
    display: flex;
    flex-direction: column;
    gap: 16px;

    .disabled-alert {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 6px 8px;
        background: #fdf4e8;
        border: 1px solid #f9d090;
        border-radius: 2px;
        font-size: 12px;
        line-height: 20px;
        color: #4d4f56;

        .bk-icon {
            margin-top: 2px;
            font-size: 16px;
            color: #ff9c01;
        }

        .alert-title {
            margin-bottom: 2px;
        }

        ul {
            list-style: disc;
            padding-left: 18px;
        }

        b {
            font-weight: 700;
        }
    }

    .form-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
        .bk-textarea-wrapper,
        textarea,
        .bk-textarea,
        .bk-cascade-name,
        .bk-cascade-input {
            border-radius: 6px;
        }
        .bk-textarea-wrapper {
            overflow: hidden;
        }

        .form-label {
            font-size: 12px;
            line-height: 20px;
            color: #4d4f56;
        }
    }
    .replace-cascade {
        width: 100%;
        border-radius: 6px;
    }

    .dialog-tips {
        font-size: 12px;
        line-height: 20px;
        color: #979ba5;
    }
}

.disabled-cascade-popover {
    .bk-option-name {
        display: inline-flex;
        align-items: center;
        max-width: 100%;
    }

    .cascade-cate-icon {
        flex-shrink: 0;
        margin-right: 8px;
        font-size: 16px;
        color: #8f9fbd;
    }

    .cascade-cate-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .bk-cascade-panel-ul > li {
        position: relative;
    }

    .cascade-cate-divider {
        position: absolute;
        top: 0;
        left: 12px;
        right: 12px;
        height: 1px;
        background: #dcdee5;
    }
}
</style>

<style lang="scss">

.bk-options-wrapper .category-top-option {
  color: #111214;
  font-family: "PingFang SC";
}

.bk-options-wrapper .category-sub-option {
  position: relative;
  display: inline-block;
  margin-left: 6px;
  padding-left: 14px;
  color: #4E5E7A;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 1px;
    background: #dcdee5;
  }
}

.bk-options-wrapper .category-ai-option,
.bk-options-wrapper .category-uncat-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.bk-options-wrapper .category-ai-option {
  .ai-icon {
    flex-shrink: 0;
    width: 16px;
    height: 16px;
  }

  .ai-name {
    background: linear-gradient(98deg, #4667F3 3.74%, #D287EA 96.48%);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
}

.bk-options-wrapper .category-uncat-option .bk-icon {
  font-size: 14px;
}
.bk-options-wrapper li.category-option-divider {
  position: relative;
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 16px;
    right: 16px;
    height: 1px;
    background: #dcdee5;
  }
}
</style>

<style lang="scss">
.plugin-edit-dialog {
  .bk-dialog-header {
    .bk-dialog-title {
      font-size: 20px;
      line-height: 28px;
      color: #111214;
    }
  }

  .bk-dialog-body {
    padding: 0 24px 24px 24px;
  }
  .bk-dialog-content {
    border-radius: 6px;
    overflow: hidden;
  }

  .bk-dialog-footer {
    height: 48px;
    padding: 8px 24px;
    background: #f7f9fc;
    border-top: 1px solid #e9edf5;

    .bk-button {
      height: 32px;
      border-radius: 6px;
    }
  }
  .bk-select{
    border-radius: 6px;
    border: 1px solid #C1CDE5;
    background: #FFF;
  }
  .bk-select.is-focus {
    border-color: #3a84ff;
  }
  .disabled-config-form {
    .bk-textarea-wrapper {
      border-radius: 6px;
      overflow: hidden;
    }

    .replace-cascade {
      width: 100%;
      border-radius: 6px;
    }

    .dialog-tips {
      margin: 0;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }
  }
}
</style>

<style lang="scss">
.category-select-popover {
  .tippy-tooltip {
    padding: 0;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgba(25, 25, 41, 0.02);
    background-color: #fff !important;
  }
}
</style>
