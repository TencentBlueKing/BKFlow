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
  <div class="condition-form">
    <div class="form-wrap">
      <div class="form-item">
        <label class="label">
          {{ $t('分支类型') }}
        </label>
        <bk-radio-group v-model="branchType">
          <bk-radio
            :value="'customize'"
            :disabled="isReadonly">
            {{ $t('自定义分支') }}
          </bk-radio>
          <bk-radio
            :value="'default'"
            :disabled="isReadonly || hasDefaultBranch">
            {{ $t('默认分支') }}
            <i
              v-bk-tooltips="defaultTipsConfig"
              class="common-icon-info" />
          </bk-radio>
        </bk-radio-group>
      </div>
      <div
        v-if="branchType === 'customize'"
        class="form-item">
        <label class="label">
          {{ $t('表达式') }}
          <span class="required">*</span>
        </label>
        <div class="code-wrapper">
          <condition-expression
            :parse-lang="gwConfig.extra_info && gwConfig.extra_info.parse_lang" />
          <full-code-editor
            v-validate="expressionRule"
            name="expression"
            :value="expression"
            :options="{ language: 'python', readOnly: isReadonly }"
            @input="onDataChange" />
        </div>
        <span
          v-show="veeErrors.has('expression')"
          class="common-error-tip error-msg">
          {{ veeErrors.first('expression') }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
  import i18n from '@/config/i18n/index.js';
  import { mapMutations } from 'vuex';
  import { NAME_REG } from '@/constants/index.js';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import ConditionExpression from '../../template/TemplateEdit/components/ConditionExpression.vue';

  export default {
    name: 'ConditionEdit',
    components: {
      ConditionExpression,
      FullCodeEditor,
    },
    props: {
      gateways: {
        type: Object,
        default: () => ({}),
      },
      conditionData: {
        type: Object,
        default: () => ({}),
      },
      backToVariablePanel: Boolean,
      isReadonly: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      const { name, value, id, nodeId } = this.conditionData;
      const gwConfig = this.gateways[nodeId];
      const defaultCondition = gwConfig && gwConfig.default_condition; // 默认分支配置
      const isDefaultBranch = defaultCondition && defaultCondition.flow_id === id; // 当前分支是否为默认分支
      const branchType = isDefaultBranch ? 'default' : 'customize';
      let hasDefaultBranch = false;
      if (defaultCondition && defaultCondition.flow_id !== id) {
        hasDefaultBranch = true;
      }
      const expression = this.toggleExpressionFormat(value);
      return {
        gwConfig,
        branchType, // 当前分支类型
        hasDefaultBranch, // 是否存在默认分支(不包含当前分支)
        defaultTipsConfig: {
          width: 216,
          content: i18n.t('所有分支均不匹配时执行，类似switch-case-default里面的default'),
          placements: ['bottom-start'],
        },
        conditionName: name,
        expression,
        conditionRule: {
          required: true,
          max: 20,
          regex: NAME_REG,
        },
        expressionRule: {
          required: true,
        },
      };
    },
    watch: {
      conditionData(val) {
        const { name, value } = val;
        this.conditionName = name;
        this.expression = this.toggleExpressionFormat(value);
      },
      branchType: {
        handler(val) {
          if (val === 'default') {
            this.conditionName = i18n.t('默认');
          } else {
            this.conditionName = this.conditionData.name;
          }
        },
      },
    },
    methods: {
      ...mapMutations('template/', [
        'setBranchCondition',
      ]),
      onDataChange(val) {
        this.expression = val;
      },
      toggleExpressionFormat(str, slice = true) {
        const gwConfig = this.gateways[this.conditionData.nodeId];
        const { parse_lang: parseLang } = gwConfig.extra_info || {};
        if (parseLang !== 'MAKO') {
          return str;
        }
        if (slice) {
          return /^\${.+\}$/.test(str) ? str.slice(2, -1) : str;
        }
        return `\${${str}}`;
      },
    },
  };
</script>

<style lang="scss" scoped>
    @import '../../../scss/mixins/scrollbar.scss';
    .config-header {
        display: flex;
        align-items: center;
        .variable-back-icon {
            font-size: 32px;
            cursor: pointer;
            &:hover {
                color: #3a84ff;
            }
        }
    }
    .condition-form {
        height: calc(100vh - 60px);
        .form-wrap {
            height: calc(100% - 49px);
        }
        .form-item {
            margin-bottom: 20px;
            .label {
                display: block;
                position: relative;
                line-height: 36px;
                color: #313238;
                font-size: 14px;
                .required {
                    color: #ff2602;
                }
            }
            .bk-form-radio {
                margin-right: 48px;
                .common-icon-info {
                    color: #979ba5;
                }
            }
        }
        .expression-tips {
            margin-left: 6px;
            color:#c4c6cc;
            font-size: 16px;
            cursor: pointer;
            &:hover {
                color:#f4aa1a;
            }
            &.quote-info {
                margin-left: 0px;
            }
        }
        .btn-wrap {
            position: relative;
            padding: 8px 20px;
            border-top: 1px solid #cacedb;
            background: #fff;
        }
    }
    .code-wrapper .full-code-editor {
        height: 300px;
    }
</style>
