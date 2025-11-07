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
  <div class="output-params">
    <bk-table
      v-if="list.length"
      :data="list"
      :col-border="false"
      :row-class-name="getRowClassName">
      <bk-table-column
        :label="$t('名称')"
        :width="180"
        prop="name">
        <p
          slot-scope="{ row }"
          v-bk-tooltips="{ content: row.description, disabled: !row.description }"
          :class="['output-name', { 'has-tips': row.description }]">
          {{ row.name }}
        </p>
      </bk-table-column>
      <bk-table-column label="KEY">
        <div
          slot-scope="{ row }"
          class="output-key">
          <div
            v-bk-overflow-tips
            class="key">
            {{ row.key }}
          </div>
          <!--编辑变量-Input-->
          <div
            v-if="row.hooked"
            class="hooked-input">
            {{ row.varKey }}
            <i
              v-if="!isViewMode"
              class="bk-icon icon-edit-line"
              @click="$emit('openVariablePanel', { key: row.varKey })" />
          </div>
        </div>
      </bk-table-column>
      <bk-table-column
        :label="$t('勾选为全局变量')"
        :width="120">
        <i
          slot-scope="props"
          v-bk-tooltips="{
            content: props.row.hooked ? $t('取消接收输出') : $t('使用变量接收输出'),
            placement: 'top',
            zIndex: 3000
          }"
          :class="['common-icon-variable-hook hook-icon', {
            actived: props.row.hooked,
            disabled: isViewMode || !hook
          }]"
          @click="onHookChange(props)" />
      </bk-table-column>
    </bk-table>
    <no-data
      v-else
      :message="$t('暂无参数')" />
  </div>
</template>
<script>
  import { random4 } from '@/utils/uuid.js';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'OutputParams',
    components: {
      NoData,
    },
    props: {
      params: {
        type: Array,
        default: () => ([]),
      },
      hook: {
        type: Boolean,
        default: true,
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      thirdPartyCode: {
        type: String,
        default: '',
      },
      isSubflow: Boolean,
      isViewMode: Boolean,
      nodeId: {
        type: String,
        default: '',
      },
      version: {
        type: String,
        default: '',
      }, // 标准插件版本或子流程版本
      uniformOutputs: {
        type: Array,
        default: () => ([]),
      }, // api插件输出参数
    },
    data() {
      const list = this.getOutputsList(this.params);
      return {
        list,
        selectIndex: '',
        unhookingVarIndex: 0, // 正被取消勾选的表单下标
      };
    },
    watch: {
      params(val) {
        this.list = this.getOutputsList(val);
      },
    },
    methods: {
      getOutputsList() {
        const list = [];
        const varKeys = Object.keys(this.constants);
        this.params.forEach((param) => {
          let { key: varKey } = param;
          const isHooked = varKeys.some((item) => {
            let result = false;
            const varItem = this.constants[item];
            if (varItem.source_type === 'component_outputs') {
              // 获取该变量在当前节点下的源信息
              const sourceInfo = varItem.source_info[this.nodeId];
              if (sourceInfo && sourceInfo.includes(param.key)) {
                varKey = item; // 更新变量key名称
                result = true;
              }
            }
            return result;
          });
          let desc = param.schema ? param.schema.description : '--';
          desc = param.fromDmn ? param.tips : desc;
          const info = {
            key: param.key,
            varKey,
            name: param.name,
            description: desc,
            version: param.version,
            status: param.status,
            hooked: isHooked,
          };
          list.push(info);
        });
        return list;
      },
      getRowClassName({ row }) {
        return row.status || '';
      },
      handleBeforeChange() {
        console.log('111');
      },
      /**
       * 输出参数勾选切换
       */
      onHookChange(props) {
        if (this.isViewMode) return;
        const index = props.$index;
        this.unhookingVarIndex = index;
        if (!props.row.hooked) {
          props.row.hooked = true;
          // 输出选中默认新建不弹窗，直接生成变量。 如果有冲突则key+随机数
          const { key, version, plugin_code: pluginCode } = props.row;
          const value = /^\$\{\w+\}$/.test(key) ? key : `\${${key}}`;
          const isExist = value in this.constants;
          let setKey = '';
          if ((/^\$\{((?!\{).)*\}$/).test(key)) {
            setKey = isExist ? `${key.slice(0, -1)}_${random4()}}` : key;
            props.row.varKey = setKey;
          } else {
            setKey = isExist ? `\$\{${`${key}_${random4()}`}\}` : `\$\{${key}\}`;
            props.row.varKey = setKey;
          }
          const config = {
            name: props.row.name,
            key: setKey,
            source_info: {
              [this.nodeId]: [this.params[index].key],
            },
            version,
            plugin_code: this.isSubflow ? pluginCode : (this.thirdPartyCode || ''),
            custom_type: props.row.type ?? '',
          };
          if (key === 'data' && this.uniformOutputs.length) {
            config.extra_info = this.getUniformExtraInfo();
          }
          this.createVariable(config);
        } else {
          const config = ({
            type: 'delete',
            id: this.nodeId,
            key: props.row.varKey,
            tagCode: props.row.varKey,
            source: 'output',
            custom_type: props.row.type ?? '',
          });
          this.$emit('hookChange', 'delete', config);
        }
      },
      // 变量勾选/取消勾选后，需重新对form进行赋值
      setFormData() {
        const index = this.unhookingVarIndex;
        this.list[index].hooked = false;
      },
      createVariable(variableOpts) {
        const len = Object.keys(this.constants).length;
        const defaultOpts = {
          name: '',
          key: '',
          desc: '',
          custom_type: '',
          source_info: {},
          source_tag: '',
          value: '',
          show_type: 'hide',
          source_type: 'component_outputs',
          validation: '',
          index: len,
          version: '',
          plugin_code: '',
        };
        const variable = Object.assign({}, defaultOpts, variableOpts);
        this.$emit('hookChange', 'create', variable);
      },
      getUniformExtraInfo() {
        return this.uniformOutputs.reduce((acc, cur) => {
          const { key, name, meta_desc: metaDesc } = cur;
          const value = { name };
          if (metaDesc) {
            value.meta_desc = metaDesc;
          }
          acc[key] = value;
          return acc;
        }, {});
      },
    },
  };
</script>
<style lang="scss" scoped>
    .bk-table {
        ::v-deep .bk-table-row {
            &.deleted {
                background: #fff5f4;
            }
            &.added {
                background: rgba(220,255,226,0.30);
            }
        }
    }
    .output-key {
      display: flex;
      align-items: center;
      .key {
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      .key-input,
      .hooked-input {
        flex: 1;
        height: 32px;
        min-width: 180px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 8px;
        margin-left: 15px;
        background: #fafbfd;
        border: 1px solid #dcdee5;
        border-radius: 2px;
      }
      .icon-edit-line {
        width: 24px;
        height: 24px;
        display: inline-block;
        text-align: center;
        line-height: 24px;
        font-size: 16px;
        color: #979ba5;
        background: #f0f1f5;
        border-radius: 2px;
        cursor: pointer;
        &:hover {
          color: #3a84ff;
          background: #e1ecff;
        }
      }
      .key-input {
        position: relative;
        margin-left: 0;
        padding: 0;
        border: none;
        &.valid-error {
          ::v-deep .bk-form-control {
            .bk-form-input {
              border-color: #ea3636;
            }
            &.control-active + .tooltips-icon {
              display: none;
            }
          }
          .tooltips-icon {
            position: absolute;
            z-index: 10;
            right: 8px;
            top: 8px;
            color: #ea3636;
            cursor: pointer;
            font-size: 16px;
          }
        }
      }
    }
    .output-name {
        display: inline-block;
        max-width: 100%;
        cursor: default;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        &.has-tips {
          border-bottom: 1px dashed #979ba5;
        }
    }
    .hook-icon {
        display: inline-block;
        position: absolute;
        right: 22px;
        top: 5px;
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 32px;
        font-size: 16px;
        color: #979ba5;
        background: #f0f1f5;
        text-align: center;
        border-radius: 2px;
        cursor: pointer;
        &.disabled {
            color: #c4c6cc;
            cursor: not-allowed;
        }
        &.actived {
            color: #3a84ff;
            background: #e2edff;
        }
    }
</style>
