<template>
  <div class="params-wrapper">
    <div class="param-header">
      <span class="param-name param-title">{{ $t('循环变量') }}</span>
      <span class="param-data param-title">{{ $t('数据来源') }}</span>
    </div>
    <div class="param-content">
      <div
        v-for="(item, index) in curVarList"
        :key="index"
        class="param-row">
        <bk-form
          ref="loopVarFormRef"
          :model="item"
          :rules="formRules"
          form-type="inline"
          ext-cls="loopVarForm">
          <bk-form-item
            property="name"
            class="param-name-form-item param-item"
            :label-width="1">
            <bk-input
              v-model="item.name"
              :placeholder="$t('请输入循环变量')"
              :readonly="isViewMode"
              class="param-name-input"
              @change="onParamChange" />
          </bk-form-item>
          <bk-form-item
            property="value"
            class="param-source-form-item param-item"
            :label-width="1">
            <div class="param-source-wrapper">
              <bk-input
                v-model="item.value"
                :placeholder="$t('请输入数据来源, 如: 1,2,3 或 ${key}')"
                :readonly="isViewMode"
                class="param-source-input"
                @input="onSourceInput($event, index)"
                @change="onParamChange" />
              <VariableList
                v-if="activeVarIndex === index"
                :ref="`variableListRef_${index}`"
                class="param-source-input-list"
                :is-list-open="isListOpen"
                :var-list="filteredVarList"
                :textarea-height="32"
                @select="onSelectVar" />
            </div>
          </bk-form-item>
        </bk-form>
        <div class="param-actions">
          <bk-icon
            type="plus-circle-shape"
            :class="['action-icon', { 'is-disabled': isViewMode }]"
            :disabled="isViewMode"
            @click.prevent="addParam" />
          <bk-icon
            type="minus-circle-shape"
            :class="['action-icon', { 'is-disabled': isViewMode || curVarList.length <= 1 }]"
            :disabled="isViewMode || curVarList.length <= 1"
            @click.prevent="removeParam(index)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import tools from '@/utils/tools.js';
import { mapState } from 'vuex';
import VariableList from '@/components/common/RenderForm/VariableList.vue';
import { buildConstantArray, filterVariableList } from '@/components/common/RenderForm/formMixins.js';

const VAR_REG = /\$.*$/;

export default {
  name: 'LoopVar',
  components: {
    VariableList,
  },
  props: {
    isViewMode: {
      type: Boolean,
      default: false,
    },
    varList: {
      type: Array,
      default: () => [
        { name: '', value: '', is_quote: false },
      ],
    },
    subflowForms: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      curVarList: tools.deepClone(this.varList),
      activeVarIndex: -1,
      isListOpen: false,
      filteredVarList: [],
      formRules: {
        name: [
          {
            required: true,
            message: this.$t('循环变量不能为空'),
            trigger: 'blur',
          },
          {
            validator: this.validateVarName,
            message: this.$t('循环变量由英文字母、数字、下划线组成，且不能以数字开头'),
            trigger: 'blur',
          },
          {
            validator: this.validateVarNameUnique,
            message: this.$t('循环变量不能重复'),
            trigger: 'blur',
          },
        ],
        value: [
          {
            required: true,
            message: this.$t('数据来源不能为空'),
            trigger: 'blur',
          },
          {
            validator: this.validateVarSource,
            message: this.$t('数据来源格式不正确，仅支持 1,2,3 形式或单个变量 ${key}'),
            trigger: 'blur',
          },
        ],
      },
    };
  },
  computed: {
    ...mapState({
      constants: state => state.template.constants,
    }),
    constantArr() {
      return buildConstantArray(this.constants, {});
    },
  },
  watch: {
    varList: {
      handler(value) {
        this.curVarList = tools.deepClone(value);
      },
      deep: true,
    },
  },
  created() {
    window.addEventListener('click', this.handleListShow, false);
  },
  beforeDestroy() {
    window.removeEventListener('click', this.handleListShow, false);
  },
  methods: {
    handleListShow(e) {
      if (!this.$el.contains(e.target)) {
        this.isListOpen = false;
        this.activeVarIndex = -1;
      }
    },
    onSourceInput(val, index) {
      this.activeVarIndex = index;
      const result = filterVariableList(val, this.constantArr, VAR_REG);
      this.filteredVarList = result.varList;
      this.isListOpen = result.isListOpen;
      if (result.isListOpen) {
        this.$nextTick(() => {
          const ref = this.$refs[`variableListRef_${index}`];
          if (ref) {
            const instance = Array.isArray(ref) ? ref[0] : ref;
            instance.searchKeyword = '';
          }
        });
      }
    },
    onSelectVar(val) {
      if (this.activeVarIndex >= 0 && this.activeVarIndex < this.curVarList.length) {
        const currentValue = this.curVarList[this.activeVarIndex].value;
        this.curVarList[this.activeVarIndex].value = currentValue.replace(VAR_REG, val);
        this.onParamChange();
      }
      this.isListOpen = false;
      this.activeVarIndex = -1;
    },
    validateVarName(value) {
      const reg = /(^\${(?!_env_|_system\.)[a-zA-Z_]\w*}$)|(^(?!_env_|_system\.)[a-zA-Z_]\w*$)/;// 合法变量key正则，eg:${fsdf_f32sd},fsdf_f32sd;
      return reg.test(value);
    },
    validateVarSource(value) {
      if (!value) return true; // 空值由required校验处理
      // 允许两种格式：
      // 1. 逗号分隔的纯文本形式，如 1,2,3 或 a,b,c（不含 ${} 变量引用）
      // 2. 单独一个变量 ${name}
      const singleVarReg = /^\$\{[^}]+\}$/;
      const commaSeparatedReg = /^[^$]+(,[^$]+)*$/;
      return singleVarReg.test(value) || commaSeparatedReg.test(value);
    },
    validateVarNameUnique(value) {
      if (!value) return true; // 空值由required校验处理
      // 校验变量名是否重复，统一转换为 ${name} 格式后再比较
      const normalizedValue = /^\$\{\w+\}$/.test(value) ? value : `\${${value}}`;
      const names = this.curVarList.map(item => item.name).filter(name => name);
      const count = names.filter((name) => {
        const normalizedName = /^\$\{\w+\}$/.test(name) ? name : `\${${name}}`;
        return normalizedName === normalizedValue;
      }).length;
      return count <= 1;
    },
    onParamChange() {
      this.$emit('change', this.curVarList);
    },
    addParam() {
      if (this.isViewMode) return;
      this.curVarList.push({
        name: '',
        value: '',
        is_quote: false,
      });
      this.onParamChange();
    },
    removeParam(index) {
      if (this.isViewMode || this.curVarList.length <= 1) return;
      this.curVarList.splice(index, 1);
      this.onParamChange();
    },
    validate() {
      const promises = [];
      this.curVarList.forEach((item, index) => {
        const form = this.$refs.loopVarFormRef[index];
        if (form) {
          promises.push(form.validate());
        }
      });
      return promises.length > 0 ? Promise.all(promises) : Promise.resolve(true);
    },
    clearValidate() {
      this.curVarList.forEach((item, index) => {
        const form = this.$refs.loopVarFormRef[index];
        if (form) {
          form.clearError();
        }
      });
    },
  },
};
</script>

<style lang="scss" scoped>
  .params-wrapper {
    .param-header {
      display: flex;
      align-items: center;
      height: 32px;
      background-color: #F0F1F5;
      border-radius: 2px;
      padding: 0 16px;
      font-size: 12px;
      color: #4D4F56;
      .param-title {
        position: relative;
        &:after {
          height: 8px;
          line-height: 1;
          content: "*";
          color: #ea3636;
          font-size: 12px;
          position: absolute;
          display: inline-block;
          vertical-align: middle;
          top: 50%;
          -webkit-transform: translate(3px, -50%);
          transform: translate(3px, -50%);
        }
      }
      .param-name {
        flex: 0 0 160px;
      }
      .param-data {
        flex: 1;
        margin-left: 12px;
      }
    }
    .param-content{
      background: #F5F7FA;
      border-radius: 2px;
      padding: 12px 15px;
      .param-row {
        display: flex;
        align-items: center;
        &:not(:first-child){
          margin-top: 12px;
        }
        .param-item{
          margin-top: 0;
        }
        .loopVarForm{
          display: flex !important;
          flex: 1;
          align-items: center;
          width: 100%;
          .param-name-form-item {
            flex: 0 0 auto;
            margin-right: 12px;
          }
          .param-name-input{
            width: 150px;
          }
          ::v-deep .param-source-form-item{
            flex: 1;
            width: 100%;
            .bk-form-content{
              width: 100%;
            }
            .param-source-wrapper {
              position: relative;
              width: 100%;
            }
          }
        }
        .param-actions {
          display: flex;
          align-items: center;
          width: 64px;
          margin-top: 6px;
          .action-icon {
            font-size: 20px !important;
            color: #c4c6cc;
            cursor: pointer;
            margin-left: 12px;
            &.is-disabled {
              cursor: not-allowed !important;
            }
          }
        }
      }
    }
  }
</style>
