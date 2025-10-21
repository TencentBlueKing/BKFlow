<template>
  <div>
    <bk-table
      size="small"
      class="credential-dialog-table"
      border
      dark-header
      :data="credentialList">
      <bk-table-column
        v-for="item of tableFields"
        :key="item.prop"
        :label="item.label"
        :prop="item.prop">
        <template slot-scope="{ row }">
          <bk-input
            v-model.trim="row[item?.prop]"
            :type="item.inputType"
            :disabled="disabled"
            :allow-emoji="false"
            :clearable="true"
            :show-clear-only-hover="true" />
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        width="120">
        <template slot-scope="{ $index }">
          <bk-icon
            size="medium"
            type="plus-circle-shape"
            class="plus-shape-icon"
            @click="handleAdd" />
          <bk-icon
            v-bk-tooltips="{
              content: $t('至少保留一个'),
              disabled: credentialList.length > 1,
            }"
            size="medium"
            type="minus-circle-shape"
            :class="[
              'minus-shape-icon',
              { 'is-disabled': credentialList.length === 1 },
            ]"
            @click="handleDelete($index)" />
        </template>
      </bk-table-column>
    </bk-table>
    <p
      v-if="!disabled"
      class="error-tip">
      {{ tipContent }}
    </p>
  </div>
</template>

<script>
export default {
  props: {
    tableFields: {
      type: Array,
      default: () => [],
    },
    selectList: {
      type: Array,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    isUniqueKey: {
      type: Boolean,
      default: true,
    },
    emptyTip: {
      type: String,
      default: '',
    },
    errorTip: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      tipContent: '',
      formData: {
        isOpenSpace: false,
      },
      credentialList: [],
    };
  },
  watch: {
    selectList: {
      handler(list) {
          this.credentialList = list.length > 0 ? list : this.setCredentialField(this.tableFields);
      },
      immediate: true,
    },
  },
  methods: {
    // 转换函数：将字段配置转为初始数据对象
    setCredentialField(list) {
      const fields = list.reduce((curr, field) => {
        curr[field.prop] = '';
        return curr;
      }, {});
      return [fields];
    },
    handleAdd() {
      const tableField = this.setCredentialField(this.tableFields);
      this.credentialList = [...this.credentialList, ...tableField];
    },
    handleDelete(index) {
      if (this.credentialList.length === 1) {
        return;
      }
      this.credentialList.splice(index, 1);
    },
    getDuplicateKeys(arr) {
      const keyMap = new Map();
      const duplicates = new Set();
      for (const item of arr) {
        const { key } = item;
        const count = (keyMap.get(key) || 0) + 1;
        keyMap.set(key, count);
        if (count > 1) {
          duplicates.add(key);
        }
      }
      return Array.from(duplicates);
    },
    validate() {
      this.tipContent = '';
      if (this.disabled) {
        return true;
      }
      const tableField = this.tableFields.map(item => item.prop);
      // 校验是否存在空项
      const emptyIndex = this.credentialList.findIndex(item => tableField.some(field => !item[field]));
      if (emptyIndex > -1) {
        this.tipContent = this.$t(this.emptyTip, {
          value: emptyIndex + 1,
        });
        return false;
      }
      // 校验value值格式是否正确
      const reg = /^[a-zA-Z0-9_-]+$/;
      const errorIndex = this.credentialList.findIndex(item => tableField.some(field => !reg.test(item[field])));
      if (errorIndex > -1) {
        this.tipContent = this.$t(this.errorTip, {
          value: errorIndex + 1,
        });
        return false;
      }
      // 校验key是否是唯一的
      const textContent = this.getDuplicateKeys(this.credentialList);
      if (textContent.length && this.isUniqueKey) {
        this.tipContent = this.$t('凭证内容或者作用域存在重复的key', { value: textContent.join() });
        return false;
      }
      return true;
    },
    clearValidate() {
      this.tipContent = '';
    },
  },
};
</script>
