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
  <div class="tag-input">
    <div class="rf-form-wrapper">
      <template v-if="formMode">
        <el-input
          v-model="inputValue"
          type="text"
          :disabled="!editable || disabled"
          :show-password="showPassword"
          :placeholder="placeholder"
          @input="onInput" />
        <transition>
          <div
            v-show="showVarList && isListOpen"
            class="rf-select-list">
            <ul class="rf-select-content">
              <li
                v-for="item in varList"
                :key="item.key"
                class="rf-select-item"
                @click.stop="onSelectVal(item.key)">
                <span class="var-key">{{ item.key }}</span>
                <span class="var-name">{{ item.name }}</span>
              </li>
            </ul>
          </div>
        </transition>
      </template>
      <span
        v-else
        class="rf-view-value">{{ viewValue }}</span>
    </div>
    <span
      v-show="!validateInfo.valid"
      class="common-error-tip error-info">{{ validateInfo.message }}</span>
  </div>
</template>
<script>
  import '@/utils/i18n.js';
  import { mapState } from 'vuex';
  import dom from '@/utils/dom.js';
  import { getFormMixins } from '../formMixins.js';

  const VAR_REG = /\$.*$/;

  export const attrs = {
    placeholder: {
      type: String,
      required: false,
      default: '',
      desc: 'placeholder',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
      desc: gettext('禁用表单输入'),
    },
    showPassword: {
      type: Boolean,
      required: false,
      default: false,
      desc: gettext('是否以密码模式显示'),
    },
    value: {
      type: [String, Number],
      required: false,
      default: '',
    },
    showVarList: {
      type: Boolean,
      default: false,
      inner: true,
    },
  };
  export default {
    name: 'TagInput',
    mixins: [getFormMixins(attrs)],
    data() {
      return {
        isListOpen: false,
        varList: [],
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

      inputValue: {
        get() {
          return this.value;
        },
        set(val) {
          this.updateForm(val);
        },
      },
      viewValue() {
        if (this.value === '' || this.value === undefined) {
          return '--';
        }
        return this.showPassword ? '******' : this.value;
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
        if (!this.isListOpen) {
          return;
        }
        const listPanel = document.querySelector('.rf-select-list');
        if (listPanel && !dom.nodeContains(listPanel, e.target)) {
          this.isListOpen = false;
        }
      },
      onInput(val) {
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
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';

.tag-input {
    ::v-deep .el-input__inner {
        padding: 0 10px;
    }
    .rf-form-wrapper {
        position: relative;
        .rf-select-list {
            position: absolute;
            top: 40px;
            right: 0;
            width: 100%;
            background: #ffffff;
            border-radius: 2px;
            box-shadow: 0 0 8px 1px rgba(0, 0, 0, 0.1);
            overflow-y: hidden;
            z-index: 100;
        }
        .rf-select-content {
            max-height: 100px;
            overflow: auto;
            @include scrollbar;
        }
        .rf-select-item {
            padding: 0 10px;
            line-height: 32px;
            font-size: 12px;
            cursor: pointer;
            &:hover {
                background: #eef6fe;
                color: #3a84ff;
            }
            > span {
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
            }
            .var-name {
                max-width: 250px;
                color: #c4c6cc;
                margin-left: 16px;
            }
        }
    }
}
</style>
