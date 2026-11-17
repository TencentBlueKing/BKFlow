<template>
  <div class="category-select-panel">
    <div class="panel-search">
      <bk-input
        v-model="keyword"
        :clearable="true"
        right-icon="bk-icon icon-search"
        :placeholder="$t('搜索分类')" />
    </div>
    <template v-if="showAiRecommend || showUnclassified">
      <div
        v-if="aiRecommendOptions.length"
        class="ai-recommend-box">
        <div class="ai-recommend-header">
          <img
            :src="aiBluekingIcon"
            class="ai-icon"
            alt="">
          <span class="option-name ai-recommend-name">{{ $t('AI 推荐') }}</span>
        </div>
        <div
          v-for="opt in aiRecommendOptions"
          :key="opt.id"
          class="panel-option ai-recommend-item"
          @click="handleSelect(opt.id)">
          <span class="option-name">{{ opt.name }}</span>
        </div>
      </div>
      <div
        v-else-if="showAiRecommend"
        :class="['panel-option', { 'is-ai-loading': aiRecommendLoading }]"
        @click="handleSelect('', false, true)">
        <img
          :src="aiBluekingIcon"
          class="ai-icon"
          alt="">
        <span class="option-name ai-recommend-name">{{ aiRecommendLoading ? $t('AI 推荐获取中...') : $t('AI 推荐') }}</span>
      </div>
      <div
        v-if="showUnclassified"
        :class="[ 'panel-option' ]"
        @click="handleSelect('')">
        <i class="bk-icon icon-question-circle uncategorized-icon" />
        <span class="option-name">{{ $t('未分类') }}</span>
      </div>
      <div
        v-if="optionTree.length"
        class="panel-divider" />
    </template>
    <div
      v-for="group in optionTree"
      :key="group.id"
      class="panel-group">
      <div
        :class="['panel-option is-top', { active: activeId === group.id }]"
        @click="handleSelect(group.id)">
        <span class="option-name">{{ group.name }}</span>
      </div>
      <div
        v-if="group.children && group.children.length"
        class="panel-sub-list">
        <div
          v-for="sub in group.children"
          :key="sub.id"
          :class="['panel-option is-sub', { active: activeId === sub.id }]"
          @click="handleSelect(sub.id)">
          <span class="option-name">{{ sub.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import aiBluekingIcon from '@/assets/images/ai-blueking.svg';

export default {
  name: 'CategorySelectPanel',
  props: {
    categoryTree: {
      type: Array,
      default: () => [],
    },
    activeId: {
      type: [String, Number],
      default: '',
    },
    followSource: {
      type: Boolean,
      default: false,
    },
    selectableLevel: {
      type: String,
      default: 'all',
    },
    showUnclassified: {
      type: Boolean,
      default: true,
    },
    showAiRecommend: {
      type: Boolean,
      default: true,
    },
    // AI 建议的目标目录 id 列表
    aiRecommendIds: {
      type: Array,
      default: () => [],
    },
    // AI 建议拉取中
    aiRecommendLoading: {
      type: Boolean,
      default: false,
    },
    excludeIds: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      keyword: '',
      aiBluekingIcon,
    };
  },
  computed: {
    filteredTree() {
      const kw = (this.keyword || '').trim().toLowerCase();
      const tree = this.categoryTree || [];
      if (!kw) return tree;
      // 仅可选一级目录（selectableLevel === 'level1'）时，搜索只按一级目录名匹配
      if (this.selectableLevel === 'level1') {
        return tree.filter(group => (group.name || '').toLowerCase().includes(kw));
      }
      return tree.reduce((acc, group) => {
        const hitSelf = (group.name || '').toLowerCase().includes(kw);
        const children = hitSelf
          ? (group.children || [])
          : (group.children || []).filter(sub => (sub.name || '').toLowerCase().includes(kw));
        if (hitSelf || children.length) {
          acc.push({ ...group, children });
        }
        return acc;
      }, []);
    },
    optionTree() {
      const excluded = new Set(this.excludeIds || []);
      const onlyLevel1 = this.selectableLevel === 'level1';
      return this.filteredTree.reduce((acc, group) => {
        if (excluded.has(group.id)) return acc;
        const children = onlyLevel1
          ? []
          : (group.children || []).filter(sub => !excluded.has(sub.id));
        acc.push({ ...group, children });
        return acc;
      }, []);
    },
    // AI 建议目录项
    aiRecommendOptions() {
      const ids = new Set((this.aiRecommendIds || []).map(id => String(id)));
      if (!ids.size) return [];
      const onlyLevel1 = this.selectableLevel === 'level1';
      const options = [];
      (this.optionTree || []).forEach((group) => {
        if (ids.has(String(group.id))) {
          options.push({ id: group.id, name: group.name });
        }
        if (!onlyLevel1) {
          (group.children || []).forEach((sub) => {
            if (ids.has(String(sub.id))) {
              options.push({ id: sub.id, name: `${group.name}/${sub.name}` });
            }
          });
        }
      });
      return options;
    },
  },
  methods: {
    handleSelect(categoryId, followSource = false, isAiRecommend = false) {
      this.$emit('select', { categoryId, followSource, isAiRecommend });
    },
  },
};
</script>

<style lang="scss" scoped>
.category-select-panel {
  max-height: 474px;
  padding: 4px 0;
  overflow-y: auto;
  background: #fff;

  .panel-search {
    padding: 4px 8px;
  }

  .panel-option {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 32px;
    padding: 6px 12px;
    font-size: 12px;
    line-height: 20px;
    color: #4e5e7a;
    cursor: pointer;
    transition: background-color 0.15s ease;

    &:hover {
      background: #f2f6fc;
    }

    &.is-top {
      color: #111214;
    }

    &.is-sub {
      padding-left: 36px;
    }

    &.active {
      background: #f2f6fc;
    }
    .uncategorized-icon {
        font-size: 14px !important;
    }

    .ai-icon {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
    }

    &.is-ai-loading {
      cursor: default;
      opacity: 0.7;
    }

    .ai-recommend-name {
        background: linear-gradient(98deg, #4667F3 3.74%, #D287EA 96.48%);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .option-icon {
      flex-shrink: 0;
      font-size: 16px;
      color: #4e5e7a;
    }

    .option-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .option-extra {
      flex-shrink: 0;
      margin-left: auto;
      color: #8f9fbd;
    }
  }

  .panel-sub-list {
    position: relative;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      bottom: 0;
      left: 20px;
      width: 1px;
      background: #dcdee5;
    }
  }

  .panel-divider {
    height: 1px;
    margin: 4px 12px;
    background: #dcdee5;
  }

  .ai-recommend-box {
    margin: 4px 8px;
    border: 1px solid transparent;
    border-radius: 4px;
    background:
      linear-gradient(#fff, #fff) padding-box,
      linear-gradient(98deg, #4667F3 3.74%, #D287EA 96.48%) border-box;

    .ai-recommend-header {
      display: flex;
      align-items: center;
      gap: 8px;
      height: 32px;
      padding: 6px 12px;
      font-size: 12px;

      .ai-icon {
        flex-shrink: 0;
        width: 16px;
        height: 16px;
      }
    }

    .ai-recommend-item {
      border-radius: 0;

      &:last-child {
        border-radius: 0 0 3px 3px;
      }
    }
  }
}
</style>
