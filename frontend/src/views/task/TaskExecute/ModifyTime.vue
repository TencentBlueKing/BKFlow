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
  <div
    v-bkloading="{ isLoading: loading, opacity: 1, zIndex: 100 }"
    class="modify-time-container">
    <div class="edit-wrapper">
      <RenderForm
        v-if="!isEmptyParams"
        ref="renderForm"
        v-model="renderData"
        :scheme="renderConfig"
        :form-option="renderOption" />
      <NoData v-else />
    </div>
    <div
      v-if="!isEmptyParams"
      class="action-wrapper">
      <bk-button
        theme="primary"
        class="confirm-btn"
        :loading="modifyTimeLoading"
        data-test-id="taskExcute_form_saveModifyTimeBtn"
        @click="onModifyTime">
        {{ $t('确定') }}
      </bk-button>
      <bk-button
        theme="default"
        data-test-id="taskExcute_form_cancelBtn"
        @click="onCancelRetry">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import { mapState, mapActions } from 'vuex';
  import tools from '@/utils/tools.js';
  import NoData from '@/components/common/base/NoData.vue';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import atomFilter from '@/utils/atomFilter.js';
  export default {
    name: 'ModifyTime',
    components: {
      RenderForm,
      NoData,
    },
    props: {
      nodeDetailConfig: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        modifyTimeLoading: false,
        loading: true,
        bkMessageInstance: null,
        nodeInfo: {},
        renderOption: {
          showGroup: false,
          showLabel: true,
          showHook: false,
        },
        renderConfig: [],
        renderData: {},
        initalRenderData: {},
      };
    },
    computed: {
      ...mapState({
        spaceId: state => state.template.spaceId,
        atomFormConfig: state => state.atomForm.config,
      }),
      ...mapState('project', {
        project_id: state => state.project_id,
      }),
      isEmptyParams() {
        return Object.keys(this.renderData).length === 0;
      },
    },
    mounted() {
      this.loadNodeInfo();
    },
    methods: {
      ...mapActions('task/', [
        'getNodeActDetail',
        'setSleepNode',
      ]),
      ...mapActions('atomForm/', [
        'loadAtomConfig',
      ]),
      async loadNodeInfo() {
        this.loading = true;
        try {
          const { version } = this.nodeDetailConfig;
          const nodeDetailRes = await this.getNodeActDetail(this.nodeDetailConfig);
          this.renderConfig = await this.getNodeConfig(this.nodeDetailConfig.component_code, version);
          this.nodeInfo = nodeDetailRes.data;
          if (nodeDetailRes.result) {
            Object.keys(this.nodeInfo.inputs).forEach((key) => {
              this.$set(this.renderData, key, this.nodeInfo.inputs[key]);
            });
            this.initalRenderData = this.renderData;
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.loading = false;
        }
      },
      async getNodeConfig(type, version) {
        if (atomFilter.isConfigExists(type, version, this.atomFormConfig)) {
          return this.atomFormConfig[type][version];
        }
        try {
          await this.loadAtomConfig({ atom: type, version, space_id: this.spaceId });
          return this.atomFormConfig[type][version];
        } catch (e) {
          console.log(e);
        }
      },
      judgeDataEqual() {
        return tools.isDataEqual(this.initalRenderData, this.renderData);
      },
      async onModifyTime() {
        let formvalid = true;
        if (this.$refs.renderForm) {
          formvalid = await this.$refs.renderForm.validate();
        }
        if (!formvalid || this.modifyTimeLoading) return false;

        const { instance_id, component_code, node_id } = this.nodeDetailConfig;
        const data = {
          instance_id,
          node_id,
          component_code,
          inputs: this.renderData,
        };
        this.modifyTimeLoading = true;
        try {
          const res = await this.setSleepNode(data);
          if (res.result) {
            this.$emit('modifyTimeSuccess', node_id);
            this.$bkMessage({
              message: i18n.t('修改成功'),
              theme: 'success',
            });
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.modifyTimeLoading = false;
        }
      },
      onCancelRetry() {
        const { node_id } = this.nodeDetailConfig;
        this.$emit('modifyTimeCancel', node_id);
      },
    },
  };
</script>
<style lang="scss" scoped>
    @import '../../../scss/config.scss';
    @import '../../../scss/mixins/scrollbar.scss';
    .modify-time-container {
        position: relative;
        height: 100%;
        overflow: hidden;
        .edit-wrapper {
            padding: 20px 20px 0;
            height: calc(100% - 60px);
            overflow-y: auto;
            @include scrollbar;
        }
        .action-wrapper {
            padding-left: 20px;
            height: 60px;
            line-height: 60px;
            border-top: 1px solid $commonBorderColor;
            .confirm-btn{
                margin-right: 12px;
            }
        }
    }
</style>
