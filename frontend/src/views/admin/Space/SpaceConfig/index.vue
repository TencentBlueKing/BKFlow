<template>
  <div
    v-bkloading="{ isLoading: listLoading }"
    class="space-config-page">
    <div
      v-if="spaceConfigList.length"
      class="space-config-form">
      <div class="space-config-header">
        <bk-button
          theme="primary"
          :loading="saving"
          :disabled="!hasAnyChange"
          @click="handleGlobalSave">
          {{ $t('保存') }}
        </bk-button>
        <bk-button
          :disabled="!hasAnyNonDefault || saving"
          @click="handleGlobalRestore">
          {{ $t('恢复默认值') }}
        </bk-button>
      </div>
      <div class="space-config-body">
        <SpaceConfigItem
          v-for="item in spaceConfigList"
          ref="configItems"
          :key="item.name"
          :config-item="item"
          :space-id="spaceId"
          @change="onItemChange(item.name, $event)" />
      </div>
    </div>
    <NoData
      v-else-if="!listLoading"
      type="empty" />
  </div>
</template>
<script>
  import NoData from '@/components/common/base/NoData.vue';
  import SpaceConfigItem from './SpaceConfigItem.vue';
  import { mapActions } from 'vuex';

  export default {
    name: 'SpaceConfigList',
    components: {
      NoData,
      SpaceConfigItem,
    },
    props: {
      spaceId: {
        type: [String, Number],
        default: '',
      },
      hasAlertNotice: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        listLoading: false,
        spaceConfigList: [],
        saving: false,
        changedSet: new Set(),
      };
    },
    computed: {
      hasAnyChange() {
        return this.changedSet.size > 0;
      },
      hasAnyNonDefault() {
        return this.spaceConfigList.some(item => !item.isDefault);
      },
    },
    watch: {
      spaceId: {
        handler() {
          this.getSpaceConfigList();
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'getSpaceConfigData',
        'getSpaceConfigMeta',
        'updateSpaceConfig',
        'deleteSpaceConfig',
        'batchDeleteSpaceConfig',
        'batchApplySpaceConfig',
      ]),
      onItemChange(name, isChanged) {
        if (isChanged) {
          this.changedSet.add(name);
        } else {
          this.changedSet.delete(name);
        }
        // 触发响应式更新
        this.changedSet = new Set(this.changedSet);
      },
      // 空间配置列表
      async getSpaceConfigList() {
        if (!this.spaceId) return;
        try {
          this.listLoading = true;
          const [resp1, resp2] = await Promise.all([
            this.getSpaceConfigData({ space_id: this.spaceId }),
            this.getSpaceConfigMeta({ space_id: this.spaceId }),
          ]);
          const list = Object.values(resp2.data).reduce((acc, cur) => {
            const configData = resp1.data.find(item => item.name === cur.name);
            if (configData) {
              const { value_type: type, value, json_value: jsonValue } = configData;
              const valueText = type === 'TEXT' ? value : JSON.stringify(jsonValue);
              acc.push({
                ...cur,
                ...configData,
                valueText,
              });
            } else {
              acc.push({
                ...cur,
                valueText: cur.default_value,
                isDefault: true,
              });
            }
            return acc;
          }, []);
          list.sort((a, b) => {
            let result = a.isDefault ? 1 : -1;
            result = a.isDefault === b.isDefault ? 0 : result;
            return result;
          });
          this.spaceConfigList = list;
          this.changedSet = new Set();
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      async handleGlobalSave() {
        const items = this.$refs.configItems || [];
        // 校验所有配置项
        const invalidItems = [];
        items.forEach((comp) => {
          const validation = comp.validate();
          if (!validation.valid) {
            invalidItems.push(validation.desc);
          }
        });
        if (invalidItems.length) {
          this.$bkMessage({
            message: `${this.$t('以下配置项数据格式不正确,应为JSON格式:')}${invalidItems.join('、')}`,
            theme: 'error',
            ellipsisLine: 2,
            ellipsisCopy: true,
          });
          return;
        }
        // 只收集有变更的配置项，避免将未修改的配置（如含占位符的默认值）提交给后端
        const configs = {};
        items.forEach((comp) => {
          const data = comp.getChangedData();
          if (!data) return; // 未变更，跳过
          const value = data.json_value !== undefined ? data.json_value : data.text_value;
          if (value === '' || value === null || value === undefined) return;
          configs[data.name] = value;
        });
        if (!Object.keys(configs).length) return;
        try {
          this.saving = true;
          const resp = await this.batchApplySpaceConfig({
            space_id: this.spaceId,
            configs,
          });
          if (resp.result === false) return;
          this.$bkMessage({
            message: this.$t('保存成功！'),
            theme: 'success',
          });
          await this.getSpaceConfigList();
        } catch (error) {
          console.warn(error);
        } finally {
          this.saving = false;
        }
      },
      handleGlobalRestore() {
        const nonDefaultItems = this.spaceConfigList.filter(item => !item.isDefault && item.id);
        if (!nonDefaultItems.length) return;
        const h = this.$createElement;
        this.$bkInfo({
          subHeader: h('div', { class: 'custom-header' }, [
            h('div', {
              class: 'custom-header-title',
            }, [this.$t('确认将所有配置项恢复为默认值？')]),
          ]),
          extCls: 'dialog-custom-header-title',
          maskClose: false,
          width: 400,
          confirmLoading: true,
          cancelText: this.$t('取消'),
          confirmFn: async () => {
            try {
              const ids = nonDefaultItems.map(item => item.id);
              const resp = await this.batchDeleteSpaceConfig({
                space_id: this.spaceId,
                ids,
              });
              if (resp.result === false) return;
              this.$bkMessage({
                message: this.$t('恢复默认值成功！'),
                theme: 'success',
              });
              await this.getSpaceConfigList();
            } catch (error) {
              console.warn(error);
            }
          },
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
@import '@/scss/mixins/scrollbar.scss';
  .space-config-page {
    min-height: 200px;
    padding: 0 24px 24px;
    .space-config-form {
      .space-config-header {
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 8px;
        margin-bottom: 15px;
      }
      .space-config-body {
        max-height: calc(-160px + 100vh);
        overflow-y: auto;
        @include scrollbar;
        padding: 8px 0;
        background: #fff;
        border-radius: 2px;
        box-shadow: 0 2px 6px 0 rgba(0, 0, 0, 0.1);
      }
    }
  }
</style>
