<template>
  <li class="key-value-item">
    <bk-form
      ref=""
      class="key-form"
      :model="data"
      :rules="rules">
      <bk-form-item
        :required="true"
        property="key">
        <bk-input
          v-model="data.key"
          :readonly="readonly"
          :placeholder="$t('键')" />
      </bk-form-item>
    </bk-form>
    <span class="operator">:</span>
    <bk-form
      class="value-form"
      :model="data"
      :rules="rules">
      <bk-form-item
        :required="true"
        property="value">
        <bk-input
          v-model="data.value"
          :placeholder="$t('值')" />
      </bk-form-item>
    </bk-form>
    <bk-button
      v-if="operator"
      icon="icon-plus-line"
      class="mr5 ml5"
      @click="updateList()" />
    <bk-button
      v-if="operator"
      icon="icon-minus-line"
      @click="updateList(index)" />
  </li>
</template>

<script>
  export default {
    props: {
      data: {
        type: Object,
        default: () => ({
          key: '',
          value: '',
        }),
      },
      rules: {
        type: Object,
        default: () => ({}),
      },
      index: {
        type: Number,
        default: 0,
      },
      type: {
        type: String,
        default: '',
      },
      operator: {
        type: Boolean,
        default: true,
      },
      readonly: {
        type: Boolean,
        default: false,
      },
    },
    methods: {
      updateList(index) {
        this.$emit('updateList', this.type, index);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .key-value-item {
    display: flex;
    align-items: center;
    ::v-deep .key-form {
      width: 190px;
    }
    ::v-deep .value-form {
      flex: 1;
    }
    ::v-deep .bk-form-content {
      margin-left: 0 !important;
    }
    .operator {
      display: inline-block;
      width: 20px;
      font-size: 14px;
      font-weight: 700;
      text-align: center;
      color: #313238;
      vertical-align: middle;
    }
    &:not(:last-child) {
      margin-bottom: 5px;
    }
    .bk-button {
      padding: 0;
      min-width: 32px;
    }
  }
</style>
