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
        <span>{{ rows.length }} / {{ maxRecommend }}</span>
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
      :placeholder="$t('搜索 插件名称、类型、来源、目录、描述、最近修改人')"
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
      v-if="isInvalidTab"
      class="legacy-alert invalid-alert"
      type="warning">
      <template slot="title">
        <span>{{ $t('以下插件在来源中已不存在，本空间仍保留它们的设置记录，它们不会出现在画布面板；已有流程中的节点保持原样，能否执行取决于来源。') }}</span>
      </template>
    </bk-alert>

    <bk-alert
      v-if="isReviewTab"
      class="legacy-alert review-alert"
      type="warning">
      <template slot="title">
        <ul class="review-alert-tips">
          <li>
            {{ $t('当前新插件策略为「全部需要审核 / 设条件自动通过」，如需调整，请前往') }}
            <span class="strategy-link">{{ $t('新插件策略') }}</span>
          </li>
          <li>
            {{ $t('通过之前，请确认「目标目录」，默认是「未分类」，可手动「修改目标目录」') }}
          </li>
        </ul>
      </template>
    </bk-alert>

    <div
      v-if="hasToolbar"
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
                    {{ $t('启用后，将自动按绑定分类并设为可见') }}
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
            @click="handleBatchStatus('rejected')">
            {{ $t('批量停用') }}
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
              {{ $t('批量移动') }}
            </bk-button>
            <template slot="content">
              <category-select-panel
                :category-tree="categoryTree"
                @select="handleBatchMoveCategory" />
            </template>
          </bk-popover>
          <bk-button
            v-else
            disabled
            icon-right="icon-angle-down">
            {{ $t('批量移动') }}
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
                @select="handleBatchMoveCategory" />
            </template>
          </bk-popover>
        </template>
      </div>
    </div>

    <bk-table
      ref="pluginTable"
      v-bkloading="{ isLoading: loading || submitting }"
      :data="rows"
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
              v-if="isRecommend || row.tag === 'recommend'"
              class="plugin-tag is-recommend">{{ $t('推荐') }}</span>
            <span
              class="plugin-name"
              @click="handleNameClick(row)">{{ row.name }}</span>
          </div>
          <span v-else-if="col.id === 'type'">{{ typeText(row.type) }}</span>
          <span v-else-if="col.id === 'source'">{{ sourceText(row.source) }}</span>
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
              @show="activeCategoryPopId = row.id"
              @hide="activeCategoryPopId === row.id && (activeCategoryPopId = '')">
              <div
                :class="['category-chip', { 'is-active': activeCategoryPopId === row.id }]">
                <span>{{ categoryPath(row.category) }}</span>
              </div>
              <template slot="content">
                <category-select-panel
                  :category-tree="categoryTree"
                  :active-id="row.category"
                  :follow-source="!row.category"
                  @select="payload => handleQuickChangeCategory(row, payload.categoryId, payload.followSource)" />
              </template>
            </bk-popover>
          </div>
          <!-- 状态 -->
          <span
            v-else-if="col.id === 'status'"
            :class="['status-badge', `is-${row.status}`]">
            <i :class="['bk-icon', statusMap[row.status].icon]" />
            {{ statusMap[row.status].label }}
          </span>
          <!-- 引用流程数 -->
          <span
            v-else-if="col.id === 'refCount'"
            class="ref-count">
            {{ row.refCount }}
          </span>
          <!-- 来源入库时间 -->
          <span v-else-if="col.id === 'incomeTime'">
            {{ row.incomeTime || row.updateTime || '--' }}
          </span>
          <span v-else>{{ row[col.id] || "--" }}</span>
        </template>
      </bk-table-column>
      <!-- 空间推荐：取消推荐 + 更多（编辑 / 状态变更 / 下架配置） -->
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
              :width="78"
              :distance="4">
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
        v-else-if="!isInvalidTab"
        :label="$t('操作')"
        :width="isReviewTab ? 110 : 150"
        fixed="right">
        <template slot-scope="{ row }">
          <div class="operate-column">
            <!-- 可用：编辑 / 下架 -->
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
                @click="openOfflineDialog(row)">
                {{ $t('停用') }}
              </bk-button>
            </template>
            <template v-else-if="isReviewTab || isRejectedTab">
              <bk-popconfirm
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
                @click="handleRowStatus(row, 'rejected')">
                {{ $t('不启用') }}
              </bk-button>
              <bk-button
                v-else
                text
                theme="primary"
                @click="openOfflineConfigDialog(row)">
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
      :category-tree="categoryTree" />

    <!-- 下架确认弹窗 -->
    <bk-dialog
      v-model="offlineDialogVisible"
      ext-cls="offline-confirm-dialog"
      :width="640"
      header-position="left">
      <template slot="header">
        <div class="offline-dialog-header">
          {{ $t('确认停用 「{name}」插件？', { name: offlineRow ? offlineRow.name : '' }) }}
        </div>
      </template>
      <div
        v-if="offlineRow"
        class="offline-dialog-body">
        <!-- 下架说明 -->
        <div class="offline-alert">
          <bk-icon type="exclamation-circle" />
          <div class="alert-content">
            <p class="alert-title">
              {{ $t('停用只禁止新增使用：') }}
            </p>
            <ul>
              <li>{{ $t('已有流程中的') }} <b>{{ offlineRow.nodeCount || 0 }}</b> {{ $t('个节点照常编辑、执行，画布上标记「已下架」；') }}</li>
              <li>{{ $t('在已有流程里新增该插件的节点将无法保存，新建、复制、导入流程不受限制。') }}</li>
            </ul>
          </div>
        </div>
        <!-- 下架原因 -->
        <div class="form-item">
          <div class="form-label">
            {{ $t('停用原因（选填）') }}
          </div>
          <bk-input
            v-model="offlineForm.offlineReason"
            type="textarea"
            :rows="3"
            :maxlength="200"
            :show-word-limit="true"
            :placeholder="$t('请输入')" />
        </div>
        <!-- 替换插件 -->
        <div class="form-item">
          <div class="form-label">
            {{ $t('停用插件（选填）') }}
          </div>
          <bk-cascade
            v-model="replacePluginPath"
            class="replace-cascade"
            ext-popover-cls="offline-cascade-popover"
            :list="offlineCascadeList"
            :clearable="true"
            :placeholder="$t('请选择')">
            <!-- 各级选项前置分类图标（与侧栏目录分类一致）；末级插件无 icon 字段，不显示图标 -->
            <template
              slot="option"
              slot-scope="{ node }">
              <i
                v-if="node.icon"
                :class="['cascade-cate-icon', node.icon]" />
              <span class="cascade-cate-name">{{ node.name }}</span>
            </template>
          </bk-cascade>
        </div>
        <p class="dialog-tips">
          {{ $t('原因与停用插件会显示在画布节点提示与保存拦截提示中。') }}
          <br>
          {{ $t('不填原因时，画布/拦截统一显示「该插件已被空间管理员下架」。') }}
        </p>
      </div>
      <template slot="footer">
        <bk-button
          theme="danger"
          :outline="true"
          @click="handleOfflineConfirm">
          {{ $t('确认停用') }}
        </bk-button>
        <bk-button
          theme="default"
          @click="handleOfflineCancel">
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
                  class="info-name">{{ editingPlugin.name }}</span>
                <span
                  v-if="editingPlugin.tag === 'recommend'"
                  class="recommend-tag">推荐</span>
                <span :class="['status-badge', `is-${editingPlugin.status}`]">{{ editingStatusInfo.label }}</span>
              </div>
              <p class="info-desc">
                {{ editingPlugin.desc || '--' }}
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
                class="meta-value is-code">{{ editingPlugin.code || '--' }}</span>
            </div>
          </div>
        </section>

        <div
          v-if="isOfflineConfigMode"
          class="edit-form-area offline-config-form">
          <div class="edit-form-item">
            <div class="edit-form-label">
              {{ $t('停用原因（选填）') }}
            </div>
            <bk-input
              v-model="editForm.offlineReason"
              type="textarea"
              :rows="3"
              :maxlength="200"
              :show-word-limit="true"
              :placeholder="$t('已统一迁移到「发送通知」插件，旧机器人即将停用')" />
          </div>
          <div class="edit-form-item">
            <div class="edit-form-label">
              {{ $t('停用插件（选填）') }}
            </div>
            <bk-cascade
              v-model="replacePluginPath"
              class="replace-cascade"
              ext-popover-cls="offline-cascade-popover"
              :list="offlineCascadeList"
              :clearable="true"
              :placeholder="$t('请选择')">
              <template
                slot="option"
                slot-scope="{ node }">
                <i
                  v-if="node.icon"
                  :class="['cascade-cate-icon', node.icon]" />
                <span class="cascade-cate-name">{{ node.name }}</span>
              </template>
            </bk-cascade>
          </div>
          <p class="dialog-tips">
            {{ $t('原因与停用插件会显示在画布节点提示与保存拦截提示中。') }}
            <br>
            {{ $t('不填原因时，画布/拦截统一显示「该插件已被空间管理员下架」。') }}
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
import Sortable from 'sortablejs';
import aiBluekingIcon from '@/assets/images/ai-blueking.svg';
import useListQuery from './mixins/useListQuery';
import {
  getPluginList,
  updatePlugin,
  getRecommendList,
  saveRecommendOrder,
  cancelRecommend,
  updatePluginStatus,
} from './api';
import {
  getStatusMap,
  getStatusTabs,
  getTypeOptions,
  getSourceOptions,
  getTypeText,
  getSourceText,
  getCategoryPath,
  buildCategoryNameMap,
  getRowActions,
  getStatusChangeMessage,
  renderCategoryHeader as renderCategoryHeaderCell,
  MAX_RECOMMEND,
  CATEGORY_ICONS,
} from './shared';

// 拖拽幽灵行固定宽度（设计稿 figma 236:8851）
const GHOST_FIXED_WIDTH = 700;
// 幽灵行可见列的索引：手柄(1) / 插件(3) / 类型(4) / 所属分类(6)（与 CSS nth-child 对应）
const GHOST_VISIBLE_COLUMNS = [0, 2, 3, 5];
// 编辑弹窗「所属目录」下拉的两个固定项（仅用于下拉选择，不直接落库；口径与分类选择面板一致）
const EDIT_AI_RECOMMEND = '__ai_recommend__';
const EDIT_UNCATEGORIZED = '__uncategorized__';

export default {
  name: 'PluginList',
  components: {
    PluginDetailSlider,
    CategorySelectPanel,
    bkCascade,
  },
  mixins: [useListQuery],
  props: {
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
    // 全量插件（用于下架确认弹窗的替换插件选项）
    plugins: {
      type: Array,
      default: () => [],
    },
    // 分类原始树（用于下架确认弹窗的替换插件级联分组）
    categoryTree: {
      type: Array,
      default: () => [],
    },
    // 已推荐数量（空间推荐名额上限校验用）
    recommendTotal: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      rows: [],
      loading: false,
      statusCounts: {},
      pendingLocateTab: false,  // 仅「搜索条件变化」触发的那次请求才自动定位 Tab，避免覆盖用户手动切换的选择
      selection: [],
      isDetailSliderShow: false,
      detailPlugin: null,
      offlineDialogVisible: false,
      offlineRow: null,
      offlineForm: {
        offlineReason: '',
        replacePluginId: '',
      },
      replacePluginPath: [], // 级联选中路径（分类 → 子分类 → 插件），末级即替换插件 id
      activeCategoryPopId: '', // 面板展开中的分类 chip 所在行 id（激活态样式）
      editDialogVisible: false,
      editMode: 'edit',
      editingPlugin: null,
      editSaving: false,
      editForm: {
        category: '',
        recommended: false,
        offlineReason: '',
      },
      passRow: null,
      passCategory: '',
      activePassCategoryPop: false, // 启用至目录下拉展开态（激活触发框边框样式）
      // hideOnClick:false 保证点击目录下拉时确认气泡不关闭；onCreate 给 tooltip 根元素加类，用于清掉 tippy 自带 padding
      passTippyOptions: {
        hideOnClick: false,
        onCreate: (instance) => {
          instance.tooltip && instance.tooltip.classList.add('review-pass-tooltip');
        },
      },
      submitting: false, // 空间推荐的写操作（排序 / 取消推荐 / 状态变更）进行中
      sortable: null,
      grabPointerY: 0,
      grabRowTop: 0,
    };
  },
  computed: {
    isRecommend() {
      return this.category === 'recommend';
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
          divider: true,
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
    statusMap() {
      return getStatusMap(key => this.$t(key));
    },
    // 状态 Tab 及数量
    statusTabs() {
      return getStatusTabs(this.statusCounts, key => this.$t(key));
    },
    // 当前是否为「可用」Tab（行内：编辑 / 显示 / 下架）
    isAvailableTab() {
      return this.activeTab === 'visible';
    },
    // 当前是否为「已失效」Tab（仅展示，无选择列与操作列）
    isInvalidTab() {
      return this.activeTab === 'invalid';
    },
    // 当前是否为「待审核」Tab（批量通过 / 批量忽略 / 批量移动）
    isReviewTab() {
      return this.activeTab === 'review';
    },
    // 当前是否为「未启用」Tab（行内：启用 / 停用配置）
    isRejectedTab() {
      return this.activeTab === 'rejected';
    },
    // 已失效 / 未启用 Tab 无勾选列
    hasSelection() {
      return !this.isInvalidTab && !this.isRejectedTab;
    },
    hasToolbar() {
      return !this.isRecommend && (this.isReviewTab || this.isAvailableTab);
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
        { id: 'updatedBy', name: this.$t('最近修改人') },
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
      const incomeCol = { id: 'incomeTime', label: this.$t('来源入库时间'), width: 200, sortable: true };
      if (this.isRecommend) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('目录'), width: 250 },
          { id: 'refCount', label: this.$t('当前引用流程'), width: 130, sortable: true },
          { id: 'updatedBy', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
          { id: 'updateTime', label: this.$t('最近修改时间'), width: 200, sortable: true },
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
      if (this.isRejectedTab) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('原目录'), width: 250 },
          { id: 'refCount', label: this.$t('当前引用流程'), width: 130, sortable: true },
          { id: 'updatedBy', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
          { id: 'updateTime', label: this.$t('最近修改时间'), width: 200, sortable: true },
          // incomeCol,
          statusCol,
        ];
      }
      if (this.isInvalidTab) {
        return [
          { id: 'name', label: this.$t('插件'), width: 250 },
          typeCol,
          sourceCol,
          { id: 'category', label: this.$t('原所属目录'), width: 250 },
          { id: 'refCount', label: this.$t('当前引用流程'), width: 130, sortable: true },
          // { id: 'invalidReason', label: this.$t('失效原因'), width: 250 },
          { id: 'foundTime', label: this.$t('发现时间'), width: 200, sortable: true },
          statusCol,
        ];
      }
      return [
        { id: 'name', label: this.$t('插件'), width: 250 },
        typeCol,
        sourceCol,
        { id: 'category', label: this.$t('目录'), width: 250 },
        { id: 'refCount', label: this.$t('当前引用流程'), width: 130, sortable: true },
        { id: 'updatedBy', label: this.$t('最近修改人'), width: 200, filters: this.updatedByFilters, filterMethod: this.filterMethod },
        { id: 'updateTime', label: this.$t('最近修改时间'), width: 200, sortable: true },
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
      return [...new Set(this.rows.map(row => row.updatedBy).filter(Boolean))]
        .map(name => ({ text: name, value: name }));
    },
    // 启用至目录：当前选中分类的显示名（空串回落「未分类」占位）
    passCategoryLabel() {
      return buildCategoryNameMap(this.categoryTree)[this.passCategory] || '';
    },
    // 待审核确认气泡中的选中插件文案
    reviewSelectedNames() {
      if (this.selection.length === 1) return this.selection[0].name;
      return this.$t('已选 {count} 项', { count: this.selection.length });
    },
    cascadeSourcePlugin() {
      if (this.editDialogVisible && this.isOfflineConfigMode) return this.editingPlugin;
      return this.offlineRow;
    },
    offlineCascadeList() {
      const self = this.cascadeSourcePlugin;
      if (!self) return [];
      const candidates = (this.plugins || []).filter(item => item.id !== self.id);
      const toLeaf = item => ({ id: item.id, name: item.name });
      const byCategory = {};
      candidates.forEach((item) => {
        const key = item.category || '';
        byCategory[key] = byCategory[key] || [];
        byCategory[key].push(item);
      });
      return [
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
      return this.editingPlugin ? (this.statusMap[this.editingPlugin.status] || {}) : {};
    },
    editingTypeText() {
      return this.editingPlugin ? getTypeText(this.editingPlugin.type, key => this.$t(key)) : '--';
    },
    editingSourceText() {
      return this.editingPlugin ? getSourceText(this.editingPlugin.source, key => this.$t(key)) : '--';
    },
    editingLogoText() {
      return this.editingPlugin && this.editingPlugin.name ? this.editingPlugin.name.trim().charAt(0) : '';
    },
    isOfflineConfigMode() {
      return this.editMode === 'offline-config';
    },
    editDialogTitle() {
      return this.isOfflineConfigMode ? this.$t('停用配置') : this.$t('编辑插件');
    },
    // 只有「可用」插件可新设为推荐；其余状态一律置灰（已推荐的仍需允许关闭以释放名额）
    editRecommendDisabled() {
      return !!this.editingPlugin && this.editingPlugin.status !== 'visible' && !this.editForm.recommended;
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
    rows() {
      this.$nextTick(this.initSortable);
    },
    'editForm.category'(val, oldVal) {
      if (val !== EDIT_AI_RECOMMEND) return;
      this.$bkMessage({ message: this.$t('功能建设中，敬请期待'), theme: 'warning' });
      this.$nextTick(() => {
        this.editForm.category = oldVal === undefined ? '' : oldVal;
      });
    },
  },
  mounted() {
    this.fetchList();
  },
  beforeDestroy() {
    this.destroySortable();
  },
  methods: {
    handleSearchChange(values) {
      this.searchValues = (values || []).map(item => ({ ...item }));
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
        const { count, results, status_counts: statusCounts } = await getPluginList({
          spaceId: this.spaceId,
          ...this.queryParams,
        });
        this.rows = results;
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
        const { results } = await getRecommendList({ spaceId: this.spaceId });
        this.rows = results;
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
    // 列头筛选
    filterMethod(value, row, column) {
      const { property } = column;
      return row[property] === value;
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
      if (!this.rows.length || !leafCategories.length) return;
      this.rows.forEach((row) => {
        const categoryId = leafCategories[Math.floor(Math.random() * leafCategories.length)];
        this.$emit('category-change', { row, categoryId, followSource: false });
      });
    },
    handleSelectionChange(selection) {
      this.selection = selection;
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
      this.$emit('category-change', { row, categoryId, followSource });
    },
    // 批量移动
    handleBatchMoveCategory({ categoryId, followSource }) {
      const popRef = this.$refs.batchMovePopover;
      if (popRef) {
        popRef.hideHandler();
      }
      this.$emit('batch-category-change', { rows: [...this.selection], categoryId, followSource });
    },
    handleRowStatus(row, status, message) {
      this.$emit('status-change', { row, status, message });
    },
    handlePassClick(row) {
      this.passRow = row;
      this.passCategory = row.category || '';
    },
    // AI 推荐目标目录
    handlePassAiRecommend() {
      const leafCategories = [];
      (this.categoryTree || []).forEach((group) => {
        leafCategories.push(group.id);
        (group.children || []).forEach(child => leafCategories.push(child.id));
      });
      if (!leafCategories.length) return;
      this.passCategory = leafCategories[Math.floor(Math.random() * leafCategories.length)];
    },
    // 「启用至目录」面板选择：AI 推荐随机取叶子分类，其余直接回写；选中后收起下拉
    handlePassCategorySelect({ categoryId, isAiRecommend }) {
      if (isAiRecommend) {
        this.handlePassAiRecommend();
      } else {
        this.passCategory = categoryId;
      }
      this.hidePassCategoryPop();
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
      this.$emit('status-change', {
        row,
        status: 'visible',
        category: this.passCategory || '',
        message: this.$t('已通过审核'),
      });
    },
    buildCategoryNode(cate, byCategory, toLeaf) {
      const children = [];
      ((cate && cate.children) || []).forEach((sub) => {
        children.push({
          id: sub.id,
          name: sub.name,
          icon: CATEGORY_ICONS.level2,
          children: (byCategory[sub.id] || []).map(toLeaf),
        });
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
    // 打开下架确认弹窗
    openOfflineDialog(row) {
      this.offlineRow = row;
      this.offlineForm = { offlineReason: '', replacePluginId: '' };
      this.replacePluginPath = [];
      this.offlineDialogVisible = true;
    },
    handleOfflineCancel() {
      this.offlineDialogVisible = false;
    },
    // 确认停用：携带停用原因与替换插件一并提交（级联末级即插件 id），停用后插件进入「未启用」
    handleOfflineConfirm() {
      this.$emit('status-change', {
        row: this.offlineRow,
        status: 'rejected',
        offlineReason: this.offlineForm.offlineReason,
        replacePluginId: this.replacePluginId,
        message: this.$t('已停用'),
      });
      this.offlineDialogVisible = false;
    },

    // 批量状态变更
    handleBatchStatus(status) {
      if (!this.selection.length) return;
      this.$emit('batch-status-change', { rows: [...this.selection], status });
    },
    // 待审核批量通过
    handleBatchReviewPass() {
      if (!this.selection.length) return;
      this.$emit('batch-status-change', {
        rows: [...this.selection],
        status: 'visible',
        message: this.$t('已通过审核'),
      });
    },
    handleOpenDetail(row) {
      this.detailPlugin = row;
      this.isDetailSliderShow = true;
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
      if (action.type === 'offline-config') {
        this.openOfflineConfigDialog(row);
        return;
      }
      const target = this.rows.find(item => item.id === row.id);
      const prevStatus = target ? target.status : '';
      await this.submit(async () => {
        await updatePluginStatus({ spaceId: this.spaceId, pluginId: row.id, status: action.status });
        if (target) {
          target.status = action.status;
        }
        this.$bkMessage({
          message: action.message || getStatusChangeMessage(action.status, key => this.$t(key)),
          theme: 'success',
        });
        // 状态变化可能改变推荐名额占用，通知父组件刷新概要
        this.$emit('recommend-changed');
      }, () => {
        if (target) {
          target.status = prevStatus;
        }
      });
    },
    // 取消推荐：立即生效并释放名额，无需二次确认
    async handleCancelRecommend(row) {
      await this.submit(async () => {
        await cancelRecommend({ spaceId: this.spaceId, pluginId: row.id });
        this.rows = this.rows.filter(item => item.id !== row.id);
        this.$bkMessage({
          message: this.$t('已取消推荐'),
          theme: 'success',
        });
        this.$emit('recommend-changed');
      });
    },
    // 统一处理空间推荐的写操作：进行中置 submitting，失败提示并回滚
    async submit(request, rollback) {
      this.submitting = true;
      try {
        await request();
      } catch (e) {
        if (rollback) rollback();
        this.$bkMessage({
          message: this.$t('操作失败，请重试'),
          theme: 'error',
        });
      } finally {
        this.submitting = false;
      }
    },
    // 在表格 tbody 上挂载行拖拽：仅手柄可发起，蓝色插入线标落点，幽灵行跟随指针
    initSortable() {
      this.destroySortable();
      if (!this.isRecommend) return;
      const tableEl = this.$refs.pluginTable;
      const tbody = tableEl && tableEl.$el ? tableEl.$el.querySelector('tbody') : null;
      if (!tbody) return;
      this.sortable = new Sortable(tbody, {
        handle: '.drag-handle',
        animation: 150,
        // 用 fallback 模式呈现设计稿的「幽灵行跟随指针」效果
        forceFallback: true,
        fallbackClass: 'recommend-ghost-row',
        ghostClass: 'recommend-insert-line',
        onStart: this.handleDragStart,
        onEnd: this.handleSortEnd,
      });
      // 捕获阶段记录按下时指针相对所在行的纵向偏移——onStart 触发时原行已被压缩成
      // 3px 插入线，拿不到原始行位置，必须在 mousedown 阶段先记下来
      tbody.addEventListener('mousedown', this.recordGrabOffset, true);
    },
    recordGrabOffset(e) {
      const tr = e.target && e.target.closest ? e.target.closest('tr') : null;
      if (tr) {
        this.grabPointerY = e.clientY;
        this.grabRowTop = tr.getBoundingClientRect().top;
      }
    },
    handleDragStart() {
      // 拖拽进行中将光标换成四向移动图标
      document.body.classList.add('recommend-row-dragging');
      const grabOffset = Math.min(Math.max((this.grabPointerY || 0) - (this.grabRowTop || 0), 0), 42);
      let tries = 0;
      const applyGhostStyle = () => {
        const ghost = document.querySelector('.recommend-ghost-row');
        if (!ghost) return false;
        // 高度固定 42（覆盖 Sortable 从原行拷贝的内联高度）
        ghost.style.height = '42px';
        // 固定宽度 + 四列按内容自适应
        const cells = Array.from(ghost.children);
        const visibleCells = GHOST_VISIBLE_COLUMNS.map(i => cells[i]).filter(Boolean);
        ghost.style.tableLayout = 'auto';
        ghost.style.width = 'auto';
        const contentWidths = visibleCells.map(cell => cell.offsetWidth);
        // 内容本身超过固定宽度时以内容为准，否则末列会被压没
        const contentTotal = contentWidths.reduce((sum, w) => sum + w, 0);
        ghost.style.tableLayout = 'fixed';
        ghost.style.width = `${Math.max(GHOST_FIXED_WIDTH, contentTotal)}px`;
        contentWidths.forEach((width, i) => {
          // 最后一列留空不设宽，用来吸收剩余空间
          if (i < visibleCells.length - 1) {
            visibleCells[i].style.width = `${width}px`;
          } else {
            visibleCells[i].style.width = '';
          }
        });
        // 垂直居中修正：ghost 的 top 是 Sortable 挂载时写死的，后续移动只改 transform，
        // 这里改 top 加一个固定偏移量即可全程生效（偏移 = 幽灵行半高 - 抓取偏移）
        const ghostTop = parseFloat(getComputedStyle(ghost).top);
        if (!Number.isNaN(ghostTop)) {
          ghost.style.top = `${ghostTop + (ghost.offsetHeight / 2) - grabOffset}px`;
        }
        return true;
      };
      const timer = setInterval(() => {
        if (applyGhostStyle() || (tries += 1) > 60) {
          clearInterval(timer);
        }
      }, 16);
    },
    clearHoverRows() {
      const tableEl = this.$refs.pluginTable;
      const tbody = tableEl && tableEl.$el ? tableEl.$el.querySelector('tbody') : null;
      if (!tbody) return;
      tbody.querySelectorAll('tr.hover-row').forEach(row => row.classList.remove('hover-row'));
    },
    destroySortable() {
      if (this.sortable) {
        this.sortable.destroy();
        this.sortable = null;
        // 兜底：拖拽被外力中断（如组件销毁）时 body 标记类不会走 onEnd，这里补清理
        document.body.classList.remove('recommend-row-dragging');
        const tableEl = this.$refs.pluginTable;
        const tbody = tableEl && tableEl.$el ? tableEl.$el.querySelector('tbody') : null;
        if (tbody) {
          tbody.removeEventListener('mousedown', this.recordGrabOffset, true);
        }
      }
    },
    // 拖拽结束：先还原 Sortable 对真实 DOM 的改动，再按数据重排
    async handleSortEnd(evt) {
      document.body.classList.remove('recommend-row-dragging');
      const { item, oldIndex, newIndex } = evt;
      if (item && item.parentNode && oldIndex !== undefined && newIndex !== undefined && oldIndex !== newIndex) {
        const parent = item.parentNode;
        const refNode = oldIndex > newIndex
          ? parent.children[oldIndex + 1]
          : parent.children[oldIndex];
        parent.insertBefore(item, refNode || null);
      }
      // 清理拖拽期间残留的行 hover 类
      this.clearHoverRows();
      // 清理 fallback 拖拽期间按住移动拉出的文本选区
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
      }
      if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return;
      const prevRows = [...this.rows];
      const nextRows = [...this.rows];
      const [moved] = nextRows.splice(oldIndex, 1);
      nextRows.splice(newIndex, 0, moved);
      this.rows = nextRows;
      // Vue 按新数据重渲染后再清一次：上一轮清理可能发生在重渲染之前
      this.$nextTick(this.clearHoverRows);
      await this.submit(async () => {
        await saveRecommendOrder({ spaceId: this.spaceId, ids: nextRows.map(item => item.id) });
        this.$bkMessage({
          message: this.$t('顺序修改成功'),
          theme: 'success',
        });
      }, () => {
        this.rows = prevRows;
      });
    },
    openEditDialog(row) {
      this.editingPlugin = row;
      this.editMode = 'edit';
      this.editForm = {
        category: row.category || EDIT_UNCATEGORIZED,
        recommended: !!row.recommended,
        offlineReason: '',
      };
      this.replacePluginPath = [];
      this.editDialogVisible = true;
    },
    // 打开下架配置弹窗
    openOfflineConfigDialog(row) {
      this.editingPlugin = row;
      this.editMode = 'offline-config';
      this.editForm = {
        category: row.category || '',
        recommended: !!row.recommended,
        offlineReason: row.offlineReason || '',
      };
      this.editDialogVisible = true;
      this.replacePluginPath = this.findCascadePath(this.offlineCascadeList, row.replacePluginId);
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
      if (this.isOfflineConfigMode) {
        this.editSaving = true;
        try {
          await updatePlugin({
            spaceId: this.spaceId,
            pluginId: this.editingPlugin.id,
            data: {
              category: this.editingPlugin.category || '',
              recommended: !!this.editingPlugin.recommended,
              offlineReason: this.editForm.offlineReason,
              replacePluginId: this.replacePluginId,
            },
          });
          this.$bkMessage({
            message: this.$t('保存成功'),
            theme: 'success',
          });
          this.editDialogVisible = false;
          this.reload();
          this.$emit('edit-saved');
        } catch (e) {
          this.$bkMessage({
            message: this.$t('操作失败，请重试'),
            theme: 'error',
          });
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
        await updatePlugin({
          spaceId: this.spaceId,
          pluginId: this.editingPlugin.id,
          data: {
            // 「未分类」用哨兵 id 参与选择与必填校验，提交时还原为空 category
            category: this.editForm.category === EDIT_UNCATEGORIZED ? '' : this.editForm.category,
            recommended: this.editForm.recommended,
          },
        });
        this.$bkMessage({
          message: this.$t('保存成功'),
          theme: 'success',
        });
        this.editDialogVisible = false;
        this.reload();
        // 推荐名额 / 分类计数可能变化，通知父组件刷新概要
        this.$emit('edit-saved');
        if (this.isRecommend) {
          this.$emit('recommend-changed');
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

  &.is-visible {
      color: #1D8F70;
      background: #E1F5F0;
  }
  &.is-review {
    color: #f59500;
    background-color: #FFEDD1;
  }

  &.is-invalid,
  &.is-rejected {
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

  ::v-deep .recommend-table {」
    th,
    td {
      user-select: none;
    }

    th:first-child .cell,
    td:first-child .cell {
      padding: 0 12px;
      overflow: visible;
      text-overflow: clip;
      white-space: nowrap;
    }

    .drag-handle {
      font-size: 16px;
      color: #979ba5;
      cursor: grab;

      &:hover {
        color: #3a84ff;
      }
    }

    tr.recommend-insert-line {
      background: #3a84ff;

      td {
        height: 3px;
        padding: 0;
        border: none;
        background: #3a84ff !important;
        font-size: 0;
        line-height: 0;
      }

      .cell {
        display: none;
      }
    }
S 设置
    tr.recommend-ghost-row {
      display: table;
      border-collapse: separate;
      border-spacing: 0;
      // 不拦截指针事件：避免幽灵行挡住底下行的 hover 高亮
      pointer-events: none;
      opacity: 1 !important;
      background: #f0f5ff !important;
      border: 2px solid #3a84ff;
      border-radius: 4px;
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.18);
      cursor: grabbing;

      td {
        background: #f0f5ff !important;
        border: none !important;
        padding: 0 16px;
        vertical-align: middle;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;

        .cell {
          padding: 0;
        }
      }
      td {
        display: none;
      }

      td:nth-child(1),
      td:nth-child(3),
      td:nth-child(4),
      td:nth-child(6) {
        display: table-cell;
      }

      .drag-handle {
        color: #3a84ff;
      }
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
        border-radius: 8px;
        font-size: 10px;
        line-height: 16px;
        flex-shrink: 0;

        &.is-visible {
          color: #1d8f70;
          background: #e1f5f0;
        }

        &.is-review {
          background: #fff4e2;
          color: #ff9c01;
        }

        &.is-invalid {
          background: #f0f1f5;
          color: #979ba5;
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
.offline-confirm-dialog {
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
    .offline-alert {
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

.offline-dialog-body {
    display: flex;
    flex-direction: column;
    gap: 16px;

    .offline-alert {
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

.offline-cascade-popover {
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

    > .bk-cascade-options > .bk-cascade-panel:first-child > .bk-cascade-panel-ul > li:nth-child(4) {
        position: relative;

        &::before {
            content: '';
            position: absolute;
            top: 0;
            left: 12px;
            right: 12px;
            height: 1px;
            background: #dcdee5;
        }
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
  border-bottom: 1px solid #dcdee5;
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
  .offline-config-form {
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
body.recommend-row-dragging,
body.recommend-row-dragging * {
  cursor: url("data:image/svg+xml,%3Csvg width='32' height='32' viewBox='0 0 32 32' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M16.0003 3L10.5835 8.41667H14.9164V14.9167H8.41678V10.5828L3 15.9995L8.41678 21.4161V17.0833H14.9164V23.5833H10.5835L16.0003 29L21.417 23.5833H17.0836V17.0833H23.5832V21.4161L29 15.9995L23.5832 10.5828V14.9167H17.0836V8.41667H21.417L16.0003 3Z' fill-rule='evenodd' clip-rule='evenodd' fill='%234D4F56'/%3E%3C/svg%3E") 16 16, move !important;
}

body.recommend-row-dragging
  .recommend-table
  tbody
  tr.hover-row:not(.recommend-insert-line):not(.recommend-ghost-row)
  > td {
  background-color: #fff !important;
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
