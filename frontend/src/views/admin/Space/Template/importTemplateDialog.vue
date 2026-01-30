<template>
  <bk-dialog
    class="import-tpl-dialog"
    width="850"
    header-position="left"
    :mask-close="false"
    :ext-cls="'common-dialog'"
    :title="$t('导入流程')"
    :value="isShow"
    @cancel="onCloseDialog">
    <div class="import-dialog-content">
      <!-- 上传区域 -->
      <div :class="['upload-file-area', `upload-${checkResult}`]">
        <bk-upload
          :key="isShow"
          accept=".json"
          url=""
          :limit="1"
          :tip="$t('仅支持 .json 格式文件')"
          :custom-request="handleUpload"
          @on-delete="handleFileDelete" />
      </div>
    </div>
    <div
      slot="footer"
      class="footer-wrap">
      <div class="operate-area">
        <bk-button
          theme="primary"
          :disabled="checkResult !== 'success'"
          :loading="importPending"
          @click="onConfirm">
          {{ $t("导入") }}
        </bk-button>
        <bk-button @click="onCloseDialog">
          {{ $t("取消") }}
        </bk-button>
      </div>
    </div>
  </bk-dialog>
</template>
<script>
  import { mapActions, mapMutations, mapGetters } from 'vuex';
  import validatePipeline from '@/utils/validatePipeline.js';
  import { generateGraphData } from '@/utils/graphJson.js';

  export default {
    name: 'ImportTplDialog',
    props: {
      isShow: {
        type: Boolean,
        default: false,
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        uploadLoading: false,
        checkResult: '',
        pipelineData: {},
        importPending: false,
      };
    },
    methods: {
      ...mapMutations('template/', [
        'setTemplateData',
      ]),
      ...mapActions('templateList/', [
        'templateUploadCheck',
      ]),
      ...mapActions('template/', [
        'createTemplate',
        'saveTemplateData',
      ]),
      ...mapGetters('template/', [
        'getPipelineTree',
      ]),
      async handleUpload(file) {
        if (this.uploadLoading) return;

        const fileInfo = file.fileObj.origin;
        if (!fileInfo) return;

        this.checkResult = '';
        this.uploadLoading = true;
        try {
          const formData = new FormData();
          formData.append('file', fileInfo);
          const resp = await this.templateUploadCheck(formData);

          if (!resp.result) {
            this.checkResult = 'error';
            return;
          }

          const { pipeline_tree: pipelineTree } = resp.data;
          const pipelineData = {
            ...pipelineTree,
            line: pipelineTree.line || [],
            location: pipelineTree.location || [],
          };
          const validateResult = validatePipeline.isPipelineDataValid(pipelineData);

          this.checkResult = validateResult ? 'success' : 'error';
          this.pipelineData = validateResult ? pipelineData : {};
        } catch (error) {
          console.warn(error);
        } finally {
          this.uploadLoading = false;
        }
      },
      handleFileDelete() {
        this.checkResult = '';
      },
      /**
       * 导入流程
       * 1.先创建新的流程
       * 2.导入的替换新创建的流程
       */
      async onConfirm() {
        try {
          this.importPending = true;

          // 创建新的流程
          const data = {
            spaceId: this.spaceId,
            params: { name: this.pipelineData.name },
          };
          const createResp = await this.createTemplate(data);
          if (!createResp.result) return;

          // 节点排版
          generateGraphData(this.pipelineData);

          // 更新模板
          this.setTemplateData({
            ...createResp.data,
            pipeline_tree: this.getPipelineTree(),
          });

          // 替换新的流程
          const saveResp = await this.saveTemplateData({
            spaceId: this.spaceId,
            templateId: createResp.data.id,
          });

          if (!saveResp.result) return;

          this.$bkMessage({
            message: this.$t('导入成功'),
            theme: 'success',
          });

          this.$router.push({
            name: 'templatePanel',
            params: {
              templateId: createResp.data.id,
              type: 'view',
            },
          });
        } catch (error) {
          console.warn(error);
        } finally {
          this.importPending = false;
        }
      },
      onCloseDialog() {
        this.handleFileDelete();
        this.$emit('update:isShow', false);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .import-dialog-content {
    padding: 20px;
    .upload-file-area {
      width: 530px;
      margin: 120px auto 100px;
      /deep/.file-wrapper {
        background: #fafbfd;
      }
      /deep/.all-file .progress-bar {
        width: 100%;
      }
    }
    .upload-success {
      /deep/.all-file .progress-bar {
        width: 100%;
        background: #2dcb56;
      }
    }
    .upload-error {
      /deep/.all-file .progress-bar {
        width: 100%;
        background: #ff5656;
      }
    }
  }
</style>
