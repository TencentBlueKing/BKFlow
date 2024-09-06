<template>
  <!-- 节点历史执行时间/透视面板 -->
  <div
    class="node-tips-content"
    :style="nodeTipsPanelPosition">
    <!-- 节点输入输出变量(node.name用来判断节点是否选择过插件) -->
    <div
      v-if="isPerspectivePanelShow"
      class="perspective-tips-context">
      <div class="tips-content">
        <p class="tip-label">
          {{ $t('变量引用') }}
        </p>
        <template v-if="nodeVariable.variableList.length">
          <p
            v-for="item in nodeVariable.variableList"
            :key="item">
            {{ item }}
          </p>
        </template>
        <template v-else>
          {{ '--' }}
        </template>
      </div>
    </div>
  </div>
</template>

<script>
  export default {
    name: 'NodeTipsPanel',
    props: {
      isPerspectivePanelShow: {
        type: Boolean,
        default: false,
      },
      nodeVariable: {
        type: Object,
        default: () => ({
          variableList: [],
        }),
      },
      nodeTipsPanelPosition: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {

      };
    },
  };
</script>

<style lang="scss" scoped>
@import '../../../scss/mixins/scrollbar.scss';
.node-tips-content {
  position: absolute;
  z-index: 5;
  min-width: 200px;
  .perspective-tips-context {
    width: 100%;
    .tips-content {
      max-height: 160px;
      padding: 12px 16px;
      font-size: 12px;
      color: #63656e;
      line-height: 16px;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      box-shadow: 0px 0px 5px 0px rgba(0, 0, 0, 0.09);
      overflow-y: auto;
      @include scrollbar;
      p {
          margin-bottom: 4px;
      }
    }
    .tip-label {
      line-height: 19px;
      font-size: 14px;
      color: #63656e;
      font-weight: 700;
      margin-bottom: 8px !important;
    }
    .dividLine {
      height: 1px;
      background: #dcdee5;
      margin: 10px 0;
    }
  }
  &:hover {
      display: block;
  }
}
</style>
