<template>
  <div
    class="space-config-item"
    :class="{ 'is-default': isCurrentValueDefault }">
    <div class="config-item-row">
      <div class="config-item-label">
        <span
          v-bk-overflow-tips
          class="label-text">
          {{ configItem.desc }}
        </span>
        <span
          v-if="isCurrentValueDefault"
          class="default-tag">
          {{ $t('默认值') }}
        </span>
      </div>
      <div class="config-item-control">
        <!-- 混合类型：值类型选择器 + 对应控件 -->
        <template v-if="configItem.is_mix_type">
          <div class="mix-type-row">
            <span class="mix-type-label">{{ $t('值类型') }}</span>
            <bk-select
              v-model="localValueType"
              ext-cls="mix-type-select"
              :clearable="false"
              @selected="handleValueTypeChange">
              <bk-option
                id="TEXT"
                name="TEXT" />
              <bk-option
                id="JSON"
                name="JSON" />
            </bk-select>
          </div>
        </template>
        <!-- JSON 类型 -->
        <div
          v-if="isJsonType"
          class="code-editor-wrapper">
          <FullCodeEditor
            ref="fullCodeEditor"
            v-model="formValue"
            style="height: 300px;"
            :options="{ language: 'json', placeholder: configItem.example }" />
        </div>
        <!-- select 类型 -->
        <bk-select
          v-else-if="isSelectType"
          v-model="formValue"
          :clearable="false"
          :placeholder="placeholderText">
          <bk-option
            v-for="option in configItem.choices"
            :id="option"
            :key="option"
            :name="option" />
        </bk-select>
        <!-- 文本输入 -->
        <bk-input
          v-else
          v-model="formValue"
          :placeholder="placeholderText" />
      </div>
    </div>
  </div>
</template>
<script>
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import tools from '@/utils/tools.js';

  export default {
    name: 'SpaceConfigItem',
    components: {
      FullCodeEditor,
    },
    props: {
      configItem: {
        type: Object,
        required: true,
      },
      spaceId: {
        type: [String, Number],
        required: true,
      },
    },
    data() {
      return {
        formValue: '',
        localValueType: 'TEXT',
        initialValue: '',
        defaultFormValue: '', // 用于存储默认值的格式化版本
        hasDefaultValue: false, // 标记配置项是否有默认值
      };
    },
    computed: {
      isJsonType() {
        if (this.configItem.is_mix_type) {
          return this.localValueType === 'JSON';
        }
        return this.configItem.value_type === 'JSON'
          || (this.configItem.value_type === undefined && !this.configItem.choices);
      },
      isSelectType() {
        return !!this.configItem.choices && !this.isJsonType;
      },
      placeholderText() {
        const { example = '' } = this.configItem;
        if (this.configItem.is_mix_type) {
          return this.$t('请输入');
        }
        return typeof example === 'string' ? example : JSON.stringify(example);
      },
      isValueChanged() {
        return this.formValue !== this.initialValue;
      },
      // 动态判断当前值是否为默认值
      isCurrentValueDefault() {
        // 如果配置项没有默认值，则不显示默认值标签
        if (!this.hasDefaultValue) {
          return false;
        }
        // 比较当前值与默认值（两者都是字符串类型）
        return String(this.formValue) === String(this.defaultFormValue);
      },
    },
    watch: {
      configItem: {
        handler(val) {
          this.initFormValue(val);
        },
        immediate: true,
        deep: true,
      },
      formValue() {
        this.$emit('change', this.isValueChanged);
      },
    },
    methods: {
      initFormValue(item) {
        const {
          value_type: valueType,
          choices,
          value,
          json_value: jsonValue = {},
          isDefault,
          default_value: defaultValue,
        } = item;
        this.localValueType = valueType || 'TEXT';
        let formType = valueType === 'JSON' ? 'json' : 'input';
        formType = choices ? 'select' : formType;
        this.hasDefaultValue = defaultValue !== null && defaultValue !== undefined;
        // 格式化默认值用于比较（确保始终为字符串类型）
        let formattedDefaultValue = '';
        if (this.hasDefaultValue) {
          formattedDefaultValue = formType === 'json' && defaultValue
            ? JSON.stringify(defaultValue, null, 4)
            : String(defaultValue);
        }
        this.defaultFormValue = formattedDefaultValue;
        let formValue;
        if (isDefault) {
          formValue = formattedDefaultValue;
        } else {
          formValue = formType === 'json' && jsonValue ? JSON.stringify(jsonValue, null, 4) : value;
        }
        formValue = formValue || '';
        this.formValue = formValue;
        this.initialValue = formValue;
      },
      handleValueTypeChange() {
        this.formValue = '';
      },
      /**
       * 校验表单值
       * @returns {{ valid: boolean, desc: string }}
       */
      validate() {
        if (this.isJsonType) {
          const val = this.formValue;
          if (val !== undefined && val !== null && val !== '' && !tools.checkIsJSON(val)) {
            return { valid: false, desc: this.configItem.desc || this.configItem.name };
          }
        }
        return { valid: true, desc: this.configItem.desc || this.configItem.name };
      },
      /**
       * 获取变更数据，未变更返回 null
       * @returns {Object|null}
       */
      getChangedData() {
        if (!this.isValueChanged) return null;
        const { id, name, value_type: valueType, is_mix_type: isMixType } = this.configItem;
        const data = {
          id,
          name,
          space_id: this.spaceId,
          value_type: isMixType ? this.localValueType : valueType,
        };
        if (this.isJsonType) {
          const val = this.formValue;
          data.json_value = (val !== undefined && val !== null && val !== '') ? JSON.parse(val) : null;
        } else {
          data.text_value = this.formValue;
        }
        return data;
      },
      getCurrentData() {
        const { id, name, value_type: valueType, is_mix_type: isMixType } = this.configItem;
        const data = {
          id,
          name,
          space_id: this.spaceId,
          value_type: isMixType ? this.localValueType : valueType,
        };
        if (this.isJsonType) {
          const val = this.formValue;
          data.json_value = (val !== undefined && val !== null && val !== '') ? JSON.parse(val) : null;
        } else {
          data.text_value = this.formValue;
        }
        return data;
      },
    },
  };
</script>
<style lang="scss" scoped>
  .space-config-item {
    padding: 24px 32px;
    border-bottom: 1px solid #f0f1f5;
    transition: background-color 0.2s;
    &:last-child {
      border-bottom: none;
    }
    &:hover {
      background-color: #fafbfd;
    }
    &.is-default {
      .config-item-label .label-text {
        color: #979ba5;
      }
    }
    .config-item-row {
      display: flex;
      align-items: flex-start;
    }
    .config-item-label {
      display: flex;
      align-items: center;
      flex-shrink: 0;
      width: 220px;
      padding-top: 6px;
      padding-right: 24px;
      text-align: right;
      .label-text {
        flex: 1;
        min-width: 0;
        font-size: 12px;
        color: #313238;
        line-height: 22px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .default-tag {
        margin-left: 6px;
        padding: 0 6px;
        font-size: 12px;
        line-height: 18px;
        color: #979ba5;
        background: #f0f1f5;
        border-radius: 2px;
        white-space: nowrap;
      }
      .label-icon {
        margin-left: 4px;
        font-size: 12px;
        color: #c4c6cc;
        cursor: pointer;
        flex-shrink: 0;
        &:hover {
          color: #979ba5;
        }
      }
    }
    .config-item-control {
      flex: 1;
      min-width: 0;
      .mix-type-row {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
      }
      .mix-type-label {
        font-size: 12px;
        color: #63656e;
        margin-right: 8px;
        white-space: nowrap;
      }
      .mix-type-select {
        width: 120px;
        flex-shrink: 0;
      }
      .code-editor-wrapper {
        position: relative;
        height: 300px;
        border: 1px solid #dcdee5;
        border-radius: 2px;
        overflow: hidden;
      }
    }
  }
</style>
