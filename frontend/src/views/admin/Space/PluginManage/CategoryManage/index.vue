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
  <div
    v-bkloading="{ isLoading: loading, opacity: 1 }"
    class="category-manage">
    <header class="page-header">
      <div
        class="header-left">
        <i
          class="bk-icon icon-arrows-left back-icon"
          @click="handleBack" />
        <span class="page-title">{{ $t('目录批量管理') }}</span>
      </div>
      <div class="header-right">
        <bk-button
          theme="primary"
          class="header-btn"
          :loading="saving"
          @click="handleSave">
          {{ $t('保存') }}
        </bk-button>
        <bk-button
          class="header-btn"
          @click="handleBack">
          {{ $t('取消') }}
        </bk-button>
      </div>
    </header>

    <div class="page-main">
      <div class="manage-card">
        <div class="manage-alert">
          <i class="commonicon-icon common-icon-yuan-jinggao alert-icon" />
          <ul class="alert-list">
            <li>{{ $t('支持手动拖拽移动插件和目录（但注意最多只有 2 层目录，含有子目录的目录不能再移动到别的目录下）') }}</li>
            <li>{{ $t('支持多选插件、目录，选择「移动至...」') }}</li>
            <li>{{ $t('也可以用自然语言「AI 智能分类」') }}</li>
          </ul>
        </div>
        <div class="manage-toolbar">
          <bk-popover
            ref="aiPopover"
            trigger="manual"
            placement="bottom-start"
            theme="light"
            ext-cls="ai-classify-popover ai-classify-tippy"
            :arrow="false"
            :tippy-options="{ duration: 0 }"
            width="400"
            @show="handleAiPanelShow">
            <div slot="content">
              <textarea
                ref="aiTextarea"
                v-model="aiPrompt"
                class="ai-textarea"
                :disabled="aiSmartLoading"
                :placeholder="$t('(选填) 请用自然语言描述分类需求...')"
                @keydown.enter.exact.prevent="submitAiClassify" />
              <div class="panel-footer">
                <div
                  :class="['ai-submit-btn', { 'is-active': !!aiPrompt.trim()}]"
                  :title="$t('提交')"
                  @click="submitAiClassify">
                  <bk-icon
                    type="arrows-up" />
                </div>
              </div>
            </div>
            <bk-button
              class="ai-btn"
              @click="showAiPanel">
              <i class="commonicon-icon common-icon-ai-meihua" />
              <span>{{ $t('AI 智能分类') }}</span>
            </bk-button>
          </bk-popover>
          <bk-button
            class="tool-btn"
            theme="primary"
            :outline="true"
            @click="handleCreateCategory('')">
            <i class="bk-icon icon-plus btn-icon" />
            {{ $t('新建目录') }}
          </bk-button>
          <bk-button
            class="tool-btn"
            theme="primary"
            :outline="true"
            @click="handleCreateCategory(isUncategorized ? '' : selectedLevel1Id, 'child')">
            <i class="bk-icon icon-plus btn-icon" />
            {{ $t('新建子目录') }}
          </bk-button>
          <span class="tool-divider" />
          <!-- 目录管理与插件列表的移动规则不同，按勾选内容收敛可选范围（见 moveSelectableLevel 等计算属性）：
               只勾插件 → 未分类 + AI 分类 + 一级/二级目录；
               含二级目录 → AI 分类 + 一级目录（二级只能放进一级，目录不能到未分类）；
               含一级目录的混勾 → 勾到含子目录的目录时整个按钮禁用 -->
          <span
            v-bk-tooltips="{ content: $t('勾选了含有子目录的目录，无法移动至其他目录'), disabled: !moveBlocked }"
            class="move-btn-wrap">
            <bk-popover
              ref="movePopover"
              trigger="click"
              theme="light"
              placement="bottom-start"
              ext-cls="category-select-popover"
              :width="280"
              :arrow="false"
              :transfer="true"
              :disabled="moveDisabled">
              <bk-button
                class="tool-btn"
                theme="primary"
                :outline="true"
                :disabled="moveDisabled">
                <i class="bk-icon icon-plus btn-icon" />
                {{ $t('移动至...') }}
              </bk-button>
              <template slot="content">
                <category-select-panel
                  :category-tree="categories"
                  :selectable-level="moveSelectableLevel"
                  :show-unclassified="moveShowUnclassified"
                  :exclude-ids="moveExcludeIds"
                  @select="handleMoveTo" />
              </template>
            </bk-popover>
          </span>
          <span class="tool-divider" />
          <span
            v-bk-tooltips="{ content: $t('无法在目录管理处删除插件'), disabled: !deleteDisabled }"
            class="del-btn-wrap">
            <bk-button
              class="tool-btn"
              theme="primary"
              :outline="true"
              :disabled="deleteDisabled"
              @click="handleDeleteChecked">
              <i class="commonicon-icon common-icon-delete del-icon" />
              {{ $t('删除') }}
            </bk-button>
          </span>
          <div
            ref="searchLocate"
            class="toolbar-search">
            <bk-input
              v-model="keyword"
              :clearable="true"
              right-icon="bk-icon icon-search"
              :placeholder="$t('搜索 目录名、插件名')"
              @focus="isSearchPanelShow = !!trimKeyword"
              @click.native="isSearchPanelShow = !!trimKeyword" />
            <div
              v-if="isSearchPanelShow && searchResults.length"
              class="search-dropdown">
              <div
                v-for="item in searchResults"
                :key="`${item.type}-${item.id}`"
                class="search-option"
                @mousedown.prevent="handleLocate(item)">
                <i :class="['option-icon', optionIconCls(item)]" />
                <div class="option-text">
                  <p class="option-name">
                    <span
                      v-for="(seg, index) in highlightName(item.name)"
                      :key="index"
                      :class="{ 'option-hit': seg.hit }">{{ seg.text }}</span>
                  </p>
                  <p class="option-path">
                    {{ item.path }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 三栏：一级目录 | 二级目录（子目录 + 直属插件）-->
        <div
          v-bkloading="{ isLoading: aiSmartLoading, title: $t('AI 智能分类中'), opacity: 1, color: '#fff' }"
          class="manage-columns">
          <!-- 一级目录 -->
          <section class="column">
            <header class="column-header">
              <span class="column-title">{{ $t('一级目录') }}</span>
              <span class="column-meta">
                <b>{{ filteredLevel1.length }}</b> {{ $t('个目录') }}
              </span>
            </header>
            <div
              :class="['column-body', columnBodyCls('level1')]"
              data-col-key="level1">
              <div
                :class="['cate-row', rowStateCls('uncategorized', 'plugin'), { 'is-active': selectedLevel1Id === 'uncategorized' }]"
                data-dnd-type="uncat"
                @click="onSelectLevelOne('uncategorized')">
                <span
                  class="row-checkbox uncategorized-checkbox"
                  @click.stop>
                  <bk-checkbox
                    :value="false"
                    :disabled="true" />
                </span>
                <i :class="['row-icon', 'commonicon-icon common-icon-file-open-dakaiwenjianjia']" />
                <span
                  v-bk-overflow-tips
                  class="row-name">{{ $t('未分类插件') }}</span>
                <span class="row-count-tag">{{ uncategorizedPlugins.length }}</span>
                <i class="bk-icon icon-angle-right row-arrow" />
              </div>
              <div class="row-divider" />
              <div
                v-for="cate in filteredLevel1"
                :key="cate.id"
                :data-locate-id="cate.id"
                data-dnd-type="dir"
                :class="['cate-row', rowStateCls(cate.id, 'dir'), { 'is-active': selectedLevel1Id === cate.id, 'is-flash': flashType === 'level1' && flashId === cate.id }]"
                @click="onSelectLevelOne(cate.id)"
                @mousedown="handleRowDragMousedown(cate.id, 'dir', $event)">
                <i class="commonicon-icon common-icon-drawable" />
                <span
                  class="row-checkbox"
                  @click.stop>
                  <bk-checkbox
                    :value="checkedCateIds.includes(cate.id)"
                    @change="toggleCateChecked(cate.id)" />
                </span>
                <i :class="['row-icon', 'commonicon-icon common-icon-file-open-dakaiwenjianjia']" />
                <span
                  v-bk-overflow-tips
                  class="row-name">{{ cate.name }}</span>
                <span class="row-count-tag">{{ level1PluginCount(cate) }}</span>
                <i class="bk-icon icon-angle-right row-arrow" />
              </div>
            </div>
          </section>

          <!-- 二级目录（子目录 + 直属插件） -->
          <section class="column">
            <header class="column-header">
              <span class="column-title">{{ secondTitle }}</span>
              <span class="column-meta">
                <template v-if="!isUncategorized && secondDirectories.length">
                  <b>{{ secondDirectories.length }}</b> {{ $t('个目录') }} ·
                </template>
                <b>{{ secondPlugins.length }}</b> {{ $t('个插件') }}
              </span>
            </header>
            <div
              :class="['column-body', columnBodyCls('second')]"
              data-col-key="second">
              <template v-if="secondDirectories.length || secondPlugins.length">
                <div
                  v-for="sub in secondDirectories"
                  :key="`dir-${sub.id}`"
                  :data-locate-id="sub.id"
                  data-dnd-type="dir"
                  :class="['cate-row', rowStateCls(sub.id, 'dir'), { 'is-active': selectedSecondId === sub.id, 'is-flash': flashType === 'level2' && flashId === sub.id }]"
                  @click="onSelectSecond(sub)"
                  @mousedown="handleRowDragMousedown(sub.id, 'dir', $event)">
                  <i class="commonicon-icon common-icon-drawable" />
                  <span
                    class="row-checkbox"
                    @click.stop>
                    <bk-checkbox
                      :value="checkedCateIds.includes(sub.id)"
                      @change="toggleCateChecked(sub.id)" />
                  </span>
                  <i :class="['row-icon', 'commonicon-icon common-icon-file-open-dakaiwenjianjia']" />
                  <span
                    v-bk-overflow-tips
                    class="row-name">{{ sub.name }}</span>
                  <span class="row-count-tag">{{ pluginCountById(sub.id) }}</span>
                  <i class="bk-icon icon-angle-right row-arrow" />
                </div>
                <div
                  v-for="plugin in secondPlugins"
                  :key="`plugin-${plugin.id}`"
                  :data-locate-id="plugin.id"
                  data-dnd-type="plugin"
                  :class="['cate-row', rowStateCls(plugin.id, 'plugin'), { 'is-flash': flashType === 'plugin' && flashId === plugin.id }]"
                  @click="togglePluginChecked(plugin.id)"
                  @mousedown="handleRowDragMousedown(plugin.id, 'plugin', $event)">
                  <i class="commonicon-icon common-icon-drawable" />
                  <span
                    class="row-checkbox"
                    @click.stop>
                    <bk-checkbox
                      :value="checkedPluginIds.includes(plugin.id)"
                      @change="togglePluginChecked(plugin.id)" />
                  </span>
                  <i class="row-icon commonicon-icon common-icon-plugin-chajian is-plugin" />
                  <span
                    v-bk-overflow-tips
                    class="row-name">{{ plugin.plugin_name }}</span>
                </div>
              </template>
              <bk-exception
                v-else
                class="column-empty"
                type="empty"
                scene="part" />
            </div>
          </section>

          <!-- 插件（选中二级目录下的插件） -->
          <section class="column is-last">
            <header class="column-header">
              <span class="column-title">{{ thirdTitle }}</span>
              <span
                v-if="thirdTitle"
                class="column-meta">
                <b>{{ thirdPlugins.length }}</b> {{ $t('个插件') }}
              </span>
            </header>
            <div
              :class="['column-body', columnBodyCls('third')]"
              data-col-key="third">
              <template v-if="thirdPlugins.length">
                <div
                  v-for="plugin in thirdPlugins"
                  :key="plugin.id"
                  :data-locate-id="plugin.id"
                  data-dnd-type="plugin"
                  :class="['cate-row', rowStateCls(plugin.id, 'plugin'), { 'is-flash': flashType === 'plugin' && flashId === plugin.id }]"
                  @click="togglePluginChecked(plugin.id)"
                  @mousedown="handleRowDragMousedown(plugin.id, 'plugin', $event)">
                  <i class="commonicon-icon common-icon-drawable" />
                  <span
                    class="row-checkbox"
                    @click.stop>
                    <bk-checkbox
                      :value="checkedPluginIds.includes(plugin.id)"
                      @change="togglePluginChecked(plugin.id)" />
                  </span>
                  <i class="row-icon commonicon-icon common-icon-plugin-chajian is-plugin" />
                  <span
                    v-bk-overflow-tips
                    class="row-name">{{ plugin.plugin_name }}</span>
                </div>
              </template>
              <bk-exception
                v-else
                class="column-empty"
                type="empty"
                scene="part" />
            </div>
          </section>
        </div>

        <!-- 拖拽光标 -->
        <div
          v-show="dnd.active"
          ref="dragCursor"
          class="drag-cursor">
          <i class="commonicon-icon common-icon-guangbiao-tuodong" />
        </div>
        <!-- 拖拽 ghost -->
        <div
          v-show="dnd.active && dndGhost"
          ref="dragGhost"
          class="drag-ghost">
          <template v-if="dndGhost">
            <span
              v-if="dndGhost.count > 1"
              class="ghost-count">{{ dndGhost.count }}</span>
            <i :class="['ghost-icon', dndGhost.type === 'plugin' ? 'commonicon-icon common-icon-plugin-chajian is-plugin' : 'commonicon-icon common-icon-file-open-dakaiwenjianjia']" />
            <span class="ghost-name">{{ dndGhost.name }}<template v-if="dndGhost.count > 1"> {{ $t('等') }}</template></span>
          </template>
        </div>
        <div
          v-if="denyTip"
          class="drag-deny-tip"
          :style="{ top: `${denyTip.top}px`, left: `${denyTip.left}px` }">
          {{ denyTip.text }}
        </div>
      </div>
    </div>
    <!-- 新建目录/新建子目录 -->
    <bk-dialog
      v-model="createDialogVisible"
      theme="primary"
      width="480"
      ext-cls="create-dialog"
      header-position="left"
      :title="createDialogTitle"
      @confirm="confirmCreateCategory">
      <bk-form
        ref="createFormRef"
        form-type="vertical"
        :model="createForm"
        :rules="createRules">
        <bk-form-item
          v-if="createMode === 'child'"
          :label="$t('所属目录')"
          :required="true"
          property="parentId"
          error-display-type="normal">
          <bk-select
            v-model="createForm.parentId"
            :clearable="false"
            :placeholder="$t('请选择')">
            <bk-option
              v-for="item in categories"
              :id="item.id"
              :key="item.id"
              :name="item.name" />
          </bk-select>
        </bk-form-item>
        <bk-form-item
          :label="$t('目录名称')"
          :required="true"
          property="name"
          error-display-type="normal">
          <bk-input
            v-model.trim="createForm.name"
            :maxlength="32"
            :placeholder="$t('请输入')" />
        </bk-form-item>
      </bk-form>
    </bk-dialog>

    <bk-dialog
      v-model="deleteDialogVisible"
      width="478"
      header-position="left"
      ext-cls="delete-confirm-dialog"
      :title="deleteDialogTitle">
      <p class="delete-desc">
        <span>{{ $t('请确认删除后的改动，是否符合预期？') }}</span>
        <span>{{ $t('如果不符合预期，请先手动移动 / 智能分类') }}</span>
      </p>
      <div
        v-bkloading="{ isLoading: deleteImpactLoading, opacity: 1 }"
        class="impact-loading-wrap">
        <div
          v-for="cate in deleteImpactItems"
          :key="cate.id"
          class="impact-block">
          <p
            v-if="isMultiCategoryDelete"
            class="impact-cate-name">
            {{ cate.name }}{{ $t('目录：') }}
          </p>
          <bk-table
            class="impact-table"
            :data="impactRows(cate)">
            <bk-table-column
              :label="$t('子对象')"
              width="220">
              <template slot-scope="{ row }">
                <span class="impact-num">{{ row.count }}</span>
                <span class="impact-unit"> {{ row.unit }}</span>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('删除后的改动')"
              prop="change" />
          </bk-table>
        </div>
      </div>
      <template slot="footer">
        <bk-button
          theme="danger"
          @click="confirmDeleteChecked">
          {{ $t('确认删除') }}
        </bk-button>
        <bk-button
          @click="deleteDialogVisible = false">
          {{ $t('关闭') }}
        </bk-button>
      </template>
    </bk-dialog>
  </div>
</template>

<script>
import { mapActions, mapState } from 'vuex';
import CategorySelectPanel from '../CategorySelectPanel.vue';

import { matchPluginCategory } from '../shared';
import {
  resolveDragGroup,
  resolveRowIntent,
  findCateInfo,
  isDescendantCategory,
  getMovingCateInfos,
  validateDrop,
  reorderPlugins,
  reorderMixedColumn,
} from '../dragRules';

const UNCLASSIFIED = 'uncategorized';

export default {
  name: 'CategoryManage',
  components: {
    CategorySelectPanel,
  },
  data() {
    return {
      loading: true,
      saving: false,
      categories: [],
      plugins: [],
      // 拉取时的插件归属快照（pluginId -> directory_id），保存时用于 diff 出变化项
      originalAssignments: {},
      // 整页数据版本号
      manageRevision: null,
      // 当前选中：一级目录 id（uncategorized 为「未分类插件」固定项）
      selectedLevel1Id: UNCLASSIFIED,
      // 第二栏选中的子目录 id（空表示未选中，第三栏为空态）
      selectedSecondId: '',
      // 勾选状态按类型拆分：目录 id 与插件 id
      checkedCateIds: [],
      checkedPluginIds: [],
      keyword: '',
      isSearchPanelShow: false,
      flashId: '',
      flashType: '',
      flashTimer: null,
      dirty: false,
      // AI 智能分类：自然语言分类需求（选填）
      aiPrompt: '',
      aiSmartLoading: false,
      deleteDialogVisible: false,
      deleteImpactLoading: false,
      deleteImpactItems: [],
      createDialogVisible: false,
      createMode: 'root',
      createForm: { parentId: '', name: '' },
      createNameError: '',
      createParentError: '',
      // dnd：拖拽状态机（active 拖拽中 / ids 拖拽组 / type 'dir'|'plugin' / hoverKey 落点去重）
      dnd: { active: false, ids: [], type: '', hoverKey: '' },
      // dropState：行落点（intent: { kind, targetId } + ok），驱动行的落点 class
      dropState: { intent: null, ok: true },
      // colDrop：栏空白区落点（key 栏标识 + ok + intent 供 drop 落地使用）
      colDrop: { key: '', ok: true, intent: null },
      // denyTip：禁止落点气泡（fixed 定位坐标 + 文案），拖拽期间 bk-tooltips 不触发需自绘
      denyTip: null,
      // dndGhost：拖拽 ghost 内容（数量 + 类型 + 名称）
      dndGhost: null,
      // pendingDrag：mousedown 待激活的拖拽（移动超阈值后才进入拖拽，保留 click 语义）
      pendingDrag: null,
    };
  },
  computed: {
    ...mapState({
      spaceId: state => state.spaceId,
    }),
    trimKeyword() {
      return this.keyword.trim().toLowerCase();
    },
    filteredLevel1() {
      return this.categories;
    },
    // 定位匹配结果：一级目录 / 子目录 / 插件（含路径副标题）
    searchResults() {
      const kw = this.trimKeyword;
      if (!kw) return [];
      const results = [];
      this.categories.forEach((cate) => {
        if ((cate.name || '').toLowerCase().includes(kw)) {
          results.push({ id: cate.id, type: 'level1', name: cate.name, path: this.$t('一级目录') });
        }
        (cate.children || []).forEach((sub) => {
          if ((sub.name || '').toLowerCase().includes(kw)) {
            results.push({
              id: sub.id,
              type: 'level2',
              parentId: cate.id,
              name: sub.name,
              path: cate.name,
            });
          }
        });
      });
      this.plugins.forEach((plugin) => {
        const pluginName = plugin.plugin_name || '';
        if (pluginName.toLowerCase().includes(kw)) {
          const level1 = this.categories.find(cate => cate.id === plugin.directory_id
            || (cate.children || []).some(sub => sub.id === plugin.directory_id));
          const sub = level1 && (level1.children || []).find(item => item.id === plugin.directory_id);
          let path = this.$t('未分类插件');
          if (level1) {
            path = sub ? `${level1.name} / ${sub.name}` : level1.name;
          }
          results.push({
            id: plugin.id,
            type: 'plugin',
            parentId: sub ? sub.id : '',
            level1Id: level1 ? level1.id : UNCLASSIFIED,
            name: pluginName,
            path,
          });
        }
      });
      return results;
    },
    // plugins 为全量插件：directory_id 有值即已分类，空值（'' / null）即未分类
    uncategorizedPlugins() {
      return this.plugins.filter(plugin => !plugin.directory_id);
    },
    isUncategorized() {
      return this.selectedLevel1Id === UNCLASSIFIED;
    },
    selectedLevel1() {
      return this.categories.find(cate => cate.id === this.selectedLevel1Id) || null;
    },
    // 一级目录未命中搜索时第二栏仍保持原列表
    secondDirectories() {
      return (this.selectedLevel1 && this.selectedLevel1.children) || [];
    },
    secondTitle() {
      if (this.isUncategorized) return this.$t('未分类插件');
      return (this.selectedLevel1 && this.selectedLevel1.name) || '--';
    },
    // 第二栏的直属插件（未分类时展示全部未分类插件）
    secondPlugins() {
      if (this.isUncategorized) return this.uncategorizedPlugins;
      return this.plugins.filter(plugin => this.pluginDirectoryId(plugin) === String(this.selectedLevel1Id));
    },
    selectedSecondName() {
      const sub = this.secondDirectories.find(item => item.id === this.selectedSecondId);
      return sub ? sub.name : '';
    },
    thirdTitle() {
      return this.selectedSecondName;
    },
    thirdPlugins() {
      if (!this.selectedSecondName) return [];
      return this.plugins.filter(plugin => this.pluginDirectoryId(plugin) === String(this.selectedSecondId));
    },
    hasChecked() {
      return this.checkedCateIds.length + this.checkedPluginIds.length > 0;
    },
    hasCheckedCategory() {
      return this.checkedCateIds.length > 0;
    },
    hasCheckedPlugin() {
      return this.checkedPluginIds.length > 0;
    },
    // 移动场景判定：只勾了插件时才提供「未分类」入口
    moveIsPluginOnly() {
      return !this.hasCheckedCategory;
    },
    moveBlocked() {
      const ids = new Set(this.checkedCateIds);
      return this.categories.some(cate => ids.has(cate.id) && (cate.children || []).length > 0);
    },
    moveDisabled() {
      return !this.hasChecked || this.moveBlocked;
    },
    moveSelectableLevel() {
      return this.hasCheckedPlugin && !this.hasCheckedSecondLevel ? 'all' : 'level1';
    },
    // 未分类
    moveShowUnclassified() {
      return this.moveIsPluginOnly;
    },
    // 勾选项中是否含二级目录
    hasCheckedSecondLevel() {
      const ids = new Set(this.checkedCateIds);
      return this.categories.some(cate => (cate.children || []).some(sub => ids.has(sub.id)));
    },
    // 不能移动到自己或自己的子目录下：排除被勾选目录自身及其子目录
    moveExcludeIds() {
      const ids = new Set(this.checkedCateIds);
      const excluded = [];
      this.categories.forEach((cate) => {
        if (ids.has(cate.id)) {
          excluded.push(cate.id);
          (cate.children || []).forEach(sub => excluded.push(sub.id));
          return;
        }
        (cate.children || []).forEach((sub) => {
          if (ids.has(sub.id)) excluded.push(sub.id);
        });
      });
      return excluded;
    },
    deleteDisabled() {
      // 仅勾选目录时可删除
      return !this.hasCheckedCategory || this.hasCheckedPlugin;
    },

    // 删除弹窗标题：单个目录显示名称，多个显示数量
    deleteDialogTitle() {
      const list = this.deleteImpactItems;
      if (list.length === 1) {
        return this.$t('确认删除「{0}」目录？', [list[0].name]);
      }
      return this.$t('确认删除所选的 {0} 个目录？', [list.length]);
    },
    isMultiCategoryDelete() {
      return this.deleteImpactItems.length > 1;
    },
    createDialogTitle() {
      return this.createMode === 'root' ? this.$t('新建目录') : this.$t('新建子目录');
    },
    createRules() {
      return {
        parentId: [
          { required: true, message: this.$t('必填项'), trigger: 'change' },
        ],
        name: [
          { required: true, message: this.$t('必填项'), trigger: 'blur' },
          {
            validator: value => !this.isDuplicateName(value),
            message: this.$t('目录名称已存在'),
            trigger: 'blur',
          },
        ],
      };
    },
  },
  watch: {
    keyword(val) {
      this.isSearchPanelShow = !!String(val || '').trim();
    },
    // 弹窗关闭清除校验态
    createDialogVisible(val) {
      if (val) return;
      const form = this.$refs.createFormRef;
      if (form && typeof form.clearValidate === 'function') {
        form.clearValidate();
      }
    },
  },
  created() {
    this.fetchData();
  },
  mounted() {
    document.addEventListener('mousedown', this.handleDocMouseDown);
  },
  beforeDestroy() {
    document.removeEventListener('mousedown', this.handleDocMouseDown);
    this.resetDnd();
    clearTimeout(this.flashTimer);
  },
  beforeRouteLeave(to, from, next) {
    if (!this.dirty) {
      next();
      return;
    }
    this.$bkInfo({
      title: this.$t('确定离开当前页面？'),
      subTitle: this.$t('离开后未保存的修改将丢失'),
      maskClose: false,
      width: 450,
      confirmFn: () => {
        next();
      },
    });
  },
  methods: {
    // 目录 id 在 directoriesToTree 中已转为字符串，插件 directory_id 统一 String 归一化后再比较
    pluginDirectoryId(plugin) {
      return String(plugin.directory_id || '');
    },
    ...mapActions('pluginManage', [
      'getDirectoryManagePage',
      'saveDirectoryManage',
      'getCategoryDeleteImpact',
      'deleteCategory',
      'aiSmartClassify',
    ]),
    directoriesToTree(directories = {}) {
      const nodes = Object.keys(directories).map(key => ({
        id: String((directories[key] && directories[key].id) || key),
        parent_id: directories[key] && directories[key].parent_id ? String(directories[key].parent_id) : '',
        name: (directories[key] && directories[key].name) || '',
        order: (directories[key] && directories[key].order) || 0,
        children: [],
      }));
      const byId = {};
      nodes.forEach((node) => {
        byId[node.id] = node;
      });
      const roots = [];
      nodes.forEach((node) => {
        if (node.parent_id && byId[node.parent_id]) {
          byId[node.parent_id].children.push(node);
        } else {
          roots.push(node);
        }
      });
      const byOrder = (a, b) => a.order - b.order;
      roots.sort(byOrder);
      Object.keys(byId).forEach(id => byId[id].children.sort(byOrder));
      // 剥离内部排序字段
      const clean = node => ({
        id: node.id,
        name: node.name,
        children: node.children.map(clean),
      });
      return roots.map(clean);
    },
    treeToDirectories(categories = []) {
      const directories = {};
      const walk = (nodes, parentId) => {
        (nodes || []).forEach((node, index) => {
          directories[String(node.id)] = {
            id: String(node.id),
            parent_id: parentId ? String(parentId) : '',
            name: node.name,
            order: index + 1,
          };
          walk(node.children, node.id);
        });
      };
      walk(categories, '');
      return directories;
    },
    async fetchData() {
      this.loading = true;
      try {
        const page = await this.getDirectoryManagePage({ space_id: this.spaceId });
        this.manageRevision = page.revision;
        this.categories = this.directoriesToTree(page.directories);
        this.plugins = (page.plugins || []).map(plugin => ({
          ...plugin,
          // 统一字符串化：data-locate-id / checkedCateIds / checkedPluginIds / 拖拽组 ids 均为字符串，避免 === 类型不匹配
          id: String(plugin.id),
          directory_id: plugin.directory_id ? String(plugin.directory_id) : '',
        }));
        this.originalAssignments = {};
        this.plugins.forEach(({ id, directory_id: directoryId }) => {
          this.originalAssignments[String(id)] = directoryId;
        });
        this.resetSelection();
      } finally {
        this.loading = false;
      }
    },
    resetSelection() {
      this.selectedLevel1Id = UNCLASSIFIED;
      this.selectedSecondId = '';
      this.checkedCateIds = [];
      this.checkedPluginIds = [];
      // 默认选中第一个一级目录
      const first = this.categories[0];
      if (first) this.handleSelectLevelOne(first.id);
    },
    level1PluginCount(cate) {
      return this.plugins.filter(plugin => matchPluginCategory(plugin, cate.id, this.categories)).length;
    },
    pluginCountById(categoryId) {
      return this.plugins.filter(plugin => plugin.directory_id === categoryId).length;
    },
    handleSelectLevelOne(id) {
      this.selectedLevel1Id = id;
      // 默认选中第一个子目录；无子目录时第三栏为空态
      const level1 = this.categories.find(cate => cate.id === id);
      const firstChild = level1 && (level1.children || [])[0];
      this.selectedSecondId = firstChild ? firstChild.id : '';
    },
    // 定位下拉项图标 class
    optionIconCls(item) {
      if (item.type === 'plugin') return 'commonicon-icon common-icon-plugin-chajian is-plugin';
      return 'commonicon-icon common-icon-file-open-dakaiwenjianjia';
    },
    // 名称按关键字分段（命中段高亮蓝色）
    highlightName(name) {
      const kw = this.trimKeyword;
      if (!kw || !name) return [{ text: name || '', hit: false }];
      const segments = [];
      const lower = name.toLowerCase();
      let index = 0;
      while (index < name.length) {
        const hitIndex = lower.indexOf(kw, index);
        if (hitIndex === -1) {
          segments.push({ text: name.slice(index), hit: false });
          break;
        }
        if (hitIndex > index) segments.push({ text: name.slice(index, hitIndex), hit: false });
        segments.push({ text: name.slice(hitIndex, hitIndex + kw.length), hit: true });
        index = hitIndex + kw.length;
      }
      return segments;
    },
    // 点击匹配项：定位到对应栏 → 橙色闪烁两次 → 累加勾选（保留此前已选中项）→ 展示成功提示
    handleLocate(item) {
      this.isSearchPanelShow = false;
      if (item.type === 'level1') {
        this.handleSelectLevelOne(item.id);
      } else if (item.type === 'level2') {
        this.handleSelectLevelOne(item.parentId);
        this.selectedSecondId = item.id;
      } else {
        // 插件：切到归属目录层级，保证所在行可见
        this.handleSelectLevelOne(item.level1Id);
        if (item.parentId) this.selectedSecondId = item.parentId;
      }
      // 连续定位时保留已选中项，新定位项去重追加（重复定位同一项不会取消勾选）
      const checkedList = item.type === 'level1' || item.type === 'level2'
        ? this.checkedCateIds
        : this.checkedPluginIds;
      if (!checkedList.includes(item.id)) {
        if (checkedList === this.checkedCateIds) {
          this.checkedCateIds = [...checkedList, item.id];
        } else {
          this.checkedPluginIds = [...checkedList, item.id];
        }
      }
      this.$bkMessage({
        theme: 'success',
        message: this.$t('已经定位到「{0}」', [item.name]),
        delay: 2000,
      });
      // 橙色背景闪烁两次
      this.flashId = item.id;
      this.flashType = item.type;
      clearTimeout(this.flashTimer);
      this.flashTimer = setTimeout(() => {
        this.flashId = '';
        this.flashType = '';
      }, 1400);
      this.$nextTick(() => {
        const dndType = item.type === 'plugin' ? 'plugin' : 'dir';
        const row = this.$el.querySelector(`[data-locate-id="${item.id}"][data-dnd-type="${dndType}"]`);
        if (row && row.scrollIntoView) row.scrollIntoView({ block: 'nearest' });
      });
    },
    // 定位下拉面板：点击面板外部关闭
    handleDocMouseDown(e) {
      if (!this.isSearchPanelShow) return;
      const wrap = this.$refs.searchLocate;
      if (wrap && !wrap.contains(e.target)) this.isSearchPanelShow = false;
    },
    onSelectLevelOne(id) {
      const changed = this.selectedLevel1Id !== id;
      this.handleSelectLevelOne(id);
      if (changed) {
        this.checkedCateIds = [];
        this.checkedPluginIds = [];
      }
    },
    onSelectSecond(sub) {
      const changed = this.selectedSecondId !== sub.id;
      this.handleSelectSecond(sub);
      if (changed) {
        this.checkedCateIds = [];
        this.checkedPluginIds = [];
      }
    },
    handleSelectSecond(sub) {
      this.selectedSecondId = sub.id;
    },
    toggleCateChecked(id) {
      this.checkedCateIds = this.checkedCateIds.includes(id)
        ? this.checkedCateIds.filter(item => item !== id)
        : [...this.checkedCateIds, id];
    },
    togglePluginChecked(id) {
      this.checkedPluginIds = this.checkedPluginIds.includes(id)
        ? this.checkedPluginIds.filter(item => item !== id)
        : [...this.checkedPluginIds, id];
    },
    // 勾选项中的插件 id（目录 id 不在此列，目录走树结构移动）
    getCheckedPluginIds() {
      return this.checkedPluginIds;
    },
    resolveDragGroup(id, type) {
      return resolveDragGroup({
        checkedIds: type === 'plugin' ? this.checkedPluginIds : this.checkedCateIds,
        categories: this.categories,
        plugins: this.plugins,
        id,
        type,
      });
    },
    // 在目录树中定位节点（一级 / 二级），返回层级与父级引用
    findCateInfo(id) {
      return findCateInfo(this.categories, id);
    },
    // id 是否在 ancestor 目录子树内
    isDescendantCategory(id, ancestor) {
      return isDescendantCategory(id, ancestor);
    },
    // 拖拽组中的目录信息（剔除父级也在组内的子级，避免重复移动）
    getMovingCateInfos() {
      return getMovingCateInfos(this.categories, this.dnd.ids);
    },
    handleRowDragMousedown(id, type, event) {
      // 从 checkbox 上按下不进入拖拽（checkbox 归点击勾选）
      if (event.target.closest && event.target.closest('.row-checkbox')) return;
      if (event.button !== 0) return;
      // 阻止文字选区，click 事件不受影响
      event.preventDefault();
      this.pendingDrag = { id, type, startX: event.clientX, startY: event.clientY };
      document.addEventListener('mousemove', this.handleDocMouseMove);
      document.addEventListener('mouseup', this.handleDocMouseUp);
      document.addEventListener('keydown', this.handleDndKeydown);
      window.addEventListener('blur', this.handleWindowBlur);
    },
    startDrag(event) {
      const { id, type } = this.pendingDrag;
      const ids = this.resolveDragGroup(id, type);
      this.dnd = { active: true, ids, type, hoverKey: '' };
      this.dropState = { intent: null, ok: true };
      this.colDrop = { key: '', ok: true, intent: null };
      this.denyTip = null;
      // ghost 内容：数量角标（多选 > 1 时显示）+ 图标 + 名称（多选补「等」）
      const startItem = type === 'plugin'
        ? this.plugins.find(plugin => plugin.id === id)
        : (this.findCateInfo(id) || {}).node;
      this.dndGhost = {
        count: ids.length,
        type,
        name: (startItem && (type === 'plugin' ? startItem.plugin_name : startItem.name)) || '',
      };
      // 拖拽期间隐藏系统光标与文字选区（自定义光标由 .drag-cursor 提供）
      document.body.classList.add('is-dnd-dragging');
      this.updateDragFollow(event);
    },
    handleDocMouseMove(event) {
      if (!this.pendingDrag) return;
      if (!this.dnd.active) {
        // 移动超过阈值才进入拖拽（保留原 click 语义）
        const { startX, startY } = this.pendingDrag;
        if (Math.abs(event.clientX - startX) + Math.abs(event.clientY - startY) < 4) return;
        this.startDrag(event);
      }
      this.updateDragFollow(event);
      // 栏边缘自动滚动（原生拖拽自带的行为在鼠标模拟下需手动实现）
      const scrollEl = event.target.closest ? event.target.closest('.column-body') : null;
      if (scrollEl) {
        const rect = scrollEl.getBoundingClientRect();
        if (event.clientY < rect.top + 24) scrollEl.scrollTop -= 12;
        else if (event.clientY > rect.bottom - 24) scrollEl.scrollTop += 12;
      }
      this.updateDropTarget(event.target, event);
    },
    // 光标与 ghost 跟随（直接写 transform，保证禁止气泡取 ghost 盒模型时是实时位置）：
    // 光标图标中心对准鼠标点，ghost 左上角贴在光标右侧（即光标始终位于 ghost 左上角）
    updateDragFollow(event) {
      if (this.$refs.dragCursor) {
        this.$refs.dragCursor.style.transform = `translate(${event.clientX - 9}px, ${event.clientY - 9}px)`;
      }
      if (this.$refs.dragGhost) {
        this.$refs.dragGhost.style.transform = `translate(${event.clientX + 10}px, ${event.clientY - 8}px)`;
      }
      // 气泡坐标每帧同步：denyTip 仅在悬停目标切换时创建（text 不变），
      // 但位置必须持续跟随 ghost，否则鼠标继续移动后气泡会停在旧位置
      this.syncDenyTipPos();
    },
    // 禁止气泡坐标：位于 ghost 右侧并垂直居中于 ghost（取 ghost 实时盒模型，长名不会被气泡遮挡）
    makeDenyTip(reason, event) {
      const ghost = this.$refs.dragGhost;
      if (ghost) {
        const rect = ghost.getBoundingClientRect();
        return { top: rect.top + (rect.height / 2), left: rect.right + 8, text: reason };
      }
      return { top: event.clientY, left: event.clientX + 24, text: reason };
    },
    // 按当前 ghost 位置刷新禁止气泡坐标（无 ghost 时保持创建时的 fallback 坐标）
    syncDenyTipPos() {
      if (!this.denyTip || !this.$refs.dragGhost) return;
      const rect = this.$refs.dragGhost.getBoundingClientRect();
      this.denyTip.top = rect.top + (rect.height / 2);
      this.denyTip.left = rect.right + 8;
    },
    // 落点检测与视觉更新（行 / 未分类固定行 / 栏空白区，复用原 dragover 语义）
    updateDropTarget(targetEl, event) {
      const rowEl = targetEl.closest ? targetEl.closest('.cate-row') : null;
      // 「未分类插件」固定行：只接受插件落入（语义 = 移动至未分类），复用 into 落点态渲染
      if (rowEl && rowEl.dataset.dndType === 'uncat') {
        const result = this.validateDrop({ kind: 'uncategorized', targetId: '' });
        const key = `uncat:${result.ok ? 1 : 0}`;
        if (key !== this.dnd.hoverKey) {
          this.dnd.hoverKey = key;
          this.dropState = { intent: { kind: 'into', targetId: UNCLASSIFIED }, ok: result.ok };
          this.colDrop = { key: '', ok: true, intent: null };
          this.denyTip = !result.ok && result.reason ? this.makeDenyTip(result.reason, event) : null;
        }
        return;
      }
      if (rowEl && rowEl.dataset.locateId) {
        const id = rowEl.dataset.locateId;
        // 悬停在拖拽组自身行上：清空落点（需类型一致，目录/插件 id 可能撞号）
        if (this.dnd.type === rowEl.dataset.dndType && this.dnd.ids.includes(id)) {
          if (this.dropState.intent || this.denyTip || this.colDrop.key) this.clearDropVisual();
          return;
        }
        const intent = this.resolveRowIntent(id, rowEl.dataset.dndType, rowEl, event);
        const result = this.validateDrop(intent);
        const key = `${intent.kind}:${intent.targetId}:${result.ok ? 1 : 0}`;
        if (key !== this.dnd.hoverKey) {
          this.dnd.hoverKey = key;
          this.dropState = { intent, ok: result.ok };
          this.colDrop = { key: '', ok: true, intent: null };
          this.denyTip = !result.ok && result.reason ? this.makeDenyTip(result.reason, event) : null;
        }
        return;
      }
      const colEl = targetEl.closest ? targetEl.closest('.column-body') : null;
      if (colEl) {
        this.updateColumnTarget(colEl.dataset.colKey, event);
      } else if (this.dropState.intent || this.denyTip || this.colDrop.key) {
        this.clearDropVisual();
      }
    },
    // 栏空白区：第一栏 = 根级、第二栏 = 当前一级（未分类形态 = 未分类）、第三栏 = 当前二级
    updateColumnTarget(columnKey, event) {
      let intent = null;
      if (columnKey === 'level1') {
        intent = { kind: 'root', targetId: '' };
      } else if (columnKey === 'second') {
        intent = this.isUncategorized
          ? { kind: 'uncategorized', targetId: '' }
          : { kind: 'into', targetId: this.selectedLevel1Id, targetType: 'dir' };
      } else if (columnKey === 'third' && this.selectedSecondId) {
        intent = { kind: 'into', targetId: this.selectedSecondId, targetType: 'dir' };
      }
      if (!intent) {
        if (this.dropState.intent || this.denyTip || this.colDrop.key) this.clearDropVisual();
        return;
      }
      const result = this.validateDrop(intent);
      const key = `col:${columnKey}:${result.ok ? 1 : 0}`;
      if (key !== this.dnd.hoverKey) {
        this.dnd.hoverKey = key;
        this.dropState = { intent: null, ok: true };
        this.colDrop = { key: columnKey, ok: result.ok, intent };
        this.denyTip = !result.ok && result.reason ? this.makeDenyTip(result.reason, event) : null;
      }
    },
    // 松手落地（复用原 drop 语义：禁止落点时复位并提示原因）
    handleDocMouseUp(event) {
      const { active } = this.dnd;
      this.pendingDrag = null;
      if (!active) {
        this.teardownDndListeners();
        return;
      }
      // 原生拖拽浏览器会抑制拖拽后的 click，鼠标模拟需自行吞掉同一次交互产生的 click
      this.suppressNextClick();
      const targetEl = event.target;
      const rowEl = targetEl.closest ? targetEl.closest('.cate-row') : null;
      if (rowEl && rowEl.dataset.dndType === 'uncat') {
        const result = this.validateDrop({ kind: 'uncategorized', targetId: '' });
        if (!result.ok) {
          this.resetDnd();
          if (result.reason) this.$bkMessage({ message: result.reason, theme: 'error' });
          return;
        }
        this.executeDrop({ kind: 'uncategorized', targetId: '' });
        return;
      }
      if (rowEl && rowEl.dataset.locateId) {
        const id = rowEl.dataset.locateId;
        if (this.dnd.type === rowEl.dataset.dndType && this.dnd.ids.includes(id)) {
          this.resetDnd();
          return;
        }
        const intent = this.resolveRowIntent(id, rowEl.dataset.dndType, rowEl, event);
        const result = this.validateDrop(intent);
        if (!result.ok) {
          this.resetDnd();
          if (result.reason) this.$bkMessage({ message: result.reason, theme: 'error' });
          return;
        }
        this.executeDrop(intent);
        return;
      }
      const colEl = targetEl.closest ? targetEl.closest('.column-body') : null;
      const { key, ok, intent } = this.colDrop;
      // 落点与松手栏不一致（残留旧落点）时不落地
      if (colEl && key === colEl.dataset.colKey && ok && intent) {
        this.executeDrop(intent);
        return;
      }
      this.resetDnd();
    },
    // 拖拽结束后吞掉同一次交互产生的 click（避免松手行被误触勾选/选中）
    suppressNextClick() {
      const swallow = (evt) => {
        evt.stopPropagation();
        evt.preventDefault();
      };
      document.addEventListener('click', swallow, { capture: true, once: true, passive: false });
      setTimeout(() => document.removeEventListener('click', swallow, { capture: true }), 0);
    },
    // Esc 取消拖拽 / 窗口失焦兜底复位
    handleDndKeydown(event) {
      if (event.key === 'Escape') this.resetDnd();
    },
    handleWindowBlur() {
      this.resetDnd();
    },
    teardownDndListeners() {
      document.removeEventListener('mousemove', this.handleDocMouseMove);
      document.removeEventListener('mouseup', this.handleDocMouseUp);
      document.removeEventListener('keydown', this.handleDndKeydown);
      window.removeEventListener('blur', this.handleWindowBlur);
      document.body.classList.remove('is-dnd-dragging');
    },
    // 行落点解析：目录行上/下 25% 为调序、中间为移入；插件行上下 50% 为调序
    resolveRowIntent(id, type, rowEl, event) {
      const rect = rowEl.getBoundingClientRect();
      const ratio = (event.clientY - rect.top) / rect.height;
      return resolveRowIntent({ dragType: this.dnd.type, rowType: type, ratio, targetId: id });
    },
    // 落点校验：返回 { ok, reason }，reason 非空时气泡提示（设计稿拦截文案）
    validateDrop(intent) {
      if (!intent) return { ok: false, reason: '' };
      return validateDrop({
        categories: this.categories,
        plugins: this.plugins,
        dnd: this.dnd,
        intent,
        t: key => this.$t(key),
      });
    },
    clearDropVisual() {
      this.dropState = { intent: null, ok: true };
      this.colDrop = { key: '', ok: true, intent: null };
      this.denyTip = null;
    },
    // 拖拽结束统一复位（松手 / Esc / 失焦 / 悬停自身行）
    resetDnd() {
      this.dnd = { active: false, ids: [], type: '', hoverKey: '' };
      this.clearDropVisual();
      this.dndGhost = null;
      this.pendingDrag = null;
      this.teardownDndListeners();
    },
    // 摘除拖拽组中的目录（一级从顶层、二级从父级 children）
    detachMovingCategories(idSet) {
      const moving = [];
      this.categories = this.categories.filter((cate) => {
        if (idSet.has(cate.id)) {
          moving.push(cate);
          return false;
        }
        cate.children = (cate.children || []).filter((sub) => {
          if (idSet.has(sub.id)) {
            moving.push(sub);
            return false;
          }
          return true;
        });
        return true;
      });
      return moving;
    },
    // before / after 落点与当前位置等价时不做改动（避免无效 dirty 与误提示）
    isReorderNoop(intent, idSet, type) {
      let siblings;
      if (type === 'dir') {
        const info = this.findCateInfo(intent.targetId);
        if (!info) return false;
        siblings = info.level === 1 ? this.categories : ((info.parent && info.parent.children) || []);
      } else {
        siblings = this.plugins;
      }
      const movingIdxs = [];
      siblings.forEach((item, index) => {
        if (idSet.has(item.id)) movingIdxs.push(index);
      });
      if (!movingIdxs.length) return false;
      // 多选拖拽组不连续时不做等价判定，直接执行
      const count = movingIdxs.length;
      if (movingIdxs[count - 1] - movingIdxs[0] + 1 !== count) return false;
      const first = movingIdxs[0];
      const targetIdx = siblings.findIndex(item => item.id === intent.targetId);
      if (targetIdx < 0) return false;
      // 目标在移动组之后时，移除组后目标索引前移 count 位
      const newTargetIdx = targetIdx > movingIdxs[count - 1] ? targetIdx - count : targetIdx;
      // before 等价于插回组首原位，after 等价于插回组尾原位
      return intent.kind === 'before' ? newTargetIdx === first : newTargetIdx + 1 === first + count;
    },
    // 同级调序（目录）：摘除移动组后按目标 before/after 重新插入
    reorderCategories(intent, idSet) {
      const target = this.findCateInfo(intent.targetId);
      if (!target) return;
      const moving = this.detachMovingCategories(idSet);
      if (!moving.length) return;
      // 摘除后重新定位目标索引（节点引用不变，父级 children 已被 filter 重建）
      const siblings = target.level === 1
        ? this.categories
        : ((target.parent && target.parent.children) || []);
      const idx = siblings.findIndex(item => item.id === intent.targetId);
      const insertIdx = idx < 0 ? siblings.length : idx + (intent.kind === 'after' ? 1 : 0);
      siblings.splice(insertIdx, 0, ...moving);
    },
    // 同级调序（插件）：plugins 数组顺序即展示顺序（第二/三栏按数组顺序 filter）
    // 跨栏拖拽时归属跟随目标插件，返回是否发生实际变更
    reorderPlugins(intent, idSet) {
      const { list, updates, changed } = reorderPlugins({
        plugins: this.plugins,
        ids: [...idSet],
        targetId: intent.targetId,
        kind: intent.kind,
      });
      if (!changed) return false;
      // 归属变更需 $set 写入（未分类插件可能没有 category 字段，Vue2 无法自动响应）
      updates.forEach(({ plugin, directory_id: directoryId }) => this.$set(plugin, 'directory_id', directoryId));
      this.plugins = list;
      return true;
    },
    // 目录组 before/after 调序的序列父级：落点为二级目录或直属插件时返回其一级父 id（混排序列），
    // 落点为一级目录时返回 ''（走一级序列原逻辑）
    getDirReorderParentId(intent) {
      const target = this.findCateInfo(intent.targetId);
      return target && target.level === 2 ? target.parentId : '';
    },
    // 落点为插件行时的混排序列父级 = 该插件归属（目录/插件 id 可能撞号，按 targetType 分流解析）
    getPluginReorderParentId(intent) {
      const plugin = this.plugins.find(item => item.id === intent.targetId);
      return plugin && plugin.directory_id ? plugin.directory_id : '';
    },
    // 混排调序前提：勾选组内每一项都属于该父级的混排序列（子目录或直属插件）
    canUseMixedReorder(parentId, idSet) {
      const parent = this.categories.find(cate => cate.id === parentId);
      if (!parent) return false;
      const childIds = new Set((parent.children || []).map(cate => cate.id));
      let hasItem = false;
      let ok = true;
      idSet.forEach((id) => {
        if (childIds.has(id)) {
          hasItem = true;
          return;
        }
        // 该 id 是其他目录（不在目标父 children 中）→ 不属于该混排序列；避免目录 id 撞号被误当插件检查归属
        if (this.findCateInfo(id)) {
          ok = false;
          return;
        }
        const plugin = this.plugins.find(item => item.id === id);
        if (plugin && (plugin.directory_id || '') === parentId) {
          hasItem = true;
          return;
        }
        ok = false;
      });
      return ok && hasItem;
    },
    // 拖拽落地：into/root/uncategorized/before+after 统一入口，改动本地生效并置 dirty
    executeDrop(intent) {
      const { type, ids } = this.dnd;
      const idSet = new Set(ids);
      // 目录移动时剔除「父级也在组内」的子目录，避免父子目录被拉平成同级
      const moveIdSet = type === 'dir'
        ? new Set(this.getMovingCateInfos().map(info => info.node.id))
        : idSet;
      let changed = false;
      this.resetDnd();
      if (intent.kind === 'root') {
        // 目录放回根级（一级）末尾
        const moving = this.detachMovingCategories(moveIdSet);
        if (moving.length) {
          this.categories = [...this.categories, ...moving];
          changed = true;
        }
      } else if (intent.kind === 'uncategorized') {
        // 插件移入未分类（category 置空）
        this.plugins.forEach((plugin) => {
          if (idSet.has(plugin.id) && (plugin.directory_id || '') !== '') {
            this.$set(plugin, 'directory_id', '');
            changed = true;
          }
        });
        if (changed) this.handleSelectLevelOne(UNCLASSIFIED);
      } else if (intent.kind === 'into') {
        if (type === 'plugin') {
          // 插件改归属：用 $set 写入，未分类插件可能没有 category 字段（Vue2 响应式）
          this.plugins.forEach((plugin) => {
            if (idSet.has(plugin.id) && plugin.directory_id !== intent.targetId) {
              this.$set(plugin, 'directory_id', intent.targetId);
              changed = true;
            }
          });
        } else {
          // 目录换父：摘除后挂到目标一级目录下
          const target = this.categories.find(cate => cate.id === intent.targetId);
          if (target) {
            const moving = this.detachMovingCategories(moveIdSet);
            if (moving.length) {
              target.children = [...(target.children || []), ...moving];
              changed = true;
            }
          }
          // 混合勾选（目录 + 插件）：其中的插件一并改归属到目标目录
          this.plugins.forEach((plugin) => {
            if (idSet.has(plugin.id) && plugin.directory_id !== intent.targetId) {
              this.$set(plugin, 'directory_id', intent.targetId);
              changed = true;
            }
          });
        }
        if (changed) {
          // 视图跟随到目标目录，方便确认移动结果
          const level1 = this.categories.find(cate => cate.id === intent.targetId
            || (cate.children || []).some(sub => sub.id === intent.targetId));
          if (level1) {
            this.selectedLevel1Id = level1.id;
            this.selectedSecondId = level1.id === intent.targetId
              ? ((level1.children || [])[0] ? level1.children[0].id : '')
              : intent.targetId;
          }
        }
      } else if (type === 'dir') {
    // 目录组 before/after：落点在二级目录或直属插件上时走「子目录 + 直属插件」混排序列
    // （支持混合勾选组整组移动；一级序列调序保持原逻辑）
    const mixedParentId = intent.targetType === 'plugin'
      ? this.getPluginReorderParentId(intent)
      : this.getDirReorderParentId(intent);
        if (mixedParentId && this.canUseMixedReorder(mixedParentId, idSet)) {
          const parent = this.categories.find(cate => cate.id === mixedParentId);
          const result = reorderMixedColumn({
            children: (parent && parent.children) || [],
            plugins: this.plugins,
            parentId: mixedParentId,
            ids: [...idSet],
            targetId: intent.targetId,
            kind: intent.kind,
            dragType: type,
            targetKind: intent.targetType,
          });
          if (result.changed && parent) {
            this.$set(parent, 'children', result.children);
            this.plugins = result.plugins;
            changed = true;
          }
        } else if (intent.targetType === 'plugin') {
          // 目录组落到插件行但不满足混排前提：不落地（避免撞号 id 被 findCateInfo 误解析）
        } else if (!this.isReorderNoop(intent, moveIdSet, type)) {
          this.reorderCategories(intent, moveIdSet);
          changed = true;
        }
      } else {
        changed = this.reorderPlugins(intent, idSet);
      }
      if (!changed) return;
      this.dirty = true;
      this.$bkMessage({ message: this.$t('移动成功'), theme: 'success' });
    },
    // 栏空白区落点高亮 class：同一时刻只有命中的那一栏高亮
    columnBodyCls(key) {
      if (!this.dnd.active || !this.colDrop.key || this.colDrop.key !== key) return '';
      return this.colDrop.ok ? 'is-col-drop-ok' : 'is-col-drop-deny';
    },
    // 行的拖拽态 class：拖起行半透明 + 六种落点态（before/after/into × ok/deny）
    // type 用于过滤撞号：目录 id 与插件 id 是两套编号可能相同，落点/拖拽态只落在同类型行上
    rowStateCls(id, type) {
      if (!this.dnd.active) return {};
      const cls = {};
      if (this.dnd.type === type && this.dnd.ids.includes(id)) cls['is-dragging'] = true;
      const { intent, ok } = this.dropState;
      if (intent && intent.targetId === id) {
        // 落点态只显示在落点行同类型的行上（目录/插件 id 可能撞号，不能按 id 反查类型）
        const targetType = intent.kind === 'uncategorized' ? 'plugin' : (intent.targetType || '');
        if (!targetType || targetType === type) {
          cls[`is-drop-${intent.kind}-${ok ? 'ok' : 'deny'}`] = true;
        }
      }
      return cls;
    },
    // 移动至：插件改归属（可到未分类）+ 目录换父（只能挂到某个一级目录下）
    // 目标可选范围由面板按勾选内容收敛，这里只做落地的树/数据改动
    handleMoveTo({ categoryId }) {
      if (this.moveBlocked) {
        this.closeMovePopover();
        return;
      }
      const idSet = new Set(this.checkedCateIds);
      // 1) 插件：直接改归属（一级或二级 id，空表示未分类）
      const pluginIdSet = new Set(this.getCheckedPluginIds());
      this.plugins.forEach((plugin) => {
        if (pluginIdSet.has(plugin.id)) {
          this.$set(plugin, 'directory_id', categoryId);
        }
      });
      // 2) 目录：从原父节点摘除，再挂到目标一级目录下
      //    目标为二级目录时挂到其所属一级目录下；未分类（categoryId 为空）只移动插件，目录保持原位
      if (categoryId && this.hasCheckedCategory) {
        // 目标不能是被移动的目录自身（面板已用 excludeIds 过滤，这里兜底）
        let target = idSet.has(categoryId)
          ? null
          : this.categories.find(cate => cate.id === categoryId);
        if (!target) {
          // 二级目录目标：目录不能挂到二级，落到其所属一级目录下
          const parent = this.categories.find(cate => (cate.children || []).some(sub => sub.id === categoryId));
          if (parent && !idSet.has(parent.id)) target = parent;
        }
        if (target) {
          const moving = [];
          this.categories = this.categories.filter((cate) => {
            if (idSet.has(cate.id)) {
              moving.push(cate);
              return false;
            }
            cate.children = (cate.children || []).filter((sub) => {
              if (idSet.has(sub.id)) {
                moving.push(sub);
                return false;
              }
              return true;
            });
            return true;
          });
          if (moving.length) {
            target.children = [...(target.children || []), ...moving];
          }
        }
      }
      // 3) 视图跟随到目标目录，方便确认移动结果
      const level1 = this.categories.find(cate => cate.id === categoryId
        || (cate.children || []).some(sub => sub.id === categoryId));
      if (level1) {
        this.selectedLevel1Id = level1.id;
        this.selectedSecondId = level1.id === categoryId
          ? ((level1.children || [])[0] ? level1.children[0].id : '')
          : categoryId;
      } else if (!categoryId) {
        this.handleSelectLevelOne(UNCLASSIFIED);
      }
      this.checkedCateIds = [];
      this.checkedPluginIds = [];
      this.dirty = true;
      this.closeMovePopover();
      // 混合勾选移动到未分类：插件已移动，目录保持原位（目录必须挂在某个一级目录下）
      if (!categoryId && this.hasCheckedCategory) {
        this.$bkMessage({ message: this.$t('插件已移动到未分类，目录不能移动到未分类，保持原位'), theme: 'warning' });
        return;
      }
      this.$bkMessage({ message: this.$t('移动成功'), theme: 'success' });
    },
    closeMovePopover() {
      const popover = this.$refs.movePopover;
      if (!popover) return;
      if (popover.hideHandler) {
        popover.hideHandler();
      } else if (popover.hide) {
        popover.hide();
      }
    },
    impactRows(item) {
      return [
        {
          count: item.children_count,
          unit: this.$t('个子目录'),
          change: item.children_effect,
        },
        {
          count: item.plugin_count,
          unit: this.$t('个插件'),
          change: item.plugin_effect,
        },
      ];
    },
    async handleDeleteChecked() {
      if (!this.hasCheckedCategory) return;
      this.deleteDialogVisible = true;
      this.deleteImpactItems = [];
      this.deleteImpactLoading = true;
      // 勾选目录 id
      const directoryIds = this.checkedCateIds.join(',');
      try {
        const impact = await this.getCategoryDeleteImpact({
          space_id: this.spaceId,
          directory_ids: directoryIds,
        });
        this.deleteImpactItems = (impact && impact.items) || [];
      } catch (e) {
        console.log(e);
      } finally {
        this.deleteImpactLoading = false;
      }
    },
    async confirmDeleteChecked() {
      this.deleteDialogVisible = false;
      const directoryIds = this.deleteImpactItems.map(item => String(item.id)).join(',');
      this.checkedCateIds = [];
      this.checkedPluginIds = [];
      try {
        await this.deleteCategory({
          space_id: this.spaceId,
          directory_ids: directoryIds,
        });
        await this.fetchData();
        this.dirty = true;
        this.$bkMessage({ message: this.$t('删除成功'), theme: 'success' });
      } catch (e) {
        console.log(e);
        await this.fetchData();
      }
    },
    handleCreateCategory(parentId, forceMode) {
      this.createMode = forceMode || (parentId ? 'child' : 'root');
      this.createForm = {
        parentId: parentId || '',
        name: '',
      };
      this.createDialogVisible = true;
    },
    // 目录名是否与同级已有目录重名
    isDuplicateName(name) {
      const keyword = name.trim().toLowerCase();
      if (this.createMode === 'root') {
        return this.categories.some(item => item.name.trim().toLowerCase() === keyword);
      }
      const parent = this.categories.find(item => item.id === this.createForm.parentId);
      return ((parent && parent.children) || [])
        .some(item => item.name.trim().toLowerCase() === keyword);
    },
    async confirmCreateCategory() {
      if (!this.createDialogVisible) return;
      try {
        await this.$refs.createFormRef.validate();
      } catch (e) {
        return;
      }
      const name = this.createForm.name.trim();
      const isRoot = this.createMode === 'root';
      // order 为同级排序号（必填整数，同级不可重复）
      const parent = isRoot ? null : this.categories.find(item => item.id === this.createForm.parentId);
      const siblings = isRoot ? this.categories : (parent.children || []);
      const node = {
        id: `new_${Date.now()}`,
        parent_id: isRoot ? '' : String(this.createForm.parentId),
        name,
        order: siblings.length + 1,
        children: [],
      };
      if (isRoot) {
        this.categories.push(node);
        this.handleSelectLevelOne(node.id);
      } else {
        parent.children = siblings;
        parent.children.push(node);
        if (this.selectedLevel1Id !== node.parent_id) {
          this.handleSelectLevelOne(node.parent_id);
        }
        this.selectedSecondId = node.id;
      }
      // 新建完成直接勾选新目录
      this.checkedCateIds = [node.id];
      this.dirty = true;
      this.createDialogVisible = false;
      this.$bkMessage({ message: this.$t('创建成功'), theme: 'success' });
    },
    // AI 输入面板展开后聚焦输入框
    handleAiPanelShow() {
      this.aiPrompt = '';
      this.$nextTick(() => {
        const textarea = this.$refs.aiTextarea;
        textarea && textarea.focus();
      });
    },
    showAiPanel() {
      this.$refs.aiPopover.showHandler();
    },
    // 提交 AI 分类需求
    async submitAiClassify() {
      if (this.aiSmartLoading) return;
      const content = this.aiPrompt.trim();
      this.$refs.aiPopover.hideHandler();
      this.aiSmartLoading = true;
      try {
        const res = await this.aiSmartClassify({
          space_id: this.spaceId,
          content,
        });

        if (res && res.result === 'empty') {
          this.$bkMessage({ message: this.$t('AI 暂无分类方案，请重试'), theme: 'warning' });
          return;
        }
        if (!res || res.result !== 'patch') {
          this.$bkMessage({ message: res?.message || this.$t('AI 智能分类失败，请重试'), theme: 'error' });
          return;
        }
        this.applyAiSuggestion(res);
        this.aiPrompt = '';
        this.$bkMessage({ message: this.$t('AI 智能分类已应用'), theme: 'success' });
      } finally {
        this.aiSmartLoading = false;
      }
    },
    applyAiSuggestion(res) {
      this.manageRevision = res.revision;
      this.categories = this.directoriesToTree(res.directories || {});
      this.plugins = (res.plugins || []).map(plugin => ({
        ...plugin,
        id: String(plugin.id),
        directory_id: plugin.directory_id ? String(plugin.directory_id) : '',
      }));
      this.dirty = true;
      this.resetSelection();
    },
    async handleSave() {
      this.saving = true;
      try {
        const assignments = {};
        this.plugins.forEach(({ id, directory_id: directoryId }) => {
          const next = directoryId ? String(directoryId) : '';
          if (this.originalAssignments[String(id)] !== next) {
            assignments[String(id)] = next;
          }
        });
        const next = await this.saveDirectoryManage({
          space_id: this.spaceId,
          expected_revision: this.manageRevision,
          directories: this.treeToDirectories(this.categories),
          assignments,
        });
        if (next && next.revision !== undefined) this.manageRevision = next.revision;
        this.dirty = false;
        this.$bkMessage({ message: this.$t('保存成功'), theme: 'success' });
      } finally {
        this.saving = false;
      }
    },
    handleBack() {
      this.goPluginManage();
    },
    goPluginManage() {
      this.$router.push({
        name: 'spaceAdmin',
        query: { ...this.$route.query, activeTab: 'pluginManage' },
      });
    },
  },
};
</script>

<style lang="scss" scoped>
.category-manage {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;

  .page-header {
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    padding: 0 16px;
    background: #fff;
    box-shadow: 0 1px 1px rgba(25, 25, 41, .02);

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;

      .back-icon {
        font-size: 28px;
        color: #3a84ff;
        cursor: pointer;
      }

      .page-title {
        font-size: 16px;
        line-height: 24px;
        color: #111214;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;

      .header-btn {
        min-width: 88px;
        height: 32px;
        border-radius: 6px;
        font-size: 14px;
      }
    }
  }

  .page-main {
    flex: 1;
    min-height: 0;
    padding: 16px;
    overflow-y: auto;
  }


  .manage-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    background: #fff;
    max-width: 1280px;
    border-radius: 8px;
    box-shadow: 0 1px 2px rgba(25, 25, 41, .02);
  }

  .manage-alert {
    display: flex;
    gap: 8px;
    padding: 6px 8px;
    background: #f0f4ff;
    border: 1px solid #b0c8ff;
    border-radius: 6px;

    .alert-icon {
      flex-shrink: 0;
      padding: 2px 0;
      font-size: 16px;
      color: #3974ff;
    }

    .alert-list {
      flex: 1;
      margin: 0;
      padding-left: 18px;
      font-size: 12px;
      line-height: 20px;
      color: #4e5e7a;
      li {
        list-style: disc;
      }
    }
  }


  .manage-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;

    .ai-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      height: 32px;
      padding: 0 16px 0 12px;
      font-size: 13px;
      font-family: "PingFang SC";
      color: #fff;
      background: linear-gradient(104deg, #6066ff 0%, #8c63ff 100%);
      border-radius: 6px;
      cursor: pointer;
      i {
        font-size: 16px;
      }
    }

    .tool-btn {
      display: inline-flex;
      align-items: center;
      padding: 0 16px;
      font-size: 13px;
      border-radius: 6px;

      .btn-icon {
        font-size: 20px;
      }
      .del-icon {
        font-size: 16px;
      }
    }

    .tool-divider {
      width: 1px;
      height: 16px;
      background: #e4e9f2;
    }

    .toolbar-search {
      position: relative;
      flex: 1;
      min-width: 200px;

      ::v-deep .bk-form-input {
        border: 1px solid #C1CDE5;
        border-radius: 6px;
        background: #FFF;

        &:focus {
          border-color: #3a84ff;
        }
      }

      .search-dropdown {
        position: absolute;
        top: 36px;
        left: 0;
        right: 0;
        z-index: 20;
        max-height: 320px;
        overflow-y: auto;
        background: #fff;
        border: 1px solid #e4e9f2;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(25, 25, 41, .06);

        .search-option {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          border-bottom: 1px solid #e4e9f2;
          cursor: pointer;

          &:last-child {
            border-bottom: none;
          }

          &:hover {
            background: #f2f6fc;
          }

          .option-icon {
            flex-shrink: 0;
            font-size: 24px;
            color: #8f9fbd;

            &.is-plugin {
              font-size: 16px;
              color: #3fc06d;
            }
          }

          .option-text {
            flex: 1;
            min-width: 0;
          }

          .option-name {
            margin: 0;
            overflow: hidden;
            font-size: 12px;
            font-weight: 500;
            line-height: 20px;
            color: #111214;
            text-overflow: ellipsis;
            white-space: nowrap;

            .option-hit {
              color: #3974ff;
            }
          }

          .option-path {
            margin: 0;
            overflow: hidden;
            font-size: 12px;
            line-height: 20px;
            color: #8f9fbd;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
      }
    }
  }

  .manage-columns {
    display: flex;
    height: calc(100vh - 320px);
    min-height: 480px;
    border: 1px solid #c1cde5;
    border-radius: 8px;
    overflow: hidden;

    .column {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-width: 0;

      &:not(.is-last) {
        border-right: 1px solid #c1cde5;
      }

      .column-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-shrink: 0;
        height: 40px;
        padding: 0 12px;
        background: #f2f6fc;

        .column-title {
          font-size: 13px;
          font-weight: 500;
          line-height: 22px;
          color: #111214;
        }

        .column-meta {
          font-size: 12px;
          line-height: 20px;
          color: #4e5e7a;

          b {
            font-weight: 600;
          }
        }
      }

      .column-body {
        position: relative;
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        background: #fff;

        .column-empty {
          margin-top: 40px;
        }

        &.is-col-drop-ok,
        &.is-col-drop-deny {
          &::after {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            z-index: 5;
            border: 2px solid #3974ff;
            pointer-events: none;
          }
        }

        &.is-col-drop-ok {
          background: #e5edff;
        }

        &.is-col-drop-deny {
          background: #ffebeb;

          &::after {
            border-color: #e54040;
          }
        }
      }
    }
  }

  .cate-row {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 36px;
    padding: 0 8px;
    background: #fff;
    cursor: pointer;
    user-select: none;
    position: relative;
    i {
        color: #c1cde5;
    }

    &:hover {
      background: #f5f7fa;
    }

    &.is-active {
      background: #e5edff;
    }

    &.is-flash {
      animation: locate-flash .65s ease-in-out 2;
    }


    &.is-dragging {
      opacity: .35;
    }

    &.is-drop-before-ok::before,
    &.is-drop-before-deny::before,
    &.is-drop-after-ok::after,
    &.is-drop-after-deny::after {
      content: '';
      position: absolute;
      right: 0;
      left: 0;
      z-index: 1;
      height: 3px;
      border-radius: 2px;
      pointer-events: none;
    }

    &.is-drop-before-ok::before,
    &.is-drop-before-deny::before {
      top: -2px;
    }

    &.is-drop-after-ok::after,
    &.is-drop-after-deny::after {
      bottom: -2px;
    }

    &.is-drop-before-ok::before,
    &.is-drop-after-ok::after {
      background: #3974ff;
    }

    &.is-drop-before-deny::before,
    &.is-drop-after-deny::after {
      background: #e54040;
    }

    &.is-drop-into-ok {
      background: #e5edff;
      outline: 2px solid #3974ff;
      outline-offset: -2px;
    }

    &.is-drop-into-deny {
      background: #ffebeb;
      outline: 2px solid #e54040;
      outline-offset: -2px;
    }

    .row-drag {
      flex-shrink: 0;
      font-size: 14px;
      color: #c4c6cc;
      cursor: grab;
    }

    .row-checkbox {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
    }
    .uncategorized-checkbox {
        padding-left: 22px;
        .bk-form-checkbox .bk-checkbox {
            border: 1px solid #979ba5;
        }
    }

    .row-icon {
      flex-shrink: 0;
      font-size: 16px;
      color: #8f9fbd;

      &.is-plugin {
        color: #3fc06d;
      }
    }

    .row-name {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      color: #111214;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .row-count-tag {
      flex-shrink: 0;
      min-width: 18px;
      padding: 0 5px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      font-weight: 700;
      line-height: 18px;
      color: #8f9fbd;
      text-align: center;
      background: #f0f4fa;
      border-radius: 999px;
    }

    .row-arrow {
      flex-shrink: 0;
      font-size: 20px;
      color: #8f9fbd;
    }
  }

  .row-divider {
    height: 1px;
    background: #e4e9f2;
  }

  /* 拖拽光标 */
  .drag-cursor {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 3000;
    font-size: 18px;
    line-height: 1;
    color: #111214;
    pointer-events: none;
    will-change: transform;
  }

  /* 拖拽 ghost */
  .drag-ghost {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 2999;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 36px;
    max-width: 280px;
    padding: 0 24px 0 12px;
    background: #fff;
    border: 1px solid #3974ff;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(25, 25, 41, .06);
    pointer-events: none;
    will-change: transform;

    .ghost-count {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      min-width: 18px;
      height: 18px;
      padding: 0 5px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      color: #3974ff;
      background: #e5edff;
      border-radius: 4px;
    }

    .ghost-icon {
      flex-shrink: 0;
      margin-right: -2px;
      font-size: 16px;
      color: #8f9fbd;

      &.is-plugin {
        color: #3fc06d;
      }
    }

    .ghost-name {
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      color: #111214;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }


  .drag-deny-tip {
    position: fixed;
    z-index: 3001;
    max-width: 280px;
    padding: 6px 8px;
    font-size: 12px;
    line-height: 20px;
    color: #fff;
    background: rgba(0, 0, 0, .8);
    border-radius: 4px;
    transform: translateY(-50%);
    pointer-events: none;

    &::before {
      content: '';
      position: absolute;
      top: 50%;
      left: -5px;
      width: 0;
      height: 0;
      border: 5px solid transparent;
      border-right-color: rgba(0, 0, 0, .8);
      border-left-width: 0;
      transform: translateY(-50%);
    }
  }

  @keyframes locate-flash {
    0%, 100% {
      background: #fff;
    }

    50% {
      background: #ffedd1;
    }
  }

  .del-btn-wrap,
  .move-btn-wrap {
    display: inline-flex;
    cursor: not-allowed;

    .bk-button.is-disabled {
      pointer-events: none;
      cursor: not-allowed;
    }
  }
}
</style>

<style lang="scss">
.bk-message-wrap {
  .bk-message-content {
    white-space: normal;
    word-break: break-all;
    overflow: visible;
    text-overflow: clip;
    max-width: 100%;
  }
}
.category-select-popover {
    background: #fff;
    .tippy-tooltip {
        padding: 0;
        border: 1px solid #dcdee5;
        background-color: #fff !important;
        border-radius: 2px;
        box-shadow: 0 1px 2px rgba(25, 25, 41, 0.02);
    }
}
.ai-classify-tippy {
    .tippy-tooltip {
        box-sizing: border-box;
        top: -10px;
        left: -8px;
        padding: 0;
        background: #FFF;
        border: 1px solid #C1CDE5;
        border-radius: 8px;
        box-shadow: 0 2px 8px 0 rgba(25, 25, 41, 0.06);
    }
}
.ai-classify-popover {
    padding: 8px;

    .panel-footer {
        display: flex;
        justify-content: flex-end;
        padding-right: 8px;
        padding-bottom: 8px;
    }

    .ai-submit-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: #7A7FFF;
        border-radius: 8px;
        cursor: pointer;
        color: #fff;
        font-size: 28px;

        &.is-loading {
            cursor: default;
            opacity: .8;
        }
    }
    @keyframes ai-smart-rotate {
        to {
            transform: rotate(360deg);
        }
    }
    .ai-textarea {
        display: block;
        box-sizing: border-box;
        width: 100%;
        height: 70px;
        margin-bottom: 8px;
        line-height: 20px;
        color: #313238;
        border: none;
        resize: none;
        padding: 11px 0 0 11px;
    }
}
.create-dialog {
    .bk-dialog-content {
        border-radius: 6px;
        overflow: hidden;
    }
    .bk-dialog-footer {
      .bk-button {
        border-radius: 6px;
      }
    }
    .bk-dialog-header {
        padding: 0px 24px 20px;
    }
    .bk-select,
    .bk-form-input {
        border-radius: 6px;
        border: 1px solid #C1CDE5;
        background: #FFF;
    }
    .bk-select.is-focus,
    .bk-form-input:focus {
        border-color: #3a84ff;
    }
}

.delete-confirm-dialog {
    .bk-dialog-content {
        position: relative;
        overflow: hidden;
        border-radius: 6px;

        &::before,
        &::after {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            pointer-events: none;
            background-repeat: no-repeat;
        }
        &::before {
            width: 190px;
            height: 132px;
            background-image: url('~@/assets/images/location-wai.svg');
        }
        &::after {
            width: 164px;
            height: 108px;
            background-image: url('~@/assets/images/location.svg');
        }
        .bk-dialog-header,
        .bk-dialog-body,
        .bk-dialog-footer {
            position: relative;
            z-index: 1;
        }
    }
    .bk-dialog-body {
        max-height: 500px;
        padding: 0 32px 24px;
        overflow-y: auto;
    }
    .bk-dialog-footer {
        border: none;
        padding: 0 32px 32px 0px;
        background: transparent;
        .bk-button {
            border-radius: 6px;
        }
    }
    .delete-desc {
        display: flex;
        flex-direction: column;
        margin: 0 0 12px;
        font-size: 12px;
        line-height: 20px;
        color: #4E5E7A;
        font-family: "PingFang SC";
    }

    .impact-loading-wrap {
        min-height: 80px;
    }

    .impact-table {
        border: 1px solid #C1CDE5;
        border-radius: 6px;
        background: #FFF;
        overflow: hidden;
        clear: both;

        &::before,
        &::after {
            display: none;
        }
        .bk-table-header-wrapper {
            border-radius: 6px 6px 0 0;
        }
        .bk-table-body-wrapper {
            border-radius: 0 0 6px 6px;
        }

        .bk-table-empty-block {
            height: 140px;
        }
        .bk-table-header-wrapper th {
            background: #f5f7fa;
        }
        .bk-table-body-wrapper {
            color: #4E5E7A;
            font-family: "PingFang SC";
        }
        .bk-table-header-label {
            color: #111214;
            font-weight: 500;
            font-family: "PingFang SC";
        }
    }

    .impact-block {
        margin-bottom: 12px;

        &:last-child {
            margin-bottom: 0;
        }
    }

    .impact-cate-name {
        margin: 0 0 8px;
        font-size: 12px;
        line-height: 20px;
        font-weight: 600;
        color: #313238;
        word-break: break-all;
    }

    .impact-num {
        font-weight: 600;
        color: #4E5E7A;
    }

    .impact-unit {
        color: #4E5E7A;
    }
}
body.is-dnd-dragging,
body.is-dnd-dragging * {
    cursor: none !important;
    user-select: none !important;
}
</style>
