<template>
  <div class="plugin-scope">
    <template v-if="!isDeprecatedConfig">
      <bk-radio-group
        v-model="mode"
        class="ps-mode"
        @change="emitValue">
        <bk-radio
          value="allow_all"
          class="ps-radio">
          {{ $t('不过滤(默认)：画布展示空间内全部可用插件') }}
        </bk-radio>
        <bk-radio
          value="allow_list"
          class="ps-radio">
          {{ $t('仅显示名单中的插件：面板只留所选插件；未列入的标准插件、以及未列入的 API / 第三方入口都会消失') }}
        </bk-radio>
        <bk-radio
          value="deny_list"
          class="ps-radio">
          {{ $t('隐藏名单中的插件：只从面板拿掉所选标准插件，其余（含 API 插件）仍可见。已有流程更安全') }}
        </bk-radio>
      </bk-radio-group>
      <div
        v-show="mode !== 'allow_all'"
        class="ps-select-title">
        {{ $t('插件') }}
      </div>
      <bk-select
        v-show="mode !== 'allow_all'"
        v-model="pluginCodes"
        multiple
        searchable
        display-tag
        :loading="loading"
        :placeholder="$t('请选择插件')"
        class="ps-select"
        @change="emitValue">
        <bk-option
          v-for="plugin in candidates"
          :id="plugin.id"
          :key="plugin.id"
          :name="plugin.name" />
      </bk-select>
    </template>
    <template v-else>
      <div class="ps-banner">
        <i class="bk-icon icon-info-circle-shape ps-banner-icon" />
        <div class="ps-banner-content">
          <p class="ps-banner-title">
            {{ $t('本配置已停止生效') }}
          </p>
          <p class="ps-banner-desc">
            {{ $t('本空间已于 {time} 启用插件目录，插件的可见、隐藏、下架与分类改在「插件管理」中维护。', { time: migratedAt }) }}
          </p>
        </div>
        <bk-button
          theme="primary"
          size="small"
          class="ps-banner-btn"
          @click="goPluginManage">
          {{ $t('前往插件管理') }}
        </bk-button>
      </div>
      <div class="ps-legacy">
        <p class="ps-legacy-title">
          {{ $t('迁移前的配置 (只读)') }}
        </p>
        <div class="ps-kv">
          <div class="ps-kv-row">
            <div class="ps-kv-label">
              {{ $t('过滤方式') }}
            </div>
            <div class="ps-kv-value">
              {{ legacySnapshot.filter_mode_text || modeLabel }}
            </div>
          </div>
          <div class="ps-kv-row">
            <div class="ps-kv-label">
              {{ $t('插件') }}
            </div>
            <div class="ps-kv-value is-wrap">
              <template v-if="legacySnapshot.plugins && legacySnapshot.plugins.length">
                <span
                  v-for="item in legacySnapshot.plugins"
                  :key="item.code"
                  class="ps-tag">{{ item.name }}</span>
              </template>
              <span
                v-else
                class="ps-kv-empty">--</span>
            </div>
          </div>
          <div class="ps-kv-row">
            <div class="ps-kv-label">
              {{ $t('按 scope 覆盖') }}
            </div>
            <div class="ps-kv-value is-wrap">
              <template v-if="legacySnapshot.scope_overrides && legacySnapshot.scope_overrides.length">
                <span
                  v-for="item in legacySnapshot.scope_overrides"
                  :key="item.scope"
                  class="ps-tag is-scope">{{ item.scope }}</span>
              </template>
              <span
                v-else
                class="ps-kv-empty">--</span>
            </div>
          </div>
          <div class="ps-kv-row">
            <div class="ps-kv-label">
              {{ $t('快照') }}
            </div>
            <div class="ps-kv-value is-multiline">
              {{ snapshotText }}
            </div>
          </div>
        </div>
        <!-- <div class="ps-warn">
          <bk-icon
            type="exclamation-circle"
            class="ps-warn-icon" />
          <span class="ps-warn-text">
            {{ $t('接入系统通过网关 create_space / renew_space_config 写入本配置时会返回错误，请改用插件目录接口。') }}
          </span>
        </div> -->
      </div>
    </template>
  </div>
</template>
<script>
  import { mapActions } from 'vuex';

  export default {
    name: 'PluginScope',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [Object, String],
        default: () => ({}),
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      config: {
        type: Object,
        default: () => ({}),
      },
      isDeprecatedConfig: {
        type: Boolean,
        default: false,
      },
      migrationInfo: {
        type: Object,
        default: null,
      },
    },
    data() {
      return {
        mode: 'allow_all',
        pluginCodes: [],
        candidates: [],
        loading: false,
      };
    },
    computed: {
      migratedAt() {
        return (this.migrationInfo && this.migrationInfo.migrated_at) || '--';
      },
      legacySnapshot() {
        const snapshot = (this.migrationInfo && this.migrationInfo.legacy_snapshot) || {};
        return {
          filter_mode_text: snapshot.filter_mode_text || '',
          plugins: Array.isArray(snapshot.plugins) ? snapshot.plugins : [],
          scope_overrides: Array.isArray(snapshot.scope_overrides) ? snapshot.scope_overrides : [],
          snapshot_note: snapshot.snapshot_note || '',
        };
      },
      snapshotText() {
        if (!this.migrationInfo) return '--';
        return `${this.migrationInfo.migrated_by || '--'} ${this.$t('于')} ${this.migratedAt} ${this.legacySnapshot.snapshot_note}`;
      },
      modeLabel() {
        const map = {
          allow_all: this.$t('不过滤（空间内全部可用插件）'),
          allow_list: this.$t('仅显示名单中的插件'),
          deny_list: this.$t('隐藏名单中的插件'),
        };
        return map[this.mode] || this.$t('未配置');
      },
      pluginNames() {
        if (!Array.isArray(this.pluginCodes)) return [];
        return this.pluginCodes.map((code) => {
          const matched = this.candidates.find(item => item.id === code);
          return matched ? matched.name : code;
        });
      },
    },
    watch: {
      value: {
        handler(newValue) {
          if (this.isDeprecatedConfig) return;
          this.parseValue(newValue);
        },
        immediate: true,
      },
      spaceId: {
        handler() {
          this.loadCandidates();
        },
        immediate: true,
      },
    },
    methods: {
      ...mapActions('atomForm', ['loadSingleAtomList']),
      parseValue(newValue) {
        // 未配置时默认为所有插件可用
        const hasConfig = newValue
          && typeof newValue === 'object'
          && newValue.default
          && typeof newValue.default === 'object';
        const defaultConfig = hasConfig ? newValue.default : {};
        this.mode = defaultConfig.mode || 'allow_all';
        this.pluginCodes = Array.isArray(defaultConfig.plugin_codes)
          ? [...defaultConfig.plugin_codes]
          : [];
      },
      async loadCandidates() {
        if (!this.spaceId) return;
        try {
          this.loading = true;
          const pluginList = await this.loadSingleAtomList({ space_id: this.spaceId, skip_space_config: true });
          const excludedCodes = ['subcanvas_plugin', 'subprocess_plugin'];
          this.candidates = (pluginList || [])
            .filter(plugin => !excludedCodes.includes(plugin.code))
            .map(plugin => ({ id: plugin.code, name: plugin.name }));
        } catch (e) {
          this.candidates = [];
        } finally {
          this.loading = false;
        }
      },
      goPluginManage() {
        this.$router.push({
          query: { ...this.$route.query, activeTab: 'pluginManage' },
        });
      },
      emitValue() {
        this.$emit('change', { default: { mode: this.mode, plugin_codes: this.pluginCodes } });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .ps-mode {
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .ps-select-title{
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 700;
  }
  .ps-radio {
    margin-right: 24px;
    color: #4d4f56;
    font-size: 12px;
    line-height: 20px;
    margin-bottom: 8px;
  }
  .ps-select {
    max-width: 480px;
    width: 100%;
  }
  .ps-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid #b0c8ff;
    border-radius: 6px;
    background: #f0f4ff;
    .ps-banner-icon {
      flex-shrink: 0;
      font-size: 32px;
      color: #3974ff;
    }
    .ps-banner-content {
      display: flex;
      flex: 1;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      font-family: "PingFang SC";
      font-size: 12px;
      line-height: 20px;
    }

    .ps-banner-title {
      font-weight: 500;
      color: #111214;
    }

    .ps-banner-desc {
      color: #4e5e7a;
      word-break: break-word;
    }

    .ps-banner-btn {
      flex-shrink: 0;
    }
  }

  .ps-legacy {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 12px;

    .ps-legacy-title {
      font-family: "PingFang SC";
      font-size: 14px;
      font-weight: 500;
      line-height: 22px;
      color: #111214;
    }
  }
  .ps-kv {
    width: 100%;
    border-bottom: 1px solid #e4e9f2;

    .ps-kv-row {
      display: flex;
      align-items: center;
      min-height: 40px;
      border-top: 1px solid #e4e9f2;
    }

    .ps-kv-label {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: flex-end;
      width: 100px;
      height: 40px;
      padding-right: 12px;
      background: #f2f6fc;
      font-family: "PingFang SC";
      font-size: 12px;
      font-weight: 500;
      line-height: 20px;
      color: #111214;
    }

    .ps-kv-value {
      display: flex;
      flex: 1;
      align-items: center;
      gap: 4px;
      min-width: 0;
      padding: 8px 12px;
      background: #fff;
      font-size: 12px;
      line-height: 20px;
      color: #4e5e7a;

      &.is-wrap {
        flex-wrap: wrap;
      }

      &.is-multiline {
        word-break: break-word;
      }
    }

    .ps-kv-empty {
      color: #979ba5;
    }

    // 插件名 tag
    .ps-tag {
      padding: 1px 8px;
      border-radius: 2px;
      background: #f0f4fa;
      font-family: "PingFang SC";
      font-size: 12px;
      line-height: 20px;
      color: #4e5e7a;
      word-break: break-word;
    }
  }

  .ps-warn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid #ffce81;
    border-radius: 6px;
    background: #fff3e0;
    .ps-warn-icon {
      margin-top: 2px;
      font-size: 14px !important;
      color: #FAA41E;
    }
    .ps-warn-text {
      flex: 1;
      font-family: "PingFang SC";
      font-size: 12px;
      line-height: 20px;
      color: #4e5e7a;
      word-break: break-word;
    }
  }
</style>
