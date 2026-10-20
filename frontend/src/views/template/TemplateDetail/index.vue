<template>
  <div
    v-bkloading="{ isLoading: templateDataLoading, zIndex: 100 }"
    class="template-detail-page">
    <FlowDetailBridge
      v-if="!templateDataLoading && permissions"
      ref="flowDetailRef"
      :flow-id="String(templateId)"
      :api-config="tplCanvasEditorApiConfig"
      :permissions="permissions"
      :enable-version-management="isEnableVersionManage"
      :flow-version="compVersion"
      :on-execute-success="onFlowExecuteSuccess"
      @update:flow-version="compVersion = $event"
      @back="handleBack" />
  </div>
</template>
<script>
  import { mapActions, mapMutations } from 'vuex';
  import { FlowDetailBridge } from '@blueking/bkflow-canvas-editor-vue2/flow-detail';
  import '@blueking/bkflow-canvas-editor-vue2/style';
  import * as canvasEditorApi from '../TemplateEdit/flowEditApi';

  export default {
    name: 'TemplateDetail',
    components: {
      FlowDetailBridge,
    },
    props: {
      templateId: {
        type: [Number, String],
        default: '',
      },
    },
    data() {
      return {
        templateDataLoading: false,
        isEnableVersionManage: false,
        compVersion: '', // 空串表示草稿态（可编辑）
        permissions: null, // 加载完成后由模板 auth 推导
        spaceId: '',
      };
    },
    computed: {
      tplCanvasEditorApiConfig() {
        return {
          scopeData: {
            scope_type: 'space',
            scope_value: this.spaceId,
          },
          ...canvasEditorApi,
          // 覆盖 executeFlowTask：不启动任务，直接返回成功
          executeFlowTask: async () => ({ result: true, data: {} }),
        };
      },
    },
    created() {
      this.initData();
    },
    methods: {
      ...mapActions('template/', [
        'loadTemplateData',
        'getTemplateVersionSnapshotList',
      ]),
      ...mapActions('spaceConfig/', [
        'getNotAuthSpaceConfig',
        'checkSpaceConfig',
      ]),
      ...mapMutations([
        'setSpaceId',
      ]),
      async initData() {
        this.templateDataLoading = true;
        try {
          const templateData = await this.loadTemplateData({
            templateId: this.templateId,
            common: this.$route.query.common,
          });
          this.spaceId = templateData.space_id;
          this.setSpaceId(templateData.space_id);
          await this.checkoutSpace(templateData.space_id);
          const actions = templateData.auth || [];
          this.permissions = {
            canEdit: actions.includes('EDIT'),
            canExecute: actions.includes('EXECUTE'),
            canDebug: actions.includes('MOCK'),
          };
          // - 未开版本管理、开启且有草稿 → 草稿态
          // - 开启且无草稿 → 最新已发布版本只读态（点编辑/修改才产生草稿）
          if (!this.isEnableVersionManage) {
            this.compVersion = '';
          } else {
            const res = await this.getTemplateVersionSnapshotList({
              template_id: this.templateId,
              space_id: this.spaceId,
            });
            const isHaveDraft = res.data.results?.some(item => item.draft) ?? false;
            this.compVersion = isHaveDraft ? '' : templateData.version;
          }
        } catch (e) {
            console.error(e);
        } finally {
          this.templateDataLoading = false;
        }
      },
      // 判断是否开启版本管理
      async checkoutSpace(spaceId) {
        try {
          const res = await this.getNotAuthSpaceConfig();
          if (!res.data.flow_versioning || !spaceId) {
            this.isEnableVersionManage = false;
            return;
          }
          const { name } = res.data.flow_versioning;
          const result = await this.checkSpaceConfig({ id: spaceId, name });
          this.isEnableVersionManage = result.data.value === 'true';
        } catch (error) {
          this.isEnableVersionManage = false;
        }
      },
      // SDK 执行流程成功回调
      onFlowExecuteSuccess({ createResult, executeResult }) {
        const executeUrl = executeResult?.data?.url;
        if (executeUrl) {
          window.open(executeUrl, '_blank');
          return;
        }
        const taskId = createResult?.data?.id;
        if (!taskId) {
          return;
        }
        const { href } = this.$router.resolve({
          name: 'taskExecute',
          params: { spaceId: this.spaceId },
          query: { instanceId: taskId },
        });
        window.open(href, '_blank');
      },
      handleBack() {
        if (window.history.length > 1) {
          this.$router.back();
        } else {
          this.$router.push({
            name: 'spaceAdmin',
            query: {
              space_id: this.spaceId,
              activeTab: 'template',
            },
          });
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .template-detail-page {
    position: relative;
    height: 100%;
    overflow: hidden;
  }
</style>
