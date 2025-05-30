<template>
  <div class="execute-record">
    <template v-if="Object.keys(executeInfo).length">
      <section
        class="info-section abnormal-section"
        data-test-id="taskExcute_form_exceptionInfo">
        <h4 class="common-section-title">
          {{ $t('异常信息') }}
        </h4>
        <div
          v-if="executeInfo.ex_data"
          class="fail-text">
          <p
            class="hide-html-text"
            v-html="executeInfo.failInfo" />
          <div
            class="show-html-text"
            :class="{ 'is-fold': !isExpand }"
            v-html="executeInfo.failInfo" />
          <span
            v-if="isExpandTextShow"
            class="expand-btn"
            @click="isExpand = !isExpand">
            {{ isExpand ? $t('收起') : $t('显示全部') }}
          </span>
        </div>
        <p
          v-else
          class="not-fail">
          {{ $t('暂无异常') }}
        </p>
      </section>
      <section
        class="info-section"
        data-test-id="taskExcute_form_excuteInfo">
        <h4 class="common-section-title">
          {{ $t('执行信息') }}
        </h4>
        <div
          v-if="isReadyStatus && isSubProcessNode"
          class="subprocee-link"
          @click="onSkipSubProcess">
          <i class="common-icon-box-top-right-corner" />
          {{ $t('子流程详情') }}
        </div>
        <ul
          v-if="isReadyStatus"
          class="operation-table">
          <li>
            <span class="th">{{ $t('开始时间') }}</span>
            <span class="td">{{ executeInfo.start_time || '--' }}</span>
          </li>
          <li>
            <span class="th">{{ $t('结束时间') }}</span>
            <span class="td">{{ executeInfo.finish_time || '--' }}</span>
          </li>
          <li>
            <span class="th">{{ $t('耗时') }}</span>
            <span class="td">{{ getLastTime(executeInfo.elapsed_time) || '--' }}</span>
          </li>
        </ul>
        <NoData
          v-else
          :message="$t('暂无执行信息')" />
      </section>
      <!-- 任务节点才允许展示输入、输出配置 -->
      <template v-if="['tasknode', 'subflow'].includes(location.type)">
        <InputParams
          :admin-view="adminView"
          :inputs="executeInfo.inputs"
          :render-config="executeInfo.renderConfig"
          :constants="constants"
          :render-data="executeInfo.renderData"
          :plugin-code="pluginCode"
          :space-id="spaceId"
          :template-id="templateId"
          @updateOutputs="$emit('updateOutputs', $event)" />
        <OutputParams
          :is-ready-status="isReadyStatus"
          :admin-view="adminView"
          :outputs="executeInfo.outputsInfo"
          :node-detail-config="nodeDetailConfig" />
      </template>
    </template>
    <NoData
      v-else
      :message="$t('暂无执行信息')" />
  </div>
</template>

<script>
  import tools from '@/utils/tools.js';
  import InputParams from './InputParams.vue';
  import OutputParams from './OutputParams.vue';
  import NoData from '@/components/common/base/NoData.vue';
  export default {
    name: 'ExecuteRecord',
    components: {
      InputParams,
      OutputParams,
      NoData,
    },
    props: {
      adminView: {
        type: Boolean,
        default: false,
      },
      loading: {
        type: Boolean,
        default: false,
      },
      location: {
        type: Object,
        default: () => ({}),
      },
      isReadyStatus: {
        type: Boolean,
        default: false,
      },
      executeInfo: {
        type: Object,
        default: () => ({}),
      },
      nodeDetailConfig: {
        type: Object,
        default: () => ({}),
      },
      isSubProcessNode: {
        type: Boolean,
        default: false,
      },
      pluginCode: {
        type: String,
        default: '',
      },
      spaceId: {
        type: Number,
        default: 0,
      },
      templateId: {
        type: [Number, String],
        default: '',
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        isExpand: false,
        isExpandTextShow: false,
      };
    },
    mounted() {
      const showDom = document.querySelector('.show-html-text');
      const hideDom = document.querySelector('.hide-html-text');
      if (showDom && hideDom) {
        const showDomHeight = showDom.getBoundingClientRect().height;
        const hideDomHeight = hideDom.getBoundingClientRect().height;
        this.isExpandTextShow = hideDomHeight > showDomHeight;
      }
    },
    methods: {
      getLastTime(time) {
        return tools.timeTransform(time);
      },
      onSkipSubProcess() {
        const taskInfo = this.executeInfo.outputsInfo.find(item => item.key === 'task_url');
        if (taskInfo) {
          window.open(taskInfo.value, '_blank');
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
.execute-record {
    ::v-deep .fail-text {
        position: relative;
        font-size: 12px;
        padding: 8px 16px;
        color: #313238;
        background: #fff3e1;
        border: 1px solid #ffb848;
        border-radius: 2px;
        word-break: break-all;
        .hide-html-text {
            position: absolute;
            z-index: -1;
        }
        .is-fold {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: normal;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 10;
        }
        .expand-btn {
            position: absolute;
            right: 16px;
            bottom: 8px;
            padding: 5px 0 0 5px;
            color: #3a84ff;
            background: #fff3e1;
            cursor: pointer;
        }
        a {
            color: #3a84ff;
        }
    }
    .not-fail {
        color: #979ba5;
        font-size: 12px;
        padding-left: 15px;
    }
    .operation-table {
        font-size: 12px;
        border: 1px solid #dcdee5;
        border-bottom: none;
        li {
            display: flex;
            height: 42px;
            line-height: 41px;
            color: #63656e;
            border-bottom: 1px solid #dcdee5;
            .th {
                width: 140px;
                font-weight: 400;
                color: #313238;
                padding-left: 12px;
                border-right: 1px solid #dcdee5;
                background: #fafbfd;
            }
            .td {
                padding-left: 12px;
            }
        }
    }
    .info-section {
        position: relative;
        .subprocee-link {
            display: flex;
            align-items: center;
            position: absolute;
            right: 0;
            top: 0;
            font-size: 12px;
            color: #3a84ff;
            cursor: pointer;
            i {
                margin-right: 6px;
            }
        }
    }
    ::v-deep .input-section,
    ::v-deep .outputs-section {
        font-size: 12px;
        .origin-value {
            position: absolute;
            top: 0;
            right: 0;
            display: flex;
            align-items: center;
            font-size: 12px;
            color: #63656e;
            .bk-switcher {
                top: 1px;
                margin-right: 8px;
            }
        }
    }
    .full-code-editor {
        flex: 1;
        margin: 20px 0 0 48px;
    }
    ::v-deep .no-data-wrapper {
        .no-data-wording {
            font-size: 12px;
            color: #63656e;
        }
    }
    ::v-deep .exception-part {
        margin-top: 20px;
        .part-text {
            font-size: 12px;
            color: #979ba5;
        }
    }
    .ex-data-wrap {
        ::v-deep pre {
            white-space: pre-wrap;
        }
    }
    .perform-log {
        width: 100%;
    }
    .info-section:not(:last-child) {
        margin-bottom: 32px;
    }
    .no-data-wrapper {
        margin-top: 32px;
    }
}
</style>
