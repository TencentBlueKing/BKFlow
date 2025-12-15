/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
<template>
  <div class="tag-textarea">
    <div class="rf-form-wrapper">
      <el-input
        ref="tagTextarea"
        v-model="textareaValue"
        type="textarea"
        :class="{ 'rf-view-textarea-value': !formMode }"
        :disabled="!editable || !formMode || disabled"
        :autosize="formMode ? { minRows: 2 } : true"
        resize="none"
        :placeholder="placeholder"
        @input="onInput" />
      <variable-list
        :is-list-open="showVarList && isListOpen"
        :var-list="varList"
        :textarea-height="textareaHeight"
        @select="onSelectVal" />
    </div>
    <span
      v-show="!validateInfo.valid"
      class="common-error-tip error-info">{{ validateInfo.message }}</span>
  </div>
</template>
<script>
  import '@/utils/i18n.js';
  import dom from '@/utils/dom.js';
  import { getFormMixins } from '../formMixins.js';
  import { mapState } from 'vuex';
  import VariableList from '../VariableList.vue';

  const VAR_REG = /\$.*$/;

  export const attrs = {
    value: {
      type: [String, Object],
      required: false,
      default: '',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
      desc: gettext('禁用组件'),
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
      desc: 'placeholder',
    },
    showVarList: {
      type: Boolean,
      default: false,
      inner: true,
    },
  };
  export default {
    name: 'TagTextarea',
    components: {
      VariableList,
    },
    mixins: [getFormMixins(attrs)],
    props: {
      constants: {
        type: Object,
        default() {
          return {};
        },
      },
    },
    data() {
      return {
        isListOpen: false,
        varList: [],
        textareaHeight: 40, // 文本框高度
      };
    },
    computed: {
      ...mapState({
        internalVariable: state => state.template.internalVariable,
      }),
      constantArr: {
        get() {
          let Keylist = [];
          if (this.constants) {
            Keylist = [...Object.values(this.constants)];
          }
          if (this.internalVariable) {
            Keylist = [...Keylist, ...Object.values(this.internalVariable)];
          }
          return Keylist;
        },
        set(val) {
          this.varList = val;
        },
      },
      textareaValue: {
        get() {
          if (!this.formMode && ['', undefined].includes(this.value)) {
            return '--';
          }
          return typeof this.value === 'string' ? this.value : JSON.stringify(this.value);
        },
        set(val) {
          this.updateForm(val);
        },
      },
      // 动态计算下拉列表的位置，基于文本框的实际高度
      selectListTop() {
        return this.textareaHeight + 2;
      },
    },
    watch: {
      formMode() {
        /**
         * 重新计算 textarea 高度，解决 disabled 下有滚动条和空白问题
         * resizeTextarea 为非官方暴露 api，后续需关注 element textarea 组件该问题修复后删除
         */
        this.$nextTick(() => {
          this.$refs.tagTextarea.resizeTextarea();
          this.updateTextareaHeight();
        });
      },
      textareaValue() {
        // 当文本内容变化时，更新高度
        this.updateTextareaHeight();
      },
    },
    mounted() {
      this.updateTextareaHeight();
    },
    created() {
      window.addEventListener('click', this.handleListShow, false);
    },
    mounted() {
      this.updateTextareaHeight();
    },
    beforeDestroy() {
      window.removeEventListener('click', this.handleListShow, false);
    },
    methods: {
      // 获取文本框的实际高度
      updateTextareaHeight() {
        this.$nextTick(() => {
          if (this.$refs.tagTextarea && this.$refs.tagTextarea.$el) {
            const textareaEl = this.$refs.tagTextarea.$el.querySelector('.el-textarea__inner');
            if (textareaEl) {
              this.textareaHeight = textareaEl.offsetHeight;
            }
          }
        });
      },
      handleListShow(e) {
        if (!this.isListOpen) {
          return;
        }
        const listPanel = document.querySelector('.rf-select-list');
        if (listPanel && !dom.nodeContains(listPanel, e.target)) {
          this.isListOpen = false;
        }
      },
      onInput(val) {
        // 先更新文本框高度
        this.$nextTick(() => {
          this.updateTextareaHeight();
        });
        const matchResult = val.match(VAR_REG);
        if (matchResult && matchResult[0]) {
          const regStr = matchResult[0].replace(/\\/g, '\\\\').replace(/[\$\{\}]/g, '\\$&');
          const inputReg = new RegExp(regStr);
          this.varList = this.constantArr.filter(item => inputReg.test(item.key));
        } else {
          this.varList = [];
        }
        this.isListOpen = !!this.varList.length;
      },
      onSelectVal(val) {
        const replacedValue = this.value.replace(VAR_REG, val);
        this.updateForm(replacedValue);
        this.isListOpen = false;
      },
      // 获取文本框的实际高度
      updateTextareaHeight() {
        this.$nextTick(() => {
          if (this.$refs.tagTextarea && this.$refs.tagTextarea.$el) {
            const textareaEl = this.$refs.tagTextarea.$el.querySelector('.el-textarea__inner');
            if (textareaEl) {
              this.textareaHeight = textareaEl.offsetHeight;
            }
          }
        });
      },
    },
  };
</script>
<style lang="scss">
@import '../../../../scss/mixins/scrollbar.scss';
.tag-textarea {
    .el-textarea__inner {
        padding-left: 10px;
        padding-right: 10px;
        font-size: 12px;
        word-break: break-all;
        @include scrollbar;
    }
    .rf-form-wrapper {
        position: relative;
    }
}
.rf-view-textarea-value {
    .el-textarea__inner {
        padding: 6px 0;
        line-height: 24px;
        color: #333333;
        border: none;
        resize: none;
        &[disabled = "disabled"] {
            background: inherit;
            color: inherit;
            cursor: text;
        }
    }
}
</style>
