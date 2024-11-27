<template>
  <div class="field-slider">
    <bk-form
      ref="fieldForm"
      :model="formData"
      form-type="vertical">
      <bk-form-item
        :label="$t('字段类型')"
        :property="'type'"
        :required="true"
        :rules="rules.required"
        :error-display-type="'normal'">
        <bk-select
          v-model="formData.type"
          :disabled="isDisabled"
          :clearable="false">
          <bk-option
            id="string"
            :name="$t('文本')" />
          <bk-option
            id="int"
            :name="$t('数值')" />
          <bk-option
            id="select"
            :name="$t('单选下拉')" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        :label="$t('字段名称')"
        :property="'name'"
        :required="true"
        :rules="rules.required"
        :error-display-type="'normal'">
        <bk-input
          v-model="formData.name"
          :disabled="readonly"
          :maxlength="16"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('字段标识')"
        :property="'id'"
        :required="true"
        :rules="rules.id"
        :error-display-type="'normal'">
        <bk-input
          v-model="formData.id"
          :disabled="isDisabled"
          :maxlength="16"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item
        :label="$t('提示文字')"
        :property="'tips'">
        <bk-input
          v-model="formData.tips"
          :disabled="readonly"
          :maxlength="32"
          :show-word-limit="true" />
      </bk-form-item>
      <bk-form-item :label="$t('描述信息')">
        <bk-input
          v-model="formData.desc"
          type="textarea"
          :maxlength="300"
          :disabled="readonly"
          :show-word-limit="true" />
      </bk-form-item>
      <!--下拉框类型选项-->
      <bk-form-item
        v-if="formData.type === 'select'"
        :label="$t('选项')"
        :property="'options'"
        :required="true"
        :rules="rules.options"
        :error-display-type="'normal'">
        <SelectField
          :options="formData.options"
          :readonly="readonly"
          :operate="operate"
          @updateOptions="updateOptions" />
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
  import { makeId } from '@/utils/uuid.js';
  import SelectField from './components/SelectField.vue';
  import tools from '@/utils/tools.js';

  export default {
    name: 'FieldSlider',
    components: {
      SelectField,
    },
    props: {
      operate: {
        type: String,
        default: '',
      },
      fieldInfo: {
        type: Object,
        default: () => ({}),
      },
      readonly: {
        type: Boolean,
        default: true,
      },
      inputs: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      const formData = this.fieldInfo.id ? { ...this.fieldInfo } : {
        type: 'string',
        id: `field${makeId(8)}`,
        name: '',
        tips: '',
        desc: '',
      };
      // 所有类型默认添加options，保存时除了select 类型需要过滤掉
      formData.options = formData.options || {
        type: 'custom',
        value: '',
        items: [],
      };
      return {
        formData,
        initFormData: tools.deepClone(formData),
        rules: {
          required: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
          id: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
            {
              validator: this.checkKeyExists,
              message: this.$t('字段标识已经存在'),
              trigger: 'blur',
            },
            {
              validator(val) {
                const regexp = /^[a-zA-Z][a-zA-Z0-9]*$/;
                return regexp.test(val);
              },
              message: this.$t('key值只能由数字和字母组成且不能以数字开头'),
              trigger: 'blur',
            },
          ],
          options: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
            {
              validator(val) {
                return !!val.items.length;
              },
              message: this.$t('必填项不能为空'),
              trigger: 'blur',
            },
            {
              validator: this.checkOption,
              message: this.$t('id或name不唯一'),
              trigger: 'blur',
            },
          ],
        },
      };
    },
    computed: {
      isDisabled() {
        return this.readonly || this.operate === 'edit';
      },
    },
    methods: {
      // 校验key是否存在
      checkKeyExists(val) {
        const keys = this.inputs.reduce((acc, cur) => {
          if (cur.id !== this.fieldInfo.id) {
            acc.push(cur.id);
          }
          return acc;
        }, []);
        return !keys.includes(val);
      },
      // 校验option是否存在相同id和name
      checkOption(val) {
        if (!val) return false;
        const names = new Set();
        const ids = new Set();
        return val.items.every((item) => {
          if (names.has(item.name) || ids.has(item.id)) {
            return false;
          }
          names.add(item.name);
          ids.add(item.id);
          return true;
        });
      },
      updateOptions(options) {
        this.formData.options = options;
        // 单独校验
        if (options.items.length) {
          this.$refs.fieldForm.validateField('options');
        }
      },
      validate() {
        return this.$refs.fieldForm.validate().then((valid) => {
          if (valid && this.formData.type === 'select') {
            return this.formData.options.items.every(item => item.id && item.name && !/\"/g.test(item.id));
          }
          return valid;
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
.field-slider {
  padding: 24px;
}
</style>
