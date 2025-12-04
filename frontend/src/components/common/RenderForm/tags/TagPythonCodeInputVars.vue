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
    <bk-form ref="formRef" :label-width="0" :model="{ formList }">
      <div
        v-for="(item, index) in formList"
        :key="index"
        class="form-content-item">
        <bk-form-item
          :property="`formList.${index}.key`"
          :rules="keyRules">
          <bk-input
            v-model="item.key"
            :disabled="disabled"
            :placeholder="$t('参数名')"
            class="param-input" />
        </bk-form-item>
        <div class="var-input-wrapper">
          <bk-input
            v-model="item.value"
            :disabled="disabled"
            :placeholder="$t('请输入值或 $ 选择变量')"
            @input="onInput($event, index)"
            @focus="onFocus(index)"
            @blur="onBlur" />
          <!-- 变量提示列表 -->
          <ul
            v-show="isListOpen && currentIndex === index"
            class="rf-select-list">
            <li
              v-for="(varItem, varIndex) in varList"
              :key="varIndex"
              class="var-item"
              @mousedown="onSelectVal(varItem.key, index)">
              <span class="var-key">{{ varItem.key }}</span>
              <span class="var-name">{{ varItem.name }}</span>
            </li>
          </ul>
        </div>
        <template v-if="!disabled">
          <bk-button
            icon="icon-plus-line"
            class="add-btn"
            @click="updateList(index, 'add')" />
          <bk-button
            icon="icon-minus-line"
            class="delete-btn"
            :disabled="formList.length === 1"
            @click="updateList(index, 'delete')" />
        </template>
      </div>
    </bk-form>
    <span v-show="!validateInfo.valid" class="common-error-tip error-info">{{validateInfo.message}}</span>
  </div>
</template>
<script>
  import '@/utils/i18n.js'
  import { getFormMixins } from '../formMixins.js'
  import dom from '@/utils/dom.js'
  import { mapState } from 'vuex'

  // 匹配变量的正则表达式 - 匹配 $ 开头的内容
  const VAR_REG = /\$.*$/

  export const attrs = {
    value: {
      type: [Object],
      default: () => ({}),
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  }

  export default {
    name: 'TagPythonCodeInputVars',
    mixins: [getFormMixins(attrs)],
    data() {
      // 将对象转换为数组用于显示
      const formList = this.objectToList(this.value)
      return {
        formList,
        varList: [],
        isListOpen: false,
        currentIndex: -1,
      }
    },
    computed: {
      ...mapState({
        internalVariable: state => state.template.internalVariable,
      }),
      constantArr() {
        let keyList = []
        if (this.constants) {
          keyList = Object.keys(this.constants).map(key => ({
            key: key,  // 直接使用 constants 的 key，它就是纯变量名
            name: this.constants[key].name || key,
          }))
        }
        if (this.internalVariable) {
          const internalVars = Object.keys(this.internalVariable).map(key => ({
            key: key,  // 直接使用 internalVariable 的 key
            name: this.internalVariable[key].name || key,
          }))
          keyList = [...keyList, ...internalVars]
        }
        return keyList
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
              const keys = this.formList.map(item => item.key).filter(key => key === val)
              return keys.length <= 1
            },
            message: this.$t('参数名不能重复'),
            trigger: 'change',
          },
        ]
      },
    },
    created() {
      window.addEventListener('click', this.handleListShow, false)
    },
    beforeDestroy() {
      window.removeEventListener('click', this.handleListShow, false)
    },
    watch: {
      formList: {
        handler(val) {
          // 将数组转换回对象
          const obj = this.listToObject(val)
          this.updateForm(obj)
        },
        deep: true,
      },
      value: {
        handler(val) {
          this.formList = this.objectToList(val)
        },
        immediate: false,
        deep: true,
      },
    },
    methods: {
      objectToList(obj) {
        if (!obj || typeof obj !== 'object' || Object.keys(obj).length === 0) {
          return [{ key: 'arg1', value: '' }, { key: 'arg2', value: '' }]
        }
        return Object.entries(obj).map(([key, value]) => ({ key, value }))
      },
      listToObject(list) {
        const obj = {}
        list.forEach(item => {
          if (item.key) {
            obj[item.key] = item.value
          }
        })
        return obj
      },
      handleListShow(e) {
        if (!this.isListOpen) {
          return
        }
        const listPanel = document.querySelector('.rf-select-list')
        if (listPanel && !dom.nodeContains(listPanel, e.target)) {
          this.isListOpen = false
        }
      },
      onInput(val, index) {
        const matchResult = val.match(VAR_REG)
        if (matchResult && matchResult[0]) {
          const searchStr = matchResult[0].substring(1) // 去掉 $ 符号
          this.varList = this.constantArr.filter(item => {
            return item.key.includes(searchStr)
          })
          this.isListOpen = this.varList.length > 0
          this.currentIndex = index
        } else {
          this.varList = []
          this.isListOpen = false
        }
      },
      onBlur() {
        setTimeout(() => {
          this.isListOpen = false
          this.currentIndex = -1
        }, 200)
      },
      onFocus(index) {
        this.currentIndex = index
        // 如果已经输入了 $ 符号，立即显示提示
        const val = this.formList[index].value
        if (val && val.includes('$')) {
          this.onInput(val, index)
        }
      },
      onSelectVal(val, index) {
        // 替换为 ${var_key} 格式
        const varRef = `\${${val}}`
        const replacedValue = this.formList[index].value.replace(VAR_REG, varRef)
        this.formList[index].value = replacedValue
        this.isListOpen = false
        this.currentIndex = -1
      },
      updateList(index, type) {
        if (type === 'delete') {
          this.formList.splice(index, 1)
        } else {
          this.formList.splice(index + 1, 0, {
            key: '',
            value: '',
          })
        }
      },
      validate() {
        return this.$refs.formRef.validate()
      },
    },
  }
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

    .add-btn,
    .delete-btn {
      width: 32px;
      min-width: 32px;
      padding: 0;
      margin-top: 0;
    }

    ::v-deep .bk-form-item {
      margin-bottom: 0;
    }
  }

  .rf-select-list {
    position: absolute;
    top: 32px;
    left: 0;
    right: 0;
    max-height: 200px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    @include scrollbar;

    .var-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 12px;

      &:hover {
        background: #f0f1f5;
      }

      .var-key {
        color: #313238;
        font-weight: 500;
        margin-right: 12px;
      }

      .var-name {
        color: #979ba5;
      }
    }
  }

  .error-info {
    margin-top: 4px;
    display: block;
  }
}
</style>
