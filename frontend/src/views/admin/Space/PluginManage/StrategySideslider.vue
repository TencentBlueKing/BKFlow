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
      class="strategy-slider-content">
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
        <div class="form-block">
          <div class="form-label is-required">
            {{ $t('通过后的插件') }}
          </div>
          <bk-radio-group
            v-model="draft.visibleAfterPass"
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
          v-if="draft.visibleAfterPass === 'ai'"
          class="form-block">
          <div class="form-label is-required">
            {{ $t('AI 自由范围') }}
          </div>
          <bk-radio-group
            v-model="draft.visibleAiScope"
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
              {{ $t('直通条件') }} {{ conditionLetter(index) }}
            </div>
            <i
              v-bk-tooltips.top="$t('删除')"
              class="commonicon-icon common-icon-delete condition-del"
              @click="removeCondition(index)" />

            <!-- 直通来源：跨条件组去重，已被其他条件选中的来源置灰 -->
            <div class="form-item">
              <div class="form-label is-required">
                {{ $t('直通来源') }}
              </div>
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
                    :name="item.label"
                    :disabled="isSourceDisabled(item.id, index)">
                    <span
                      v-bk-tooltips="{ content: getDisabledTip(item.id, index), disabled: !isSourceDisabled(item.id, index) }">
                      {{ item.label }}
                    </span>
                  </bk-option>
                </bk-option-group>
              </bk-select>
            </div>
            <!-- 通过后的插件 -->
            <div class="form-item">
              <div class="form-label is-required">
                {{ $t('通过后的插件') }}
              </div>
              <bk-radio-group
                v-model="cond.afterPass"
                class="radio-group">
                <bk-radio :value="'uncategorized'">
                  {{ enterUncategorizedText }}
                </bk-radio>
                <bk-radio :value="'ai'">
                  {{ $t('AI 自动决定目录') }}
                </bk-radio>
                <bk-radio :value="'assign'">
                  {{ $t('指派特定目录') }}
                </bk-radio>
              </bk-radio-group>
            </div>

            <!-- AI 自动决定目录时：AI 自由范围 -->
            <div
              v-if="cond.afterPass === 'ai'"
              class="form-item">
              <div class="form-label is-required">
                {{ $t('AI 自由范围') }}
              </div>
              <bk-radio-group
                v-model="cond.aiScope"
                class="radio-group">
                <bk-radio :value="'increment'">
                  {{ $t('仅对增量分类（不影响已有目录）') }}
                </bk-radio>
                <bk-radio :value="'free'">
                  {{ $t('完全自由（可对存量修改）') }}
                </bk-radio>
              </bk-radio-group>
            </div>

            <!-- 指派特定目录时：指派目录 -->
            <div
              v-if="cond.afterPass === 'assign'"
              class="form-item">
              <div class="form-label is-required">
                {{ $t('指派目录') }}
              </div>
              <bk-cascade
                v-model="cond.assignCategory"
                class="assign-cascade"
                :list="categories"
                :check-any-level="true"
                :clearable="true" />
            </div>
          </div>

          <div
            class="add-condition"
            @click="addCondition">
            <i class="commonicon-icon common-icon-add" />
            {{ $t('添加直通条件') }}
          </div>
        </div>
      </template>
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
import { getStrategySources } from './api';
import { createDefaultStrategy } from './shared';

export default {
  name: 'StrategySideslider',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    // 当前策略对象：{ mode, visibleAfterPass, visibleAiScope, conditions }
    strategy: {
      type: Object,
      default: createDefaultStrategy,
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
      afterPass: 'uncategorized',
      aiScope: 'increment',
      assignCategory: [],
    };
    return {
      emptyCondition,
      draft: this.normalizeStrategy(this.strategy, emptyCondition),
      sources: [],
      footerDivided: false,
    };
  },
  computed: {
    enterUncategorizedText() {
      return this.$t('进入 <未分类> 目录');
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
        this.draft = this.normalizeStrategy(this.strategy, this.emptyCondition);
        this.loadSources();
        this.$nextTick(this.bindFooterScrollWatch);
      } else {
        this.unbindFooterScrollWatch();
      }
    },
  },
  created() {
    this.loadSources();
  },
  beforeDestroy() {
    this.unbindFooterScrollWatch();
  },
  methods: {
    normalizeStrategy(val, emptyCondition = this.emptyCondition) {
      const conditions = val.conditions.length
        ? val.conditions.map(item => ({
          ...item,
          sources: [...item.sources],
          assignCategory: [...item.assignCategory],
        }))
        : [tools.deepClone(emptyCondition)];
      return { ...val, conditions };
    },
    handleVisibleChange(val) {
      this.$emit('update:visible', val);
    },
    async loadSources() {
      if (this.sources.length) return;
      const { groups } = await getStrategySources();
      this.sources = groups || [];
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
      return (group.children || []).map((item) => {
        if (item.whole) {
          return { id: group.id, label: group.name };
        }
        return { id: item.id, label: `${item.name} / ${group.name}` };
      });
    },
    // 直通来源跨条件组去重：已被其他条件选中的来源不可再选
    isSourceDisabled(sourceId, index) {
      return this.draft.conditions.some((cond, condIndex) => condIndex !== index && cond.sources.includes(sourceId),);
    },
    getDisabledTip(sourceId, index) {
      const ownerIndex = this.draft.conditions.findIndex((cond, condIndex) => condIndex !== index && cond.sources.includes(sourceId),);
      return this.$t('该来源已经被直通条件 {letter} 选择，无法重复选择', {
        letter: this.conditionLetter(ownerIndex),
      });
    },
    addCondition() {
      this.draft.conditions.push(tools.deepClone(this.emptyCondition));
    },
    removeCondition(index) {
      this.draft.conditions.splice(index, 1);
    },
    handleSave() {
      if (this.draft.mode === 'conditional') {
        for (let i = 0; i < this.draft.conditions.length; i++) {
          const cond = this.draft.conditions[i];
          const label = `${this.$t('直通条件')} ${this.conditionLetter(i)}`;
          if (!cond.sources.length) {
            this.$bkMessage({
              message: this.$t('请为{condition}选择直通来源', { condition: label }),
              theme: 'error',
            });
            return;
          }
          if (cond.afterPass === 'assign' && !cond.assignCategory.length) {
            this.$bkMessage({
              message: this.$t('请为{condition}选择指派目录', { condition: label }),
              theme: 'error',
            });
            return;
          }
        }
      }
      this.$emit('save', JSON.parse(JSON.stringify(this.draft)));
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
