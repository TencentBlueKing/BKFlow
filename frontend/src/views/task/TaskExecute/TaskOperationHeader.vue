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
        :to="`/template/view/${templateId}/`" />
      <span
        v-if="stateStr"
        :class="['task-state', state]">{{ stateStr }}</span>
      <span
        v-if="ifShowJumpToFlowBtn"
        class="commonicon-icon common-icon-box-top-right-corner link-icon"
        @click="linkToFlow" />
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
        <div
          v-if="triggerMethod !=='subprocess' "
          class="task-params-btns">
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
        <div
          v-else
          class="sub-task-btns">
          <i class="common-icon-box-top-right-corner icon-link-to-father" />
          <p
            class="view-father-process"
            @click="onViewFatherProcessExecute">
            {{ $t('查看父流程') }}
          </p>
          <span class="dividing-line" />
          <span :class="statusMap[parentTaskInfo.state].icon" />
          <span class="state-text">{{ statusMap[parentTaskInfo.state].text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
  import permission from '@/mixins/permission.js';
  // import PageHeader from '@/components/layout/PageHeader.vue'
  import { mapState } from 'vuex';
  import i18n from '@/config/i18n/index.js';

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
      triggerMethod: {
        type: String,
        default: '',
      },
      parentTaskInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        showNodeList: [0, 1, 2],
        isSubflow: false,
        statusMap: {
          FINISHED: {
            icon: 'finished bk-icon icon-check-circle-shape',
            text: i18n.t('完成'),
          },
          FAILED: {
            icon: 'failed common-icon-dark-circle-close',
            text: i18n.t('失败'),
          },
          EXPIRED: {
            icon: 'expired bk-icon icon-clock-shape',
            text: i18n.t('已过期'),
          },
          REVOKE: {
            icon: 'revoke common-icon-dark-stop',
            text: i18n.t('终止'),
          },
          SUSPENDED: {
            icon: 'execute common-icon-dark-circle-pause',
            text: i18n.t('已暂停'),
          },
          RUNNING: {
            icon: 'running common-icon-dark-circle-ellipsis',
            text: i18n.t('执行中'),
          },
          BLOCKED: {
            icon: 'running common-icon-dark-circle-ellipsis',
            text: i18n.t('执行中'),
          },
          READY: {
            icon: 'running common-icon-dark-circle-ellipsis',
            text: i18n.t('排队中'),
          },
          NODE_SUSPENDED: {
            icon: 'execute',
            text: i18n.t('节点暂停'),
          },
        },
      };
    },
    computed: {
      ...mapState({
        isIframe: state => state.isIframe,
        view_mode: state => state.view_mode,
      }),
      ifShowJumpToFlowBtn() {
        return this.$route.query.ifShowJumpToFlowBtn === 'true';
      },
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
      linkToFlow() {
        if (window.parent) {
          window.parent.postMessage({ eventName: 'jump-to-flow' }, '*');
        }
      },
      onViewFatherProcessExecute() {
        const { href } = this.$router.resolve({
            name: 'taskExecute',
            params: {
              spaceId: this.spaceId,
            },
            query: {
              instanceId: this.parentTaskInfo.task_id,
            },
        });
        window.open(href, '_blank');
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '../../../scss/config.scss';
@mixin status-icon-style($color) {
  display: inline-block;
  font-size: 12px;
  color: $color;
  vertical-align: middle;
}
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
            margin-top: -5px;
            float: left;
            .bk-button {
                border: none;
                background: transparent;
                cursor: pointer;
            }
            ::v-deep .bk-icon {
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
            margin-top: 1px;
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
                ::v-deep .bk-button-loading div {
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
                ::v-deep .common-icon-stop {
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
    ::v-deep .bk-button .bk-icon {
        font-size: 14px;
    }
}
.link-icon{
  color: #3a84ff;
  cursor: pointer;
  font-size: 12px;
  margin-left: 8px;
}
.sub-task-btns{
  margin-left: 30px;
  text-align: left;
  .icon-clock-shape {
    @include status-icon-style(#979ba5);
  }
  .common-icon-dark-circle-shape {
    @include status-icon-style(#979ba5);
  }
  .common-icon-dark-circle-ellipsis {
    @include status-icon-style(#3a84ff);
  }
  .icon-check-circle-shape {
    @include status-icon-style(#30d878);
  }
  .common-icon-dark-circle-close {
    @include status-icon-style(#ff5757);
  }
  .common-icon-dark-circle-pause {
    @include status-icon-style(#ff9c01);
  }
  .common-icon-waitting {
    @include status-icon-style(#979ba5);
  }
  .common-icon-dark-stop {
    @include status-icon-style(#ea3636);
  }
  &.revoke {
    color: #878c9c;
  }
  .common-icon-loading {
    display: inline-block;
    vertical-align: middle;
    animation: bk-button-loading 1.4s infinite linear;
  }
  display: flex;
  align-items: center;
  align-content: center;
  font-size: 14px;
  line-height: 22px;
  .icon-link-to-father{
    font-size: 12px !important;
    margin-right: 6px;
    margin-top: 2px;
  }
  .view-father-process{
    cursor: pointer;
  }
  .dividing-line{
    margin: 0 17px;
    border-right: 1px solid #DCDEE5;
    height: 14px;
  }
  span {
    vertical-align: middle; /* 文字也设置垂直居中 */
  }
  .close-icon{
    color: #EA3636;
  }
  .check-icon{
    color: #2dcb56;
  }
  .exclamation-icon{
    color: #ff9c01;
  }
  .state-text{
    margin-left: 5px;
    margin-right: 4px;
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
