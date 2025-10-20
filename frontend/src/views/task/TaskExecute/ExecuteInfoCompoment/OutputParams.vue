<template>
  <section
    class="info-section outputs-section"
    data-test-id="taskExecute_form_outputParams">
    <h4 class="common-section-title">
      {{ $t('输出参数') }}
    </h4>
    <div
      v-if="isReadyStatus && !adminView"
      class="origin-value">
      <bk-switcher
        v-model="isShowOutputOrigin"
        size="small"
        @change="outputSwitcher" />
      {{ 'Code' }}
    </div>
    <NoData
      v-if="!isReadyStatus"
      :message="$t('暂无输出')" />
    <template v-else-if="!adminView">
      <table
        v-if="!isShowOutputOrigin"
        class="operation-table outputs-table">
        <thead>
          <tr>
            <th class="output-name">
              {{ $t('参数名') }}
            </th>
            <th class="output-key">
              {{ $t('参数Key') }}
            </th>
            <th class="output-value">
              {{ $t('参数值') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(output, index) in outputsInfo"
            :key="index">
            <td class="output-name">
              {{ getOutputName(output) }}
            </td>
            <td class="output-key">
              {{ output.key }}
            </td>
            <td
              v-if="typeof output.value === 'object'"
              v-bk-overflow-tips
              class="output-value">
              <full-code-editor
                :value="JSON.stringify(output.value, null, 4)" />
            </td>
            <td
              v-else
              class="output-value">
              {{ output.value }}
            </td>
          </tr>
          <tr v-if="Object.keys(outputsInfo).length === 0">
            <td colspan="3">
              <no-data />
            </td>
          </tr>
        </tbody>
      </table>
      <full-code-editor
        v-else
        :value="outputsInfo" />
    </template>
    <div
      v-else
      class="code-block-wrap">
      <VueJsonPretty
        v-if="outputsInfo"
        :data="outputsInfo" />
      <NoData v-else />
    </div>
  </section>
</template>

<script>
  import VueJsonPretty from 'vue-json-pretty';
  import NoData from '@/components/common/base/NoData.vue';
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';
  import tools from '@/utils/tools.js';
  export default {
    components: {
      VueJsonPretty,
      NoData,
      FullCodeEditor,
    },
    props: {
      adminView: {
        type: Boolean,
        default: false,
      },
      outputs: {
        type: Array,
        default: () => ([]),
      },
      nodeDetailConfig: {
        type: Object,
        default: () => ({}),
      },
      isReadyStatus: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        isShowOutputOrigin: false,
        outputsInfo: null,
      };
    },
    watch: {
      outputs: {
        handler(val) {
          this.outputsInfo = tools.deepClone(val);
        },
        immediate: true,
      },
    },
    methods: {
      outputSwitcher() {
        if (!this.isShowOutputOrigin) {
          this.outputsInfo = JSON.parse(this.outputsInfo);
        } else {
          this.outputsInfo = JSON.stringify(this.outputsInfo, null, 4);
        }
      },
      getOutputName(output) {
        if (this.nodeDetailConfig.component_code === 'job_execute_task' && output.perset) {
          return output.key;
        }
        return output.name;
      },
    },
  };
</script>

<style lang="scss" scoped>
    .outputs-section .operation-table {
        flex: 1;
        table-layout: fixed;
        th, td {
            width: 30%;
            padding: 16px 13px;
            font-weight: normal;
            color: #313238;
            background: #f5f7fa;
            border: none;
            border-bottom: 1px solid #dcdee5;
        }
        td {
            color: #63656e;
            background: #fff;
        }
        .output-value {
            width: 50%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            word-break: break-all;
        }
    }
    .outputs-section .full-code-editor {
        height: 400px;
    }
    .no-data-wrapper {
        margin-top: 32px;
    }
</style>
