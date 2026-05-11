<template>
  <span class="loop-count-selector">
    <span class="dot-separator">&middot;</span>
    <span class="loop-count-text">{{ $t('第') }}</span>
    <bk-popover :content="tooltip">
      <bk-select
        :clearable="false"
        :value="value"
        @selected="handleSelected">
        <bk-option
          v-for="item in options"
          :id="item"
          :key="item"
          :name="item" />
      </bk-select>
    </bk-popover>
    <span class="loop-count-text">{{ suffixText }}</span>
  </span>
</template>

<script>
  export default {
    name: 'LoopCountSelector',
    props: {
      tooltip: {
        type: String,
        required: true,
      },
      options: {
        type: [Array, Number],
        required: true,
      },
      value: {
        type: [Number, String],
        required: true,
      },
      suffixText: {
        type: String,
        default() {
          return this.$t('次循环');
        },
      },
    },
    methods: {
      handleSelected(value, option) {
        this.$emit('selected', value, option);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .loop-count-selector {
    display: contents;
    .dot-separator {
      margin: 0 4px;
      font-size: 12px;
      line-height: 1;
      color: #63656E;
    }
    .loop-count-text {
      font-weight: normal;
      font-size: 13px;
      color: #63656E;
    }
  }
</style>
