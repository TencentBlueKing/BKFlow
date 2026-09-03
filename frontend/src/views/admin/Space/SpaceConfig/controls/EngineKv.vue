<template>
  <div class="engine-kv">
    <div class="ek-section">
      <div class="ek-title">
        {{ $t('空间级') }}
      </div>
      <div
        v-for="row in spaceRows"
        :key="row.uid"
        class="ek-row">
        <bk-input
          v-model="row.key"
          :placeholder="$t('请输入key')"
          :clearable="true"
          class="ek-input"
          @change="emitValue" />
        <bk-input
          v-model="row.value"
          :placeholder="$t('请输入值（字符串/数字/布尔）')"
          :clearable="true"
          class="ek-input"
          @change="emitValue" />
        <bk-icon
          type="minus-circle-shape"
          class="engine-del-icon"
          @click="removeSpaceRow(row.uid)" />
      </div>
      <bk-button
        text
        theme="primary"
        @click="addSpaceRow">
        <i class="commonicon-icon common-icon-add ek-add-icon" />
        <span class="ek-add-icon-text">{{ $t('添加') }}</span>
      </bk-button>
    </div>
    <div class="ek-section">
      <div class="ek-title">
        {{ $t('按作用域覆盖') }}
      </div>
      <div
        v-for="block in scopeBlocks"
        :key="block.uid"
        class="ek-scope-block">
        <div class="ek-scope-head">
          <bk-input
            v-model="block.scope"
            :clearable="true"
            :placeholder="$t('请输入作用域,如: {scope_type}_{scope_value}')"
            class="ek-scope-input"
            @change="emitValue" />
          <bk-input
            v-model="block.value"
            :clearable="true"
            :placeholder="scopeValuePlaceholder"
            class="ek-scope-input"
            @change="emitValue" />
          <bk-icon
            type="minus-circle-shape"
            class="engine-del-icon"
            @click="removeBlock(block.uid)" />
        </div>
      </div>
      <bk-button
        text
        theme="primary"
        @click="addBlock">
        <i class="commonicon-icon common-icon-add ek-add-icon" />
        <span class="ek-add-icon-text">{{ $t('添加作用域') }}</span>
      </bk-button>
    </div>
  </div>
</template>
<script>
  export default {
    name: 'EngineKv',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [Object, String],
        default: () => ({}),
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        spaceRows: [],
        scopeBlocks: [],
        lastEmitted: undefined,
        uidSeq: 0,
      };
    },
    computed: {
      scopeValuePlaceholder() {
        return this.$t('请输入值, 如: { "key1": "value1" }');
      },
    },
    watch: {
      value: {
        handler(newValue) {
          if (this.lastEmitted !== undefined && this.isValueEqual(newValue, this.lastEmitted)) {
            return;
          }
          this.parseValue(newValue);
        },
        immediate: true,
      },
    },
    methods: {
      genUid() {
        this.uidSeq += 1;
        return `kv_${this.uidSeq}_${Date.now()}`;
      },
      isValueEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b);
      },
      toRows(source) {
        return Object.entries(source || {}).map(([key, value]) => ({ uid: this.genUid(), key, value: String(value) }));
      },
      parseValue(newValue) {
        const valueObj = (newValue && typeof newValue === 'object') ? newValue : {};
        this.spaceRows = this.toRows(valueObj.space);
        this.scopeBlocks = Object.entries(valueObj.scope || {}).map(([scopeKey, scopeValue]) => ({
          uid: this.genUid(),
          scope: scopeKey,
          // 对象序列化回 JSON 字符串填入输入框
          value: this.stringifyScopeValue(scopeValue),
        }));
        if (!this.spaceRows.length) this.addSpaceRow();
        if (!this.scopeBlocks.length) this.addBlock();
      },
      stringifyScopeValue(scopeValue) {
        if (scopeValue === undefined || scopeValue === null) return '';
        return typeof scopeValue === 'string' ? scopeValue : JSON.stringify(scopeValue);
      },
      addSpaceRow() {
        this.spaceRows.push({ uid: this.genUid(), key: '', value: '' });
        this.emitValue();
      },
      removeSpaceRow(uid) {
        const index = this.spaceRows.findIndex(row => row.uid === uid);
        if (index > -1) this.spaceRows.splice(index, 1);
        this.emitValue();
      },
      addBlock() {
        this.scopeBlocks.push({ uid: this.genUid(), scope: '', value: '' });
        this.emitValue();
      },
      removeBlock(uid) {
        const index = this.scopeBlocks.findIndex(block => block.uid === uid);
        if (index > -1) this.scopeBlocks.splice(index, 1);
        this.emitValue();
      },
      rowsToObj(rows) {
        const keyValueMap = {};
        rows.forEach((row) => {
          if (row.key) keyValueMap[row.key] = row.value;
        });
        return keyValueMap;
      },
      emitValue() {
        const result = {};
        const space = this.rowsToObj(this.spaceRows);
        if (Object.keys(space).length) result.space = space;
        const scope = {};
        this.scopeBlocks.forEach((block) => {
          if (!block.scope || !block.value) return;
          scope[block.scope] = this.parseScopeValue(block.value);
        });
        if (Object.keys(scope).length) result.scope = scope;
        this.lastEmitted = result;
        this.$emit('change', result);
      },
      // JSON 字符串转换为对象
      parseScopeValue(raw) {
        if (typeof raw !== 'string') return raw;
        const trimmed = raw.trim();
        if (!trimmed) return raw;
        try {
          return JSON.parse(trimmed);
        } catch (e) {
          return raw;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .engine-kv {
    font-size: 12px;
  }
  .ek-section {
    margin-bottom: 16px;
  }
  .ek-title {
    color: #313238;
    font-weight: 500;
    margin-bottom: 8px;
  }
  .ek-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .ek-input {
    width: 200px;
  }
  .ek-scope-block {
    margin-bottom: 8px;
  }
  .ek-scope-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .ek-scope-input {
    width: 280px;
  }
  .ek-add-icon {
    font-size: 16px;
  }
  .ek-add-icon-text {
    font-size: 12px;
  }
  .engine-del-icon {
    color: #979ba5;
    cursor: pointer;
    font-size: 16px !important;
  }
</style>
