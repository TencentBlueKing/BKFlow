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
  <bk-sideslider
    :is-show="visible"
    :transfer="true"
    :width="800"
    :title="$t('新插件策略')"
    ext-cls="new-plugin-category-sideslider"
    @update:isShow="handleVisibleChange">
    <div
      ref="contentEl"
      slot="content"
      v-bkloading="{ isLoading: strategyLoading }"
      class="strategy-slider-content">
      <bk-form
        ref="strategyForm"
        :model="draft"
        form-type="vertical">
        <div class="form-block">
          <div class="form-label is-required">
            {{ $t('新插件策略') }}
          </div>
          <div class="strategy-cards">
            <div
              v-for="card in strategyCards"
              :key="card.value"
              :class="['strategy-card', { 'is-active': draft.mode === card.value, 'is-flex': card.value === 'conditional' }]"
              @click="handleModeChange(card.value)">
              <div :class="['card-logo', { 'is-active': draft.mode === card.value }]">
                <i :class="card.iconClass" />
              </div>
              <div class="card-text">
                <p :class="['card-title', { 'is-active': draft.mode === card.value }]">
                  {{ card.title }}
                </p>
                <p class="card-desc">
                  {{ card.desc }}
                </p>
              </div>
            </div>
          </div>
        </div>
        <!-- 全部直接通过 -->
        <template v-if="draft.mode === 'visible'">
          <div class="form-block all-visible-block">
            <div class="form-label is-required">
              {{ $t('通过后的插件') }}
            </div>
            <bk-radio-group
              v-model="draft.visible_after_pass"
              class="radio-group">
              <bk-radio :value="'uncategorized'">
                {{ enterUncategorizedText }}
              </bk-radio>
              <bk-radio :value="'ai'">
                {{ $t('AI 自动决定目录') }}
              </bk-radio>
            </bk-radio-group>
          </div>
          <div
            v-if="draft.visible_after_pass === 'ai'"
            class="form-block all-visible-block">
            <div class="form-label is-required">
              {{ $t('AI 自由范围') }}
            </div>
            <bk-radio-group
              v-model="draft.visible_ai_scope"
              class="radio-group">
              <bk-radio :value="'increment'">
                {{ $t('仅对增量分类（不影响已有目录）') }}
              </bk-radio>
              <bk-radio :value="'free'">
                {{ $t('完全自由（可对存量修改）') }}
              </bk-radio>
            </bk-radio-group>
          </div>
        </template>
        <!-- 设条件自动通过 -->
        <template v-else-if="draft.mode === 'conditional'">
          <div class="condition-group">
            <div
              v-for="(cond, index) in draft.conditions"
              :key="index"
              class="condition-card">
              <div class="condition-tag">
                {{ $t('启用条件') }} {{ conditionLetter(index) }}
              </div>
              <i
                v-bk-tooltips.top="$t('删除')"
                class="commonicon-icon common-icon-delete condition-del"
                @click="removeCondition(index)" />

              <!-- 启用来源：跨条件组去重，已被其他条件选中的来源置灰 -->
              <bk-form-item
                :label="$t('启用来源')"
                :required="true"
                :property="`conditions.${index}.sources`"
                :rules="conditionSourcesRules(index)">
                <bk-select
                  v-model="cond.sources"
                  class="source-select"
                  ext-cls="source-select-popover"
                  display-tag
                  :multiple="true"
                  :searchable="true">
                  <bk-option-group
                    v-for="group in sources"
                    :key="group.id"
                    :name="group.name">
                    <bk-option
                      v-for="item in getSourceOptions(group)"
                      :id="item.id"
                      :key="item.id"
                      :name="item.name"
                      :disabled="isSourceDisabled(item.id, index)">
                      <span
                        v-bk-tooltips="{ content: getDisabledTip(item.id, index), disabled: !isSourceDisabled(item.id, index) }">
                        {{ item.label }}
                      </span>
                    </bk-option>
                  </bk-option-group>
                </bk-select>
              </bk-form-item>
              <!-- 通过后的插件 -->
              <div class="form-item">
                <div class="form-label is-required">
                  {{ $t('通过后的插件') }}
                </div>
                <bk-radio-group
                  v-model="cond.after_pass"
                  class="radio-group">
                  <bk-radio :value="'uncategorized'">
                    {{ enterUncategorizedText }}
                  </bk-radio>
                  <bk-radio :value="'ai'">
                    {{ $t('AI 自动决定目录') }}
                  </bk-radio>
                  <bk-radio
                    v-if="hasAssignableCategory"
                    :value="'assign'">
                    {{ $t('指派特定目录') }}
                  </bk-radio>
                </bk-radio-group>
              </div>

              <!-- AI 自动决定目录时：AI 自由范围 -->
              <div
                v-if="cond.after_pass === 'ai'"
                class="form-item">
                <div class="form-label is-required">
                  {{ $t('AI 自由范围') }}
                </div>
                <bk-radio-group
                  v-model="cond.ai_scope"
                  class="radio-group">
                  <bk-radio :value="'increment'">
                    {{ $t('仅对增量分类（不影响已有目录）') }}
                  </bk-radio>
                  <bk-radio :value="'free'">
                    {{ $t('完全自由（可对存量修改）') }}
                  </bk-radio>
                </bk-radio-group>
              </div>

              <!-- 指派特定目录时：指派目录（编辑态暂存级联路径，保存时取末级目录 id） -->
              <bk-form-item
                v-if="cond.after_pass === 'assign'"
                :label="$t('指派目录')"
                :required="true"
                :property="`conditions.${index}.assign_directory_id`"
                :rules="conditionAssignRules(index)">
                <bk-cascade
                  v-model="cond.assign_directory_id"
                  class="assign-cascade"
                  :list="categories"
                  :check-any-level="true"
                  :clearable="true" />
              </bk-form-item>
            </div>

            <div
              class="add-condition"
              @click="addCondition">
              <i class="commonicon-icon common-icon-add" />
              {{ $t('添加启用条件') }}
            </div>
          </div>
        </template>
      </bk-form>
    </div>
    <div
      slot="footer"
      :class="['strategy-slider-footer', { 'is-divided': footerDivided }]">
      <bk-button
        theme="primary"
        @click="handleSave">
        {{ $t('保存') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </bk-sideslider>
</template>

<script>
import tools from '@/utils/tools.js';
import { mapActions } from 'vuex';

export default {
  name: 'StrategySideslider',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    // 空间 id（查询启用来源必填）
    spaceId: {
      type: [String, Number],
      default: '',
    },
    // 分类目录树（指派目录级联选项，两级）
    categories: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    const emptyCondition = {
      sources: [],
      after_pass: 'uncategorized',
      ai_scope: 'increment',
      assign_directory_id: [],
    };
    return {
      emptyCondition,
      draft: this.normalizeStrategy({}, emptyCondition),
      strategyLoading: false,
      sources: [],
      footerDivided: false,
    };
  },
  computed: {
    enterUncategorizedText() {
      return this.$t('进入 <未分类> 目录');
    },
    // 是否存在可指派的目录
    hasAssignableCategory() {
      return (this.categories || []).length > 0;
    },
    strategyCards() {
      return [
        {
          value: 'review',
          title: this.$t('全部需要审核'),
          desc: this.$t('进入“待审核”状态'),
          iconClass: 'commonicon-icon common-icon-daishenhe',
        },
        {
          value: 'visible',
          title: this.$t('全部直接通过'),
          desc: this.$t('直接变成“可用”状态'),
          iconClass: 'commonicon-icon common-icon-yuan-dui',
        },
        {
          value: 'conditional',
          title: this.$t('设条件自动通过'),
          desc: this.$t('满足条件直接“可用”，其他需审核'),
          iconClass: 'bk-icon icon-funnel',
        },
      ];
    },
  },
  watch: {
    visible(val) {
      if (val) {
        this.initStrategy();
        this.loadSources();
        this.$nextTick(this.bindFooterScrollWatch);
      } else {
        this.unbindFooterScrollWatch();
      }
    },
  },
  beforeDestroy() {
    this.unbindFooterScrollWatch();
  },
  methods: {
    ...mapActions('pluginManage', [
      'getStrategy',
      'getStrategySources',
    ]),
    // 打开侧滑时拉取当前策略
    async initStrategy() {
      this.strategyLoading = true;
      try {
        const strategy = await this.getStrategy({ space_id: this.spaceId });
        this.draft = this.normalizeStrategy(strategy || {}, this.emptyCondition);
      } catch (e) {
        console.warn(e);
        this.draft = this.normalizeStrategy({}, this.emptyCondition);
      } finally {
        this.strategyLoading = false;
      }
    },
    normalizeStrategy(val = {}, emptyCondition) {
      const empty = emptyCondition || this.emptyCondition;
      const conditions = (val.conditions || []).length
        ? val.conditions.map(item => ({
          sources: [...(item.sources || [])],
          after_pass: item.after_pass === 'assign' && !this.hasAssignableCategory
            ? 'uncategorized'
            : (item.after_pass || 'uncategorized'),
          ai_scope: item.ai_scope || 'increment',
          assign_directory_id: this.directoryIdToPath(item.assign_directory_id),
        }))
        : [tools.deepClone(empty)];
      return {
        mode: val.mode || 'review',
        visible_after_pass: val.visible_after_pass || 'uncategorized',
        visible_ai_scope: val.visible_ai_scope || 'increment',
        conditions,
      };
    },
    // 后端单个目录 id → 级联路径
    directoryIdToPath(directoryId) {
      if (directoryId === null || directoryId === undefined || directoryId === '') return [];
      const parent = (this.categories || []).find(cate => String(cate.id) === String(directoryId)
        || (cate.children || []).some(sub => String(sub.id) === String(directoryId)));
      if (!parent) return [directoryId];
      const child = (parent.children || []).find(sub => String(sub.id) === String(directoryId));
      return child ? [parent.id, child.id] : [parent.id];
    },
    handleVisibleChange(val) {
      this.$emit('update:visible', val);
    },
    async loadSources() {
      if (this.sources.length) return;
      this.sources = (await this.getStrategySources({ space_id: this.spaceId })) || [];
    },

    updateFooterDivided() {
      const { scrollBox } = this;
      if (!scrollBox) return;
      this.footerDivided = scrollBox.scrollHeight - scrollBox.clientHeight > 1;
    },
    bindFooterScrollWatch() {
      const { contentEl } = this.$refs;
      this.scrollBox = contentEl && contentEl.parentElement;
      if (!this.scrollBox) return;
      const ResizeObserverImpl = window.ResizeObserver;
      if (ResizeObserverImpl) {
        this.resizeObserver = new ResizeObserverImpl(this.updateFooterDivided);
        this.resizeObserver.observe(contentEl);
      }
      window.addEventListener('resize', this.updateFooterDivided);
      this.updateFooterDivided();
    },
    unbindFooterScrollWatch() {
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
        this.resizeObserver = null;
      }
      window.removeEventListener('resize', this.updateFooterDivided);
      this.scrollBox = null;
      this.footerDivided = false;
    },
    handleModeChange(value) {
      this.draft.mode = value;
      if (value === 'conditional' && !this.draft.conditions.length) {
        this.draft.conditions.push(tools.deepClone(this.emptyCondition));
      }
    },
    conditionLetter(index) {
      return String.fromCharCode(65 + (index % 26));
    },
    getSourceOptions(group) {
      if (group.whole) {
        return [{ id: group.id, name: group.name, label: group.name }];
      }
      return (group.children || []).map(item => ({
        id: item.id,
        name: `${group.name} / ${item.name}`,
        label: item.name,
      }));
    },
    // 启用来源跨条件组去重：已被其他条件选中的来源不可再选
    isSourceDisabled(sourceId, index) {
      return this.draft.conditions.some((cond, condIndex) => condIndex !== index && cond.sources.includes(sourceId),);
    },
    getDisabledTip(sourceId, index) {
      const ownerIndex = this.draft.conditions.findIndex((cond, condIndex) => condIndex !== index && cond.sources.includes(sourceId),);
      return this.$t('该来源已经被启用条件 {letter} 选择，无法重复选择', {
        letter: this.conditionLetter(ownerIndex),
      });
    },
    addCondition() {
      this.draft.conditions.push(tools.deepClone(this.emptyCondition));
    },
    removeCondition(index) {
      this.draft.conditions.splice(index, 1);
    },
    // 启用来源内联校验：非空即可，跨条件组重复由选项置灰兜底
    conditionSourcesRules(index) {
      return [{
        required: true,
        validator: () => (this.draft.conditions[index]?.sources || []).length > 0,
        message: this.$t('请选择启用来源'),
        trigger: 'change',
      }];
    },
    // 指派目录内联校验（仅在 after_pass=assign 时渲染）
    conditionAssignRules(index) {
      return [{
        required: true,
        // snake_case 为后端接口字段，用方括号字符串规避 camelcase 规则
        validator: () => (this.draft.conditions[index]?.['assign_directory_id'] || []).length > 0,
        message: this.$t('请选择指派目录'),
        trigger: 'change',
      }];
    },
    async handleSave() {
      if (this.draft.mode === 'conditional') {
        try {
          await this.$refs.strategyForm.validate();
        } catch (e) {
          return;
        }
      }
      const draft = JSON.parse(JSON.stringify(this.draft));
      const body = { mode: draft.mode };
      if (body.mode === 'visible') {
        body.visible_after_pass = draft.visible_after_pass;
        if (body.visible_after_pass === 'ai') {
          body.visible_ai_scope = draft.visible_ai_scope;
        }
      }
      if (body.mode === 'conditional') {
        body.conditions = (draft.conditions || []).map((cond) => {
          const item = {
            sources: cond.sources || [],
            after_pass: cond.after_pass,
          };
          if (item.after_pass === 'ai') {
            item.ai_scope = cond.ai_scope;
          }
          if (item.after_pass === 'assign') {
            item.assign_directory_id = (cond.assign_directory_id || []).slice(-1)[0] || '';
          }
          return item;
        });
      }
      this.$emit('save', body);
    },
    handleCancel() {
      this.$emit('update:visible', false);
    },
  },
};
</script>

<style lang="scss" scoped>
.strategy-slider-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
    padding: 24px;
}

.form-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.all-visible-block {
  margin-top: 24px;
}

.form-label {
    font-size: 12px;
    line-height: 20px;
    color: #4e5e7a;

    &.is-required::after {
        content: '*';
        margin-left: 2px;
        color: #ea3636;
        vertical-align: -0.4em;
    }
}
.strategy-cards {
    display: flex;
    gap: 12px;

    .strategy-card {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 236px;
        height: 60px;
        padding: 8px 12px;
        background: #fff;
        border: 1px solid #c1cde5;
        border-radius: 8px;
        cursor: pointer;

        &.is-flex {
            flex: 1;
            min-width: 0;
        }

        &.is-active {
            background: #f0f4ff;
            border: 2px solid #3974ff;
        }
    }

    .card-logo {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: 36px;
        height: 36px;
        background: #f0f4fa;
        border-radius: 6px;
        font-size: 20px;
        color: #4e5e7a;

        &.is-active {
            background: #3974ff;
            color: #fff;
        }
    }

    .card-text {
        min-width: 0;

        .card-title {
            margin: 0;
            font-size: 13px;
            font-weight: 500;
            line-height: 22px;
            color: #4e5e7a;

            &.is-active {
                color: #3974ff;
            }
        }

        .card-desc {
            margin: 0;
            font-size: 12px;
            line-height: 20px;
            color: #8f9fbd;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
    }
}

.radio-group {
    display: flex;
    align-items: center;
    gap: 24px;

    ::v-deep .bk-form-radio {
        margin-right: 0;

        .bk-radio-text {
            font-size: 12px;
            color: #4e5e7a;
        }
    }
}

.condition-group {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-top: 24px;
}

.condition-card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 19px;
    padding: 36px 24px 16px;
    background: #f2f6fc;
    border-radius: 6px;

    .condition-tag {
        position: absolute;
        top: 0;
        left: 0;
        display: flex;
        align-items: center;
        height: 28px;
        padding: 2px 8px;
        font-size: 13px;
        font-weight: 500;
        line-height: 22px;
        color: #fff;
        background: #4e5e7a;
        border-radius: 6px 0 8px 0;
    }

    .condition-del {
        position: absolute;
        top: 8px;
        right: 8px;
        font-size: 16px;
        color: #ea3636;
        cursor: pointer;
    }

    .source-select,
    .assign-cascade {
        width: 100%;
        border-radius: 6px;
        background: #fff;
    }
}

.add-condition {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    height: 42px;
    font-size: 13px;
    font-weight: 500;
    color: #3974ff;
    background: #e5edff;
    border-radius: 6px;
    cursor: pointer;
    i {
        font-size: 20px;
        margin-top: 1px;
    }
}
.strategy-slider-footer {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    gap: 8px;
    width: 100%;
    min-height: 48px;
    padding: 8px 24px;
    transition: background-color .2s ease, border-color .2s ease;

    .bk-button {
        width: 88px;
        border-radius: 6px;
    }

    &.is-divided {
        border-top: 1px solid var(--Neutral-7--, #e9edf5);
        background: var(--Neutral-10, #f7f9fc);
    }
}

</style>

<style lang="scss">
.source-select-popover {
    .bk-select-tag {
        background: #f0f4fa;
        border-radius: 4px;
    }
}
.new-plugin-category-sideslider {
    .bk-sideslider-footer {
        padding: 0;
        background: transparent !important;
        border: none !important;
    }
}
</style>
