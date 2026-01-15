<template>
  <transition>
    <div
      v-show="isListOpen"
      class="rf-select-list"
      :style="{ top: selectListTop + 'px' }">
      <div class="bk-select-search-wrapper">
        <i class="left-icon bk-icon icon-search" />
        <input
          v-model="searchKeyword"
          type="text"
          :placeholder="$t('搜索分类名称')"
          class="bk-select-search-input"
          @input="onSearch">
      </div>
      <!-- </div> -->
      <div class="group-content">
        <div
          v-for="group in filteredGroupList"
          :key="group.name"
          class="group-item">
          <div
            class="group-header"
            @click="toggleGroup(group)">
            <i
              :class="[
                'group-header-icon', 'bk-icon',
                group.isCollapse ? 'icon-right-shape' : 'icon-down-shape'
              ]" />
            <span class="group-name">{{ $t(group.name) }}</span>
          </div>
          <div
            v-show="!group.isCollapse"
            class="group-children">
            <div
              v-for="item in group.children"
              :key="item.key"
              class="variable-item"
              :class="getVariableClass(group.type)"
              @mousedown="onSelectVal(item.key)">
              <div class="var-prefix">
                {{ getVariablePrefix(group.type) }}
              </div>
              <span class="var-key">{{ item.key }}</span>
              <span
                v-if="item.name && item.name !== item.key"
                class="var-name">{{ item.name }}</span>
            </div>
          </div>
        </div>
        <div
          v-if="filteredGroupList.length === 0"
          class="no-data">
          {{ $t('暂无匹配的变量') }}
        </div>
      </div>
    </div>
  </transition>
</template>

<script>
export default {
  name: 'VariableList',
  props: {
    // 是否显示列表
    isListOpen: {
      type: Boolean,
      default: false,
    },
    // 变量列表
    varList: {
      type: Array,
      default: () => [],
    },
    textareaHeight: {
      type: Number,
      default: 40,
    },
  },
  data() {
    return {
      searchKeyword: '',
    };
  },
  computed: {
    // 动态计算下拉列表的位置，基于文本框的实际高度
    selectListTop() {
      return this.textareaHeight + 2;
    },
    // 根据搜索分类关键词过滤分组
    filteredGroupList() {
      if (!this.searchKeyword.trim()) {
        return this.varList;
      }
      const keyword = this.searchKeyword.toLowerCase();
      const filterList = this.varList.filter(group => group.name.toLowerCase().includes(keyword));
          // if (group.name.toLowerCase().includes(keyword)) {
          // }
          // const filteredChildren = (group.children || []).filter(item => item.key.toLowerCase().includes(keyword)
          //   || (item.name && item.name.toLowerCase().includes(keyword)));
          // return {
          //   ...group,
          //   children: filteredChildren,
          // };
        // );
        // .filter(group => group.children.length > 0);
      return filterList;
    },
  },
  methods: {
    onSelectVal(val) {
      this.$emit('select', val);
    },
    onSearch() {
      // 搜索时自动展开所有分组
      this.filteredGroupList.forEach((group) => {
        group.isCollapse = false;
      });
    },
    toggleGroup(group) {
      group.isCollapse = !group.isCollapse;
    },
    // 根据变量类型获取前缀标识
    getVariablePrefix(type) {
      const prefixMap = {
        system: 'Sys',
        input: 'In',
        output: 'Out',
        loop: 'Loop',
        custom: 'Cus',
      };
      return prefixMap[type] || '';
    },
    // 根据变量类型获取样式类名
    getVariableClass(type) {
      return `var-type-${type}`;
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../../scss/mixins/scrollbar.scss';

.rf-select-list {
  position: absolute;
  right: 0;
  width: 100%;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0 0 8px 1px rgba(0, 0, 0, 0.1);
  overflow-y: hidden;
  z-index: 100;

  .search-wrapper {
    padding: 8px;
    border-bottom: 1px solid #f0f1f5;
  }

  .group-content {
    max-height: 300px;
    overflow-y: auto;
    @include scrollbar;
  }

  .group-item {
    .group-header {
      display: flex;
      align-items: center;
      padding: 12px;
      cursor: pointer;
      font-size: 12px;
      color: #63656e;
      &:hover {
        background: #f5f7fa;
      }
      .group-header-icon {
        color: #979ba5;
        margin-right: 4px;
        font-size: 12px;
        transition: transform 0.2s;
      }
    }

    .group-children {
      .variable-item {
          display: flex;
          align-items: center;
          padding: 0 10px;
          line-height: 32px;
          font-size: 12px;
          cursor: pointer;
          > span {
              flex-shrink: 0;
              overflow: hidden;
              white-space: nowrap;
              text-overflow: ellipsis;
          }
          .name {
              max-width: 250px;
          }
          &.is-hover,
          &:hover {
              background: #f5f7fa;
          }
          // 不同类型变量的样式
          &.var-type-system .var-prefix {
            background: #eaecf2;
            color: #9ca0a8;
          }
          &.var-type-input .var-prefix {
            background: #dde8ed;
            color: #7ba5be;
          }
          &.var-type-output .var-prefix {
            background: #e0ede9;
            color: #7bb09b;
          }
          &.var-type-loop .var-prefix {
            background: #f6ecdc;
            color: #d6a95b;
          }
          &.var-type-custom .var-prefix {
            background: #ffe9e9;
            color: #c38686;
          }
          .var-name {
            max-width: 250px;
            color: #c4c6cc;
            margin-left: 16px;
          }
          .var-prefix {
            padding: 0 3px;
            height: 20px;
            display: flex;
            align-items: center;
            border-radius: 2px;
            margin-right: 5px;
          }
      }
    }
  }

  .no-data {
    padding: 20px;
    text-align: center;
    color: #c4c6cc;
    font-size: 12px;
  }
}
</style>
