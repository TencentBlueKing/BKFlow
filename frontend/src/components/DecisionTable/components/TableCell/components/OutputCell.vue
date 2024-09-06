<template>
  <div class="output-cell">
    <ValueSelector
      v-model="cell.condition.value"
      :column="cell.column"
      :placeholder="cell.column.tips" />
  </div>
</template>
<script>
  import ValueSelector from '../../../common/ValueSelector.vue';
  export default {
    name: 'OutputCell',
    components: {
      ValueSelector,
    },
    props: {
      cell: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>
<style lang="scss" scoped>
  .output-cell {
    width: 100%;
    height: 100%;
    /deep/.bk-select,
    /deep/.bk-form-input {
      padding-right: 10px;
      height: 43px;
      width: 100%;
      z-index: 5;
      line-height: 40px;
      border: 1px solid #1272FF;
      box-shadow: 0 0 4px 1px #1272ff33;
    }
    /deep/.bk-select {
      background: #fff;
      .bk-select-name {
        height: 42px;
      }
      .bk-select-angle {
        top: 9px;
        right: 5px;
      }
    }
  }
</style>
