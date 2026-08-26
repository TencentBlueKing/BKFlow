<template>
  <div class="space-config-center">
    <div class="config-sidebar">
      <bk-input
        v-model="keyword"
        class="config-search"
        :placeholder="$t('搜索配置')"
        right-icon="bk-icon icon-search" />
      <div
        v-bkloading="{ isLoading: listLoading }"
        class="config-groups">
        <bk-collapse
          v-model="activeName"
          class="config-collapse">
          <bk-collapse-item
            v-for="group in filteredGroups"
            :key="group.key"
            :name="group.key">
            {{ group.title }}
            <div slot="content">
              <div
                v-for="item in group.items"
                :key="item.name"
                :class="['group-item', { active: selectedName === item.name }]"
                @click="selectItem(item)">
                <div :class="['item-status', `is-${itemStatus(item)}`]">
                  <div class="item-status-inner" />
                </div>
                <span class="item-label">{{ item.desc }}</span>
              </div>
            </div>
          </bk-collapse-item>
        </bk-collapse>
      </div>
    </div>
    <div class="config-content">
      <ConfigDetail
        :key="selectedName"
        :config="selectedConfig"
        :space-id="spaceId"
        :saving="saving"
        :save-error="!!errorConfigs[selectedName]"
        @save="handleSave"
        @reset="handleReset" />
    </div>
    <!-- 恢复默认配置确认弹窗 -->
    <bk-dialog
      v-model="resetDialogVisible"
      :title="null"
      :width="480"
      :mask-close="false"
      :show-footer="false"
      theme="primary">
      <div class="reset-confirm-dialog">
        <div class="reset-icon-wrap">
          <i class="bk-icon icon-exclamation reset-icon" />
        </div>
        <div class="reset-title">
          {{ $t('确认恢复默认配置？') }}
        </div>
        <div class="reset-desc">
          {{ $t('恢复默认配置后，当前配置的内容将会被清空并重置') }}
        </div>
        <div class="reset-actions">
          <bk-button
            theme="primary"
            :loading="resetLoading"
            @click="confirmReset">
            {{ $t('恢复默认') }}
          </bk-button>
          <bk-button
            theme="default"
            @click="resetDialogVisible = false">
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </bk-dialog>
  </div>
</template>
<script>
  import { mapActions } from 'vuex';
  import { bkCollapse, bkCollapseItem } from 'bk-magic-vue';
  import ConfigDetail from './ConfigDetail.vue';
  import i18n from '@/config/i18n/index.js';
  // 配置项分组
  const GROUP_DEFS = [
    { key: 'access_security', title: i18n.t('权限与安全') }, // superusers、token_expiration、token_auto_renewal、api_gateway_credential_name
    { key: 'flow_canvas', title: i18n.t('流程与画布行为') }, // flow_versioning、allow_multiple_triggers、gateway_expression、canvas_mode
    { key: 'api_integration', title: i18n.t('API 与插件集成') }, // uniform_api、space_plugin_config、engine_space_config
    { key: 'other', title: i18n.t('未分类') },
  ];

  export default {
    name: 'SpaceConfigCenter',
    components: { ConfigDetail, bkCollapse, bkCollapseItem },
    props: {
      spaceId: { type: [String, Number], default: '' },
      hasAlertNotice: { type: Boolean, default: false },
    },
    data() {
      return {
        listLoading: false,
        saving: false,
        configList: [],
        selectedName: '',
        keyword: '',
        // 验证失败（异常）的配置项，name -> error，用于侧边栏红色状态
        errorConfigs: {},
        // 折叠面板展开项，默认全部展开
        activeName: ['access_security', 'flow_canvas', 'api_integration', 'other'],
        resetDialogVisible: false,
        resetLoading: false,
        pendingResetRow: null,
      };
    },
    computed: {
      publicList() {
        return this.configList;
      },
      filteredGroups() {
        const searchKeyword = this.keyword.trim().toLowerCase();
        // 前三组为具体分组，最后"未分类"兜底
        const specificKeys = GROUP_DEFS.slice(0, -1).map(g => g.key);
        const groupedList = GROUP_DEFS.map((groupDef) => {
          const items = this.publicList.filter((item) => {
            const groupKey = item.group || 'other';
            if (groupDef.key !== 'other') {
              // 具体分组：精确匹配
              if (groupKey !== groupDef.key) return false;
            } else {
              // 未分类分组：兜底所有不在前三组的项（包括没有 group 字段的）
              if (specificKeys.includes(groupKey)) return false;
            }
            if (!searchKeyword) return true;
            const label = (
              (item.ui && item.ui.label)
              || item.desc
              || item.name
            ).toLowerCase();
            return label.includes(searchKeyword)
              || item.name.toLowerCase().includes(searchKeyword);
          });
          return { ...groupDef, items };
        }).filter(groupDef => groupDef.items.length > 0);
        return groupedList;
      },
      selectedConfig() {
        return this.publicList.find(item => item.name === this.selectedName) || null;
      },
    },
    watch: {
      spaceId: {
        handler() {
          this.loadConfigs();
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'getSpaceConfigData',
        'updateSpaceConfig',
        'deleteSpaceConfig',
        'getSpaceConfigMeta',
      ]),
      async loadConfigs() {
        if (!this.spaceId) return;
        try {
          this.listLoading = true;
          const [dataResp, metaResp] = await Promise.all([
            this.getSpaceConfigData({ space_id: this.spaceId }),
            this.getSpaceConfigMeta({ space_id: this.spaceId }),
          ]);
          const stored = dataResp.data || [];
          this.configList = Object.values(metaResp.data).map((meta) => {
            const existingItem = stored.find(item => item.name === meta.name);
            if (existingItem) {
              return {
                ...meta,
                ...existingItem,
                isDefault: false,
              };
            }
            return {
              ...meta,
              value: meta.default_value,
              json_value: meta.default_value,
              isDefault: true,
            };
          });
          if (!this.selectedName && this.filteredGroups.length) {
            this.selectedName = this.filteredGroups[0].items[0].name;
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      selectItem(item) {
        if (this.selectedName && this.errorConfigs[this.selectedName]) {
          this.$delete(this.errorConfigs, this.selectedName);
        }
        this.selectedName = item.name;
      },
      itemStatus(item) {
        if (!item) return 'default';
        if (this.errorConfigs[item.name]) return 'error';
        return item.isDefault ? 'default' : 'configured';
      },
      async handleSave(payload) {
        try {
          this.saving = true;
          const resp = await this.updateSpaceConfig(payload);
          if (resp.result === false) {
            this.$set(this.errorConfigs, this.selectedName, true);
            return;
          }
          this.$delete(this.errorConfigs, this.selectedName);
          this.$bkMessage({
            message: this.$t('修改成功！'),
            theme: 'success',
          });
          this.loadConfigs();
        } catch (error) {
          console.warn(error);
          this.$set(this.errorConfigs, this.selectedName, true);
        } finally {
          this.saving = false;
        }
      },
      handleReset(row) {
        this.pendingResetRow = row;
        this.resetDialogVisible = true;
      },
      async confirmReset() {
        if (!this.pendingResetRow) return;
        try {
          this.resetLoading = true;
          const resp = await this.deleteSpaceConfig({ id: this.pendingResetRow.id });
          if (resp.result === false) return;
          this.$delete(this.errorConfigs, this.pendingResetRow.name);
          this.$bkMessage({
            message: this.$t('已恢复默认值'),
            theme: 'success',
          });
          this.resetDialogVisible = false;
          this.loadConfigs();
        } catch (error) {
          console.warn(error);
        } finally {
          this.resetLoading = false;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .space-config-center {
    display: flex;
    background: #fff;
    max-height: calc(100vh - 145px);
  }
  .config-sidebar {
    width: 240px;
    border-right: 1px solid #dcdee5;
    display: flex;
    flex-direction: column;
    .config-search {
      margin: 16px 16px 0 16px;
      width: 208px;
    }
    .config-groups {
      flex: 1;
      overflow-y: auto;
      margin-bottom: 16px;
    }
    .config-collapse {
      border: none;
      ::v-deep .bk-collapse-item {
        margin-top: 16px;
        .bk-collapse-item-header {
          padding: 0 16px;
          height: 20px;
          line-height: 20px;
          font-size: 12px;
          color: #979ba5;
          margin-bottom: 8px;
          .bk-collapse-item-header-icon {
            font-size: 14px;
          }
        }
        .bk-collapse-item-content {
          padding: 0;
        }
      }
    }
    .group-item {
      display: flex;
      align-items: center;
      padding: 8px 16px;
      cursor: pointer;
      &:hover {
        background: #f5f7fa;
      }
      &.active {
        background: #e1ecff;
        color: #3a84ff;
        .item-label {
          color: #3a84ff;
        }
      }
      .item-status {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
        margin-right: 10px;
        &.is-configured {
          background: #e5f5eb;
          .item-status-inner { background: #2caf5e; }
        }
        &.is-default {
          background: #f3f4f5;
          .item-status-inner { background: #c4c6cc; }
        }
        &.is-error {
          background: #fce6e6;
          .item-status-inner { background: #ea3636; }
        }
      }
      .item-status-inner {
        width: 5px;
        height: 5px;
        border-radius: 50%;
      }
      .item-label {
        flex: 1;
        font-size: 12px;
        color: #4d4f56;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .item-tag {
        flex-shrink: 0;
        margin-left: 8px;
        font-size: 12px;
        transform: scale(0.9);
        transform-origin: right center;
        &.is-configured {
          color: #14a568;
        }
        &.is-default {
          color: #979ba5;
        }
        &.is-error {
          color: #ea3636;
        }
      }
    }
  }
  .config-content {
    flex: 1;
    overflow-y: auto;
  }
  // 恢复默认配置确认弹窗样式
  .reset-confirm-dialog {
    text-align: center;
    padding: 0 8px;
    .reset-icon-wrap {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: #fff3e0;
      margin-bottom: 16px;
    }
    .reset-icon {
      font-size: 32px;
      color: #ff9800;
    }
    .reset-title {
      font-size: 20px;
      color: #313238;
      line-height: 28px;
      margin-bottom: 16px;
    }
    .reset-desc {
      font-size: 14px;
      color: #4d4f56;
      line-height: 22px;
      background: #f5f7fa;
      padding: 12px 16px;
      margin-bottom: 24px;
      text-align: left;
    }
    .reset-actions {
      display: flex;
      justify-content: center;
      gap: 8px;
      .bk-button {
        min-width: 96px;
      }
    }
  }
</style>
