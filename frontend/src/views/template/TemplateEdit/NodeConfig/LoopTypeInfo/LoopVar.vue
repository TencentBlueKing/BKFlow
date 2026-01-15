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
            property="source"
            class="param-source-form-item param-item"
            :label-width="1">
            <bk-input
              v-model="item.source"
              :placeholder="$t('请输入数据来源')"
              :readonly="isViewMode"
              class="param-source-input"
              @change="onParamChange" />
          </bk-form-item>
        </bk-form>
        <div class="param-actions">
          <bk-icon
            type="plus-circle-shape"
            class="action-icon"
            :disabled="isViewMode"
            @click="addParam" />
          <bk-icon
            type="minus-circle-shape"
            class="action-icon"
            :disabled="isViewMode || curVarList.length <= 1"
            @click="removeParam(index)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import tools from '@/utils/tools.js';

export default {
  name: 'LoopVar',
  props: {
    isViewMode: {
      type: Boolean,
      default: false,
    },
    varList: {
      type: Array,
      default: () => [
        { name: '', source: '' },
      ],
    },
  },
  data() {
    return {
      curVarList: tools.deepClone(this.varList),
      formRules: {
        name: [
          {
            required: true,
            message: this.$t('变量名不能为空'),
            trigger: 'blur',
          },
          {
            validator: this.validateVarName,
            message: this.$t('循环变量名称格式不正确'),
            trigger: 'blur',
          },
          {
            validator: this.validateVarNameUnique,
            message: this.$t('变量名不能重复'),
            trigger: 'blur',
          },
        ],
        source: [
          {
            required: true,
            message: this.$t('数据来源不能为空'),
            trigger: 'blur',
          },
        ],
      },
    };
  },
  watch: {
    varList: {
      handler(value) {
        this.curVarList = tools.deepClone(value);
      },
      deep: true,
    },
  },
  methods: {
    validateVarName(value) {
      const reg = /(^\${(?!_env_|_system\.)[a-zA-Z_]\w*}$)|(^(?!_env_|_system\.)[a-zA-Z_]\w*$)/;// 合法变量key正则，eg:${fsdf_f32sd},fsdf_f32sd;
      return reg.test(value);
    },
    validateVarNameUnique(value) {
      // 校验变量名是否重复
      if (!value) return true; // 空值由required校验处理
      const names = this.curVarList.map(item => item.name).filter(name => name);
      const count = names.filter(name => name === value).length;
      return count <= 1;
    },
    onParamChange() {
      this.$emit('change', this.curVarList);
    },
    addParam() {
      if (this.isViewMode) return;
      this.curVarList.push({
        name: '',
        source: '',
      });
      this.$emit('change', this.curVarList);
    },
    removeParam(index) {
      if (this.isViewMode || this.curVarList.length <= 1) return;
      this.curVarList.splice(index, 1);
      this.$emit('change', this.curVarList);
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
          }
        }
      }
    }
  }
</style>
