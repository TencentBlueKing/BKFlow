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
  <div class="tag-python-code-input-vars">
    <bk-form
      ref="formRef"
      :label-width="0"
      :model="{ formList }">
      <div
        v-for="(item, index) in formList"
        :key="index"
        class="form-content-item">
        <bk-form-item
          :property="`formList.${index}.key`"
          :rules="keyRules">
          <bk-input
            v-model="item.key"
            :disabled="disabled || !editable"
            :placeholder="$t('参数名')"
            class="param-input" />
        </bk-form-item>
        <div class="var-input-wrapper">
          <bk-input
            v-model="item.value"
            :disabled="disabled || !editable"
            :placeholder="$t('请输入值或 $ 选择变量')"
            @input="onInput($event, index)"
            @focus="onFocus(index)"
            @blur="onBlur" />
          <!-- 变量提示列表 -->
          <variable-list
            :is-list-open="isListOpen && currentIndex === index"
            :var-list="varList"
            :textarea-height="32"
            @select="onSelectVal" />
        </div>
        <template v-if="!disabled && editable">
          <bk-button
            theme="default"
            icon="plus"
            class="var-button"
            @click="updateList(index, 'add')" />
          <bk-button
            theme="default"
            class="var-button"
            :disabled="formList.length === 1"
            @click="updateList(index, 'delete')">
            <i class="common-icon-zoom-minus" />
          </bk-button>
        </template>
      </div>
    </bk-form>
    <span
      v-show="!validateInfo.valid"
      class="common-error-tip error-info">{{ validateInfo.message }}</span>
  </div>
</template>
<script>
  import '@/utils/i18n.js';
  import { getFormMixins } from '../formMixins.js';
  import dom from '@/utils/dom.js';
  import { mapState } from 'vuex';
  import tools from '@/utils/tools.js';
  import VariableList from '../VariableList.vue';

  // 匹配变量的正则表达式 - 匹配 $ 开头的内容
  const VAR_REG = /\$.*$/;

  export const attrs = {
    value: {
      type: [Object],
      default: () => ({}),
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  };

  export default {
    name: 'TagFieldMappings',
    components: {
      VariableList,
    },
    mixins: [getFormMixins(attrs)],
    data() {
      // 将对象转换为数组用于显示
      const formList = this.objectToList(this.value);
      return {
        formList,
        varList: [],
        isListOpen: false,
        currentIndex: -1,
        isUpdatingFromFormList: false,
        isUpdatingFromValue: false,
      };
    },
    computed: {
      ...mapState({
        internalVariable: state => state.template.internalVariable,
      }),
      constantArr() {
        let keyList = [];
        if (this.constants) {
          keyList = Object.keys(this.constants).map(key => ({
            key,  // 直接使用 constants 的 key，它就是纯变量名
            name: this.constants[key].name || key,
          }));
        }
        if (this.internalVariable) {
          const internalVars = Object.keys(this.internalVariable).map(key => ({
            key,  // 直接使用 internalVariable 的 key
            name: this.internalVariable[key].name || key,
          }));
          keyList = [...keyList, ...internalVars];
        }
        return keyList;
      },
      keyRules() {
        return [
          {
            required: true,
            message: this.$t('参数名不能为空'),
            trigger: 'blur',
          },
          {
            validator: (val) => {
              // 校验 key 不重复
              const keys = this.formList.map(item => item.key).filter(key => key === val);
              return keys.length <= 1;
            },
            message: this.$t('参数名不能重复'),
            trigger: 'change',
          },
        ];
      },
    },
    watch: {
      formList: {
        handler(val) {
          // 如果正在从 value 更新 formList，跳过此次更新
          if (this.isUpdatingFromValue) {
            return;
          }
          const obj = this.listToObject(val);
          // 如果转换后的对象与当前 value 相同，跳过更新
          if (tools.isDataEqual(obj, this.value)) {
            return;
          }
          // 设置标志位，防止 value watch 触发
          this.isUpdatingFromFormList = true;
          this.updateForm(obj);
          // 使用 $nextTick 确保所有相关的 watcher 执行完毕后再重置标志位
          this.$nextTick(() => {
            this.isUpdatingFromFormList = false;
          });
        },
        deep: true,
      },
      value: {
        handler(val) {
          // 如果正在从 formList 更新 value，跳过此次更新
          if (this.isUpdatingFromFormList) {
            return;
          }
          const currentObj = this.listToObject(this.formList);
          // 如果新值与当前 formList 转换后的对象相同，跳过更新
          if (tools.isDataEqual(val, currentObj)) {
            return;
          }
          // 设置标志位，防止 formList watch 触发
          this.isUpdatingFromValue = true;
          this.formList = this.objectToList(val);
          this.$nextTick(() => {
            this.isUpdatingFromValue = false;
          });
        },
        immediate: false,
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
      objectToList(obj) {
        if (!obj || typeof obj !== 'object' || Object.keys(obj).length === 0) {
          return [{ key: 'arg1', value: '' }, { key: 'arg2', value: '' }];
        }
        return Object.entries(obj).map(([key, value]) => ({ key, value }));
      },
      listToObject(list) {
        const obj = {};
        list.forEach((item) => {
          if (item.key) {
            obj[item.key] = item.value;
          }
        });
        return obj;
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
      onInput(val, index) {
        const matchResult = val.match(VAR_REG);
        if (matchResult && matchResult[0]) {
          const searchStr = matchResult[0].substring(1); // 去掉 $ 符号
          this.varList = this.constantArr.filter(item => item.key.includes(searchStr));
          this.isListOpen = this.varList.length > 0;
          this.currentIndex = index;
        } else {
          this.varList = [];
          this.isListOpen = false;
        }
      },
      onBlur() {
        setTimeout(() => {
          this.isListOpen = false;
          this.currentIndex = -1;
        }, 200);
      },
      onFocus(index) {
        this.currentIndex = index;
        // 如果已经输入了 $ 符号，立即显示提示
        const val = this.formList[index].value;
        if (val && val.includes('$')) {
          this.onInput(val, index);
        }
      },
      onSelectVal(val) {
        const varRef = val;
        const replacedValue = this.formList[this.currentIndex].value.replace(VAR_REG, varRef);
        this.formList[this.currentIndex].value = replacedValue;
        this.isListOpen = false;
        this.currentIndex = -1;
      },
      updateList(index, type) {
        if (type === 'delete') {
          this.formList.splice(index, 1);
        } else {
          this.formList.splice(index + 1, 0, {
            key: '',
            value: '',
          });
        }
      },
      validate() {
        return this.$refs.formRef.validate().catch((e) => {
          console.error(e);
          return false;
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../../scss/mixins/scrollbar.scss';

.tag-python-code-input-vars {
  .form-content-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 10px;

    .param-input {
      width: 200px;
    }

    .var-input-wrapper {
      position: relative;
      flex: 1;
    }
    ::v-deep .bk-form-item {
      margin-bottom: 0;
    }
    .var-button{
      margin-right: 2px;
      min-width: 32px !important;
      padding: 0 !important;
    }
  }

  .error-info {
    margin-top: 4px;
    display: block;
  }
}
</style>
