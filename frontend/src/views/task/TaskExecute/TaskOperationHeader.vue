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
  <div class="operation-header">
    <div class="head-left-area">
      <!-- <i class="bk-icon icon-arrows-left back-icon" @click="onBack"></i> -->
      <div class="operation-title">
        {{ $t('任务执行') }}
      </div>
      <div class="bread-crumbs-wrapper">
        <span
          v-for="(path, index) in nodeNav"
          :key="path.id"
          :class="['path-item', { 'name-ellipsis': nodeNav.length > 1 }]"
          :title="showNodeList.includes(index) ? path.name : ''">
          <span v-if="!!index && showNodeList.includes(index) || index === 1">/</span>
          <span
            v-if="showNodeList.includes(index)"
            class="node-name"
            :title="path.name"
            @click="onSelectSubflow(path.id)">
            {{ path.name }}
          </span>
          <span
            v-else-if="index === 1"
            class="node-ellipsis">...</span>
        </span>
      </div>
      <router-link
        v-if="isShowViewProcess"
        v-bk-tooltips="{
          content: $t('查看流程'),
          placements: ['top']
        }"
        class="common-icon-jump-link"
        :target="isIframe ? '_self' : '_blank'"
        :to="`/template/view/${spaceId}/?template_id=${templateId}`" />
      <span
        v-if="stateStr"
        :class="['task-state', state]">{{ stateStr }}</span>
    </div>
    <div
      slot="expand"
      class="operation-container">
      <div
        v-show="isTaskOperationBtnsShow"
        class="task-operation-btns">
        <bk-button
          v-for="operation in taskOperationBtns"
          :key="operation.action"
          v-bk-tooltips="{
            content: operation.text,
            placements: ['top']
          }"
          :class="[
            'operation-btn',
            operation.action === 'revoke' ? 'revoke-btn' : 'execute-btn'
          ]"
          theme="default"
          hide-text="true"
          :icon="'common-icon ' + operation.icon"
          :loading="operation.loading"
          :disabled="operation.disabled || !instanceActions.includes('OPERATE')"
          :data-test-id="`taskExcute_form_${operation.action}Btn`"
          @click="onOperationClick(operation.action)" />
      </div>
      <div class="task-params-btns">
        <!-- <i
          :class="[
            'params-btn',
            'common-icon-enter-config',
            {
              actived: nodeInfoType === 'modifyParams'
            }
          ]"
          v-bk-tooltips="{
            content: $t('任务入参'),
            placements: ['top'],
            hideOnClick: false
          }"
          @click="onTaskParamsClick('modifyParams', $t('任务入参'))">
        </i> -->
        <i
          v-bk-tooltips="{
            content: $t('查看节点详情'),
            placements: ['top']
          }"
          :class="[
            'params-btn',
            'solid-eye',
            'common-icon-solid-eye',
            {
              actived: nodeInfoType === 'viewNodeDetails'
            }
          ]"
          @click="onTaskParamsClick('viewNodeDetails', $t('节点详情'))" />
        <bk-popover
          placement="bottom-left"
          theme="light"
          ext-cls="operate-tip">
          <i class="bk-icon icon-more drop-icon-ellipsis" />
          <template slot="content">
            <p
              class="operate-item"
              @click="onTaskParamsClick('operateFlow', $t('操作记录'))">
              {{ $t('操作记录') }}
            </p>
            <p
              v-if="state !== 'CREATED'"
              class="operate-item"
              @click="onTaskParamsClick('globalVariable', $t('全局变量'))">
              {{ $t('全局变量') }}
            </p>
            <p
              class="operate-item"
              @click="onTaskParamsClick('templateData', 'Code')">
              {{ 'Code' }}
            </p>
          </template>
        </bk-popover>
      </div>
    </div>
  </div>
</template>
<script>
  import permission from '@/mixins/permission.js';
  // import PageHeader from '@/components/layout/PageHeader.vue'
  import { mapState } from 'vuex';

  export default {
    name: 'TaskOperationHeader',
    components: {
      // PageHeader,
    },
    mixins: [permission],
    props: {
      nodeInfoType: {
        type: String,
        default: '',
      },
      nodeNav: {
        type: Array,
        default: () => ({}),
      },
      spaceId: {
        type: [Number, String],
        default: '',
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      primitiveTplId: {
        type: [Number, String],
        default: '',
      },
      primitiveTplSource: {
        type: String,
        default: '',
      },
      instanceActions: {
        type: Array,
        default: () => ({}),
      },
      taskOperationBtns: {
        type: Array,
        default: () => ({}),
      },
      adminView: Boolean,
      state: {
        type: String,
        default: '',
      },
      stateStr: {
        type: String,
        default: '',
      },
      isTaskOperationBtnsShow: Boolean,
      isShowViewProcess: Boolean,
    },
    data() {
      return {
        showNodeList: [0, 1, 2],
      };
    },
    computed: {
      ...mapState({
        isIframe: state => state.isIframe,
        view_mode: state => state.view_mode,
      }),
    },
    watch: {
      nodeNav(val) {
        if (val.length > 3) {
          this.showNodeList = [0, val.length - 1, val.length - 2];
        } else {
          this.showNodeList = [0, 1, 2];
        }
      },
    },
    methods: {
      onSelectSubflow(id) {
        this.$emit('onSelectSubflow', id);
      },
      onOperationClick(action) {
        this.$emit('onOperationClick', action);
      },
      onTaskParamsClick(type, name) {
        this.$emit('onTaskParamsClick', type, name);
      },
      onBack() {
        if (this.view_mode === 'appmaker') {
          return this.$router.push({
            name: 'appmakerTaskHome',
            params: { type: 'edit', app_id: this.$route.params.app_id, project_id: this.project_id },
            query: { template_id: this.$route.query.templateId },
          });
        }
        if (this.$route.path.indexOf('/function') === 0) {
          return this.$router.push({
            name: 'functionHome',
          });
        }
        if (this.$route.path.indexOf('/audit') === 0) {
          return this.$router.push({
            name: 'auditHome',
          });
        }
        // 当任务执行页由创建任务路由过来时，应该返回到任务列表页
        const isFromCreate = this.$route.query.from === 'create';
        if (!isFromCreate && this.$route.name === 'taskExecute' && window.history.length > 2) {
          return this.$router.back();
        }
        this.$router.push({
          name: 'taskList',
          params: { project_id: this.project_id },
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../scss/config.scss';

.operation-header {
    display: flex;
    justify-content: space-between;
    height: 48px;
    padding: 0 20px 0 10px;
    border-bottom: 1px solid #dcdee5;
    box-shadow: 0 3px 4px 0 rgba(64, 112, 203, 0.06);
    background: #ffffff;
    .head-left-area {
        display: flex;
        align-items: center;
        .back-icon {
            font-size: 28px;
            color: #3a84ff;
            cursor: pointer;
        }
    }
    .operation-title {
        font-size: 14px;
        color: #313238;
    }
    .bread-crumbs-wrapper {
        margin-left: 10px;
        font-size: 0;
        .path-item {
            display: inline-block;
            font-size: 14px;
            overflow: hidden;
            &.name-ellipsis {
                max-width: 190px;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
            }
            .node-name {
                margin: 0 4px;
                font-size: 14px;
                color: #3a84ff;
                cursor: pointer;
            }
            .node-ellipsis {
                margin-right: 4px;
            }
            &:first-child {
                .node-name {
                    margin-left: 0px;
                }
            }
            &:last-child {
                .node-name {
                    &:last-child {
                        color: #313238;
                        cursor: text;
                    }
                }
            }
        }
    }
    .common-icon-jump-link {
        color: #3a84ff;
        margin: 0 8px 0 4px;
    }
    .task-state {
        display: inline-block;
        margin-left: 10px;
        padding: 0 6px;
        height: 20px;
        line-height: 20px;
        font-size: 12px;
        color: #63656e;
        border-radius: 10px;
        background-color: #dcdee5;
        &.EXPIRED,
        &.CREATED {
            color: #63656e;
        }
        &.FINISHED {
            background-color: #cceed9;
            color: #2dcb56;
        }
        &.RUNNING,
        &.READY {
            background-color: #cfdffb;
            color: #3a84ff;
        }
        &.SUSPENDED, &.NODE_SUSPENDED {
            background-color: #ffe8c3;
            color: #d78300;
        }
        &.FAILED {
            background-color: #f2d0d3;
            color: #ea3636;
        }
        &.REVOKED {
            background-color: #f2d0d3;
            color: #ea3636;
        }
    }
    .operation-container {
        display: flex;
        align-items: center;
        height: 100%;
        .task-operation-btns,
        .task-params-btns {
            float: left;
            .bk-button {
                border: none;
                background: transparent;
                cursor: pointer;
            }
            /deep/ .bk-icon {
                float: initial;
                top: 0;
                & + span {
                    margin-left: 0;
                }
            }
            .common-icon-branchs {
                font-size: 16px;
            }
        }
        .task-operation-btns {
            margin-right: 35px;
            line-height: initial;
            border-right: 1px solid #dde4eb;
            .operation-btn {
                margin-right: 35px;
                height: 32px;
                line-height: 32px;
                font-size: 14px;
                &.btn-permission-disable {
                    background: transparent !important;
                }
            }
            .execute-btn {
                width: 140px;
                color: #ffffff;
                background: #3a84ff; // 覆盖 bk-button important 规则
                &:hover {
                    background: #699df4; // 覆盖 bk-button important 规则
                }
                &.is-disabled {
                    color: #ffffff; // 覆盖 bk-button important 规则
                    opacity: 0.4;
                    cursor: no-drop;
                }
                &.btn-permission-disable {
                    border: 1px solid #e6e6e6;
                }
                /deep/ .bk-button-loading div {
                    background: #ffffff;
                }
            }
            .revoke-btn {
                padding: 0;
                background: transparent; // 覆盖 bk-button important 规则
                color: #ea3636;
                &:hover {
                    color: #c32929;
                }
                &.is-disabled {
                    color: #d8d8d8;
                }
                /deep/.common-icon-stop {
                    font-size: 24px;
                    margin-top: 10px;
                }
            }
        }
        .task-params-btns {
            .params-btn {
                margin-right: 25px;
                padding: 0;
                color: #979ba5;
                font-size: 14px;
                cursor: pointer;
                &.actived {
                    color: #63656e;
                }
                &:hover {
                    color: #63656e;
                }
            }
            .common-icon-enter-config {
                font-size: 18px;
            }
            .back-button {
                background: #ffffff;
                border: 1px solid #c4c6cc;
            }
            .drop-icon-ellipsis {
                font-size: 18px;
                font-weight: 600;
                color: #979ba5;
                cursor: pointer;
                &:hover {
                    color: #63656e;
                }
            }
        }
    }
    /deep/.bk-button .bk-icon {
        font-size: 14px;
    }
}
</style>
<style lang="scss">
.operate-tip {
    .tippy-tooltip {
        padding: 4px 0;
    }
    .operate-item {
        width: 160px;
        height: 40px;
        display: block;
        line-height: 40px;
        padding-left: 10px;
        color: #313238;
        font-size: 12px;
        cursor: pointer;
        &:hover {
            color: #3a84ff;
            background: #eaf3ff;
        }
    }
}
</style>
