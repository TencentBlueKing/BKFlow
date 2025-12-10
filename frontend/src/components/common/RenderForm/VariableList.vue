<template>
  <transition>
    <div
      v-show="isListOpen"
      class="rf-select-list"
      :style="{ top: selectListTop + 'px' }">
      <ul class="rf-select-content">
        <li
          v-for="(varItem, varIndex) in varList"
          :key="varIndex"
          class="rf-select-item"
          @mousedown="onSelectVal(varItem.key)">
          <span class="var-key">{{ varItem.key }}</span>
          <span class="var-name">{{ varItem.name }}</span>
        </li>
      </ul>
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
  computed: {
    // 动态计算下拉列表的位置，基于文本框的实际高度
    selectListTop() {
      return this.textareaHeight + 2;
    },
  },
  methods: {
    onSelectVal(val) {
      this.$emit('select', val);
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

  .rf-select-content {
    max-height: 100px;
    overflow: auto;
    @include scrollbar;
  }

  .rf-select-item {
    padding: 0 10px;
    line-height: 32px;
    font-size: 12px;
    cursor: pointer;
    &:hover {
        background: #eef6fe;
        color: #3a84ff;
    }
    > span {
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .var-name {
        max-width: 250px;
        color: #c4c6cc;
        margin-left: 16px;
    }
  }
}
</style>