<template>
  <div
    v-bkloading="{ isLoading: pageLoading, zIndex: 100 }"
    class="task-execute-detail-page">
    <FlowExecuteBridge
      v-if="!pageLoading"
      :task-id="String(instanceId)"
      :api-config="canvasEditorApiConfig"
      @back="handleBack"
      @view-flow="onViewFlow" />
  </div>
</template>
<script>
  import { mapActions, mapMutations } from 'vuex';
  import { FlowExecuteBridge } from '@blueking/bkflow-canvas-editor-vue2/flow-execute';
  import '@blueking/bkflow-canvas-editor-vue2/style';
  import * as canvasEditorApi from '../../../template/TemplateEdit/flowEditApi';
  import { getCanvasRoute } from '@/utils/canvasRoute.js';

  export default {
    name: 'TaskExecuteDetail',
    components: {
      FlowExecuteBridge,
    },
    props: {
      spaceId: {
        type: [Number, String],
        default: '',
      },
      instanceId: {
        type: [Number, String],
        default: '',
      },
    },
    data() {
      return {
        pageLoading: false,
      };
    },
    computed: {
      canvasEditorApiConfig() {
        return {
          scopeData: {
            scope_type: 'space',
            scope_value: this.spaceId,
          },
          ...canvasEditorApi,
          executeFlowTask: params => canvasEditorApi.executeFlowTask({ task_id: params.task_id, action: 'start' }),
          pauseFlowTask: params => canvasEditorApi.executeFlowTask({ task_id: params.task_id, action: 'pause' }),
          resumeFlowTask: params => canvasEditorApi.executeFlowTask({ task_id: params.task_id, action: 'resume' }),
          // SDK 契约要求 [{ key, value }] 数组；宿主 render_current_constants 返回 { data: { key: value } } 字典，需转换
          fetchTaskGlobalVariables: async (params) => {
            const resp = await canvasEditorApi.fetchTaskGlobalVariables(params);
            const constants = resp?.data ?? {};
            return Object.keys(constants).map(key => ({ key, value: constants[key] }));
          },
          fetchTaskNodeDetail: async (params) => {
            const resp = await canvasEditorApi.fetchTaskNodeDetail(params);
            return resp?.data ?? resp;
          },
          fetchTaskNodeLog: async (params) => {
            const resp = await canvasEditorApi.fetchTaskNodeLog(params);
            return resp?.data ?? resp;
          },
        };
      },
    },
    created() {
      this.setSpaceId(Number(this.spaceId));
      this.setPageTitle();
    },
    methods: {
      ...mapActions('task/', [
        'getTaskInstanceData',
      ]),
      ...mapMutations([
        'setSpaceId',
      ]),
      async setPageTitle() {
        try {
          const data = await this.getTaskInstanceData(this.instanceId);
          if (data?.name) {
            document.title = data.name;
          }
        } catch (e) {
          console.warn(e);
        }
      },
      async onViewFlow({ templateId }) {
        if (!templateId) return;
        const route = await getCanvasRoute(templateId, this.spaceId);
        const { href } = this.$router.resolve(route);
        window.open(href, '_blank');
      },
      handleBack() {
        if (window.history.length > 1) {
          this.$router.back();
        } else {
          this.$router.push({
            name: 'taskList',
            params: { spaceId: this.spaceId },
          });
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .task-execute-detail-page {
    position: relative;
    height: 100%;
    overflow: hidden;
    background: #f4f7fa;
  }
</style>
