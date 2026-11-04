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
  <div class="plugin-sidebar">
    <div class="sidebar-top">
      <bk-button
        theme="primary"
        class="batch-btn"
        @click="$emit('batch-manage')">
        <i class="commonicon-icon common-icon-content-mulu batch-btn-icon" />
        <span>{{ $t('目录批量管理') }}</span>
      </bk-button>
      <bk-input
        v-model="keyword"
        class="cate-search"
        :placeholder="$t('搜索 插件目录')"
        :clearable="true"
        right-icon="bk-icon icon-search" />
    </div>
    <div class="sidebar-body">
      <div
        v-for="item in topItems"
        :key="item.id"
        :class="['cate-item', { active: item.id === selected }]"
        @click="$emit('select', item.id)">
        <i :class="['cate-icon', item.icon]" />
        <span class="cate-name">{{ item.name }}</span>
        <span class="cate-count">{{ counts[item.countKey] || 0 }}</span>
      </div>
      <div class="cate-divider" />
      <div class="cate-tree">
        <div
          v-for="node in visibleNodes"
          :key="node.id"
          :class="['cate-node', `is-level-${node.level}`, { active: node.id === selected }]"
          @click="$emit('select', node.id)">
          <i
            v-if="node.level === 1 && node.hasChildren"
            :class="['bk-icon', 'node-expand-icon', expandedIds.includes(node.id) ? 'icon-down-shape' : 'icon-right-shape']"
            @click.stop="handleToggleExpand(node)" />
          <i
            :class="[
              'cate-icon',
              node.level === 1 ? categoryIcons.level1 : categoryIcons.level2,
            ]" />
          <span
            v-bk-overflow-tips
            class="cate-name">{{ node.name }}</span>
          <span class="cate-count">{{ counts.tree ? (counts.tree[node.id] || 0) : 0 }}</span>
        </div>
        <bk-exception
          v-if="!visibleNodes.length"
          class="cate-empty"
          type="search-empty"
          scene="part" />
      </div>
    </div>
  </div>
</template>

<script>
import { CATEGORY_ICONS } from './shared';

export default {
  name: 'CategorySidebar',
  props: {
    categories: {
      type: Array,
      default: () => [],
    },
    counts: {
      type: Object,
      default: () => ({ all: 0, recommend: 0, uncategorized: 0, tree: {} }),
    },
    selected: {
      type: String,
      default: 'all',
    },
  },
  data() {
    return {
      keyword: '',
      expandedIds: [],
    };
  },
  computed: {
    categoryIcons() {
      return CATEGORY_ICONS;
    },
    topItems() {
      return [
        { id: 'all', name: this.$t('全部插件'), icon: CATEGORY_ICONS.all, countKey: 'all' },
        { id: 'recommend', name: this.$t('空间推荐'), icon: CATEGORY_ICONS.recommend, countKey: 'recommend' },
        { id: 'uncategorized', name: this.$t('未分类插件'), icon: CATEGORY_ICONS.uncategorized, countKey: 'uncategorized' },
      ];
    },
    // 扁平化后的可见节点（搜索命中时父级强制展开）
    visibleNodes() {
      const kw = this.keyword.trim().toLowerCase();
      const nodes = [];
      (this.categories || []).forEach((group) => {
        const children = group.children || [];
        const groupHit = !kw || (group.name || '').toLowerCase().includes(kw);
        const hitChildren = kw
          ? children.filter(child => (child.name || '').toLowerCase().includes(kw))
          : children;
        if (!groupHit && !hitChildren.length) return;
        nodes.push({ ...group, level: 1, parentId: '', hasChildren: children.length > 0 });
        if (!kw && !this.expandedIds.includes(group.id)) return;
        // 父级自身命中时展示全部子级，否则只展示命中的子级
        (groupHit ? children : hitChildren).forEach((child) => {
          nodes.push({ ...child, level: 2, parentId: group.id, hasChildren: false });
        });
      });
      return nodes;
    },
  },
  watch: {
    categories: {
      immediate: true,
      handler(list) {
        // 新增分类后保持原有展开态，只为新出现的一级分类补默认展开
        const ids = (list || []).filter(item => (item.children || []).length).map(item => item.id);
        const kept = this.expandedIds.filter(id => ids.includes(id));
        const added = ids.filter(id => !this.expandedIds.includes(id));
        this.expandedIds = [...kept, ...added];
      },
    },
  },
  methods: {
    handleToggleExpand(node) {
      this.expandedIds = this.expandedIds.includes(node.id)
        ? this.expandedIds.filter(id => id !== node.id)
        : [...this.expandedIds, node.id];
    },
  },
};
</script>

<style lang="scss" scoped>
.plugin-sidebar {
    display: flex;
    flex-direction: column;
    width: 240px;
    flex-shrink: 0;
    height: 100%;
    background: #f2f6fc;
    border-radius: 2px;
    overflow: hidden;

    .sidebar-top {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 16px;
        padding: 0 16px;
        .batch-btn {
            width: 100%;
            height: 32px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            font-family: "PingFang SC";
            box-shadow: 0 2px 4px rgba(57, 116, 255, .12);

            ::v-deep .bk-button-text {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
            }

            .batch-btn-icon {
                font-size: 16px;
            }
        }

        .cate-search {
            ::v-deep .bk-form-input {
                height: 32px;
                border-color: #c1cde5;
                border-radius: 6px;
                font-size: 12px;

                &::placeholder {
                    color: #c1cde5;
                }
            }
        }
    }

    .sidebar-body {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 12px 0 16px 16px;
    }

    /* 顶部固定项行样式 */
    .cate-item {
        display: flex;
        align-items: center;
        padding: 8px 12px 8px 14px;
        border-radius: 6px;
        cursor: pointer;

        &:hover {
            background: #e4e9f2;
        }

        &.active {
            background: #e5edff;
            .cate-name,
            .cate-count,
            .cate-icon {
                color: #3974ff;
            }
        }
    }
    .cate-icon {
        flex-shrink: 0;
        margin-right: 8px;
        margin-left: 3px;
        font-size: 16px;
        color: #8f9fbd;
    }
    .cate-name {
        flex: 1;
        min-width: 0;
        font-family: "PingFang SC";
        font-size: 13px;
        font-weight: 500;
        line-height: 20px;
        color: #111214;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .cate-count {
        flex-shrink: 0;
        font-family: Arial;
        font-size: 12px;
        font-weight: 700;
        line-height: 20px;
        color: #8f9fbd;
    }

    .cate-divider {
        height: 1px;
        margin: 4px 0;
        background: #e4e9f2;
    }

    .cate-tree {
        position: relative;
    }

    .cate-empty {
        margin-top: 20px;

        ::v-deep .bk-exception-text {
            font-size: 12px;
        }
    }

    /* 目录节点：1 级 pl 14、2 级 pl 38 并带左侧引导线 */
    .cate-node {
        position: relative;
        display: flex;
        align-items: center;
        padding: 8px 12px 8px 14px;
        border-radius: 6px;
        cursor: pointer;

        &.is-level-2 {
            padding-left: 38px;

            /* 引导线：与一级图标中心对齐 */
            &::before {
                content: "";
                position: absolute;
                top: 0;
                bottom: 0;
                left: 22px;
                width: 1px;
                background: #c1cde5;
            }
        }

        &:hover {
            background: #e5edff;
        }

        &.active {
            background: #e5edff;

            .cate-name,
            .cate-count,
            .cate-icon {
                color: #3974ff;
            }
        }
    }

    .node-expand-icon {
        position: absolute;
        left: 3px;
        font-size: 11px;
        color: #5e7bb4;
        cursor: pointer;
    }

}
</style>
