<template>
  <div class="version-list-wrapper">
    <bk-sideslider
      ref="version-list-slider"
      :ext-cls="isSubflowNodeConfig ? 'version-list-panel' : 'version-list-panel template-version-list'"
      :width="800"
      :quick-close="true"
      :is-show="true"
      :title="$t('版本列表')"
      :show-mask="true"
      :before-close="beforeClose">
      <template slot="content">
        <search-select
          id="VersionList"
          ref="searchSelect"
          key="Version"
          v-model="searchValue"
          class="version-search-select"
          :is-show-recently-search="false"
          :placeholder="$t('版本号/版本描述/操作')"
          :search-list="searchList"
          @change="handleSearchValueChange" />
        <bk-table
          :data="pagedVersionList"
          :pagination="pagination"
          :max-height="tableMaxHeight"
          ext-cls="version-table"
          @page-change="handlePageChange"
          @page-limit-change="handlePageLimitChange">
          <bk-table-column
            v-for="field in tableFileds"
            :key="field.id"
            :label="field.label"
            :width="field.width"
            :show-overflow-tooltip="true"
            :prop="field.id"
            :fixed="field.id === 'version' ? 'left' : false ">
            <template slot-scope="{ row }">
              <div
                v-if="field.id === 'version'"
                class="table-version-id">
                <span>{{ row.version || row.desc || '--' }}</span>
                <div
                  v-if="row.isLatestVersion"
                  class="latest-version version-distinguish-icon">
                  <div class="text">
                    {{ $t('最新') }}
                  </div>
                </div>
                <div
                  v-if="row.draft"
                  class="draft-version version-distinguish-icon">
                  <div class="text">
                    {{ $t('草稿') }}
                  </div>
                </div>
              </div>
              <span
                v-else
                class="table-cell">{{ row[field.id] || '--' }}</span>
            </template>
          </bk-table-column>
          <bk-table-column
            label="操作"
            width="220"
            class="version-operation"
            fixed="right">
            <template slot-scope="props">
              <bk-button
                v-if="(props.row.isLatestVersion && !isHaveDraftVersion) || props.row.draft"
                theme="primary"
                class="version-btn"
                text
                :disabled="isSubflowNodeConfig"
                @click="editVersionItem(props.row)">
                {{ $t('编辑') }}
              </bk-button>
              <bk-button
                v-if="!props.row.draft && (!props.row.isLatestVersion || isHaveDraftVersion)"
                theme="primary"
                class="version-btn"
                text
                :disabled="isSubflowNodeConfig"
                @click="rollbackToCurVersion(props.row)">
                {{ $t('恢复到此版本') }}
              </bk-button>
              <bk-button
                theme="primary"
                class="version-btn"
                text
                :disabled="props.row.isLatestVersion || props.row.draft || isSubflowNodeConfig"
                @click="delVersionItem(props.row)">
                <bk-popover
                  :content="$t('最新版本和草稿不能删除')"
                  :disabled="!props.row.isLatestVersion && !props.row.draft">
                  {{ $t('删除') }}
                </bk-popover>
              </bk-button>
            </template>
          </bk-table-column>
        </bk-table>
      </template>
    </bk-sideslider>
    <bk-dialog
      v-model="isShowRollbackDialog"
      theme="primary"
      width="480"
      :mask-close="false"
      footer-position="center"
      @confirm="onRollbackVersionConfirm"
      @cancel="isShowRollbackDialog = false">
      <div class="rollback-dialog-content">
        <div class="title">
          <bk-icon
            type="exclamation"
            class="info-icon dialog-icon" />
          <div class="title-text">
            {{ $t('确定恢复到此版本？') }}
          </div>
        </div>
        <div class="version-text">
          <div>{{ $t('版本名称:') + ' ' + curSelectVersion }}</div>
        </div>
      </div>
      <div>{{ $t('恢复后，会将当前草稿态的内容恢复至选择的版本') }}</div>
    </bk-dialog>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import SearchSelect from '@/components/common/searchSelect/index.vue';
  import { mapActions } from 'vuex';
  export default {
    name: 'VersionList',
    components: {
      SearchSelect,
    },
    props: {
      isShow: {
          type: Boolean,
          default: false,
      },
      isSubflowNodeConfig: {
          type: Boolean,
          default: false,
      },
      subTemplateId: {
          type: [String, Number],
          default: '',
      },
      tplSnapshotId: {
        type: [Number, String],
        default: '',
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        tableFileds: [
            {
                id: 'version',
                label: i18n.t('版本号'),
                width: 200,
            },
            {
                id: 'desc',
                label: i18n.t('版本描述'),
                width: 200,
            },
            {
                id: 'create_time',
                label: i18n.t('创建时间'),
                width: 200,
            },
            {
                id: 'creator',
                label: i18n.t('创建人'),
                width: 150,
            },
            {
                id: 'update_time',
                label: i18n.t('最近更新时间'),
                width: 200,
            },
            {
                id: 'operator',
                label: i18n.t('操作人'),
                width: 150,
            },
        ],
        versionList: [],
        pagination: {
            current: 1,
            count: 0,
            limit: 10,
        },
        searchValue: [],
        searchList: [
          { id: 'version', name: i18n.t('版本号'), isDefaultOption: true },
          { id: 'desc', name: i18n.t('版本描述') },
          { id: 'operator', name: i18n.t('操作人') },
        ],
        isShowRollbackDialog: false,
        curSelectVersion: '',
      };
    },
    computed: {
      pagedVersionList() {
        const { current, limit } = this.pagination;
        const startIndex = (current - 1) * limit;
        const endIndex = startIndex + limit;
        return this.versionList.slice(startIndex, endIndex);
      },
      tableMaxHeight() {
        const maxHeight = window.innerHeight - 200;
        return maxHeight;
      },
      isHaveDraftVersion() {
        return this.versionList.some(item => item.draft);
      },
    },
    mounted() {
      this.getVersionList();
    },
    methods: {
      ...mapActions('template/', [
          'getTemplateVersionSnapshotList',
          'deleteVersionSnapshotData',
          'rollbackToVersion',
      ]),
      escapeRegExp(str) {
          if (typeof str !== 'string') {
          return '';
          }
          return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
      },
      async getVersionList(data = {}) {
        try {
          const { templateId } = this.$route.params;
          const alsoNeedData = {
            template_id: this.isSubflowNodeConfig ? this.subTemplateId : templateId,
            space_id: this.spaceId,
          };
          const requestData = Object.assign(alsoNeedData, data);
          const res = await this.getTemplateVersionSnapshotList(requestData);
          this.versionList = res.results;
          const curJudgeId = this.isSubflowNodeConfig ? this.subTemplateId : this.tplSnapshotId;
          this.versionList.forEach((item) => {
            if (item.id === curJudgeId) {
              item.isLatestVersion = true;
            } else {
              item.isLatestVersion = false;
            }
          });
          this.pagination.count = res.count;
        } catch (error) {
          this.versionList = [];
          this.pagination.count = 0;
        }
      },
      handlePageChange(page) {
        this.pagination.current = page;
      },
      handlePageLimitChange(limit) {
        this.pagination.limit = limit;
        this.pagination.current = 1;
      },
      handleSearchValueChange(data) {
        data = data.reduce((acc, cur) => {
          const value = cur.values[0];
          acc[cur.id] = value;
          return acc;
        }, {});
        this.getVersionList(data);
      },
      editVersionItem(row) {
        // 跳转到编辑态
        this.$router.replace({
          name: 'templatePanel',
          params: { type: 'edit', templateId: this.$route.params.templateId },
          query: Object.assign({ isEditDraft: row.draft }, this.$route.query),
        });
        this.$emit('close', false);
      },
      delVersionItem(row) {
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
              directives: [{
                name: 'bk-overflow-tips',
              }],
            }, [this.$t('确认删除当前版本"{0}"?', [row.version])]),
          ]),
          extCls: 'dialog-custom-header-title',
          maskClose: false,
          width: 450,
          confirmLoading: true,
          cancelText: this.$t('取消'),
          confirmFn: async () => {
            await this.onDeleteVersionConfirm(row.id);
          },
        });
      },
      async onDeleteVersionConfirm(id) {
        await this.deleteVersionSnapshotData({ id, template_id: this.$route.params.templateId, space_id: this.spaceId });
        this.getVersionList();
        this.$emit('refreshVersionList', this.isSubflowNodeConfig);
      },
      async rollbackToCurVersion(row) {
        this.curSelectVersion = row.version;
        this.isShowRollbackDialog = true;
      },
      async onRollbackVersionConfirm() {
        const res = await this.rollbackToVersion({ templateId: this.$route.params.templateId, version: this.curSelectVersion });
        if (!res.result) {
          return;
        }
        this.isShowRollbackDialog = false;
        this.$router.replace({
          name: 'templatePanel',
          params: { type: 'edit', templateId: this.$route.params.templateId },
          query: Object.assign({ isRollVersion: true, isNeedRefreshVersion: true }, this.$route.query),
        });
        this.$emit('close', false);
      },
      beforeClose() {
        this.$emit('close', false);
      },
    },
  };
</script>
<style lang="scss">
.template-version-list{
  background-color: rgba(0, 0, 0, 0.5) !important;
}
.version-list-panel {
    .bk-sideslider-content {
        padding: 20px 30px;
        .search-text-input{
            width: 240px;
            float: right;
            margin-bottom: 15px;
        }
        .table-version-id{
            display: flex;
            align-items: center;
        }
        .version-distinguish-icon{
            font-size: 10px;
            line-height: 16px;
            border-radius: 2px;
            margin-left: 8px;
            .text{
                padding: 0px 4px;
            }
        }
        .latest-version{
          color: #14A568;
          background: #E4FAF0;
          border: 1px solid #A5E0C6;
        }
        .draft-version{
          color: #646469;
          border: 1px solid #dcdee5;
        }
        .version-btn{
            margin-right: 12px;
        }
    }
}
.version-search-select{
  position: relative !important;
  float: right;
  margin-bottom: 15px;
}
.rollback-dialog-content{
    .title{
    display: flex;
    align-items: center;
    flex-direction: column;
    .dialog-icon{
      font-size: 26px !important;
      border-radius: 50%;
      width: 42px;
      height: 42px;
      line-height: 42px;
    }
    .info-icon{
      background-color: #ffe8c3;
      color: #ff9c01;
    }
    .title-text{
      font-size: 20px;
      color: #313238;
      line-height: 32px;
      margin-top: 19px;
      margin-bottom: 16px;

    }
  }
  .version-text{
    padding: 12px 16px;
    background: #F5F6FA;
    border-radius: 2px;
    color: #4D4F56;
    margin-bottom: 13px;
  }
  .bk-dialog-wrapper .bk-dialog-footer {
    padding: 4px 24px 28px 24px;
    border-radius: 2px;
  }
}
</style>
