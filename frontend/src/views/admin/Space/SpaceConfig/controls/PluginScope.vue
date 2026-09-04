<template>
  <div class="plugin-scope">
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
    },
    data() {
      return {
        mode: 'allow_all',
        pluginCodes: [],
        candidates: [],
        loading: false,
      };
    },
    watch: {
      value: {
        handler(newValue) {
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
</style>
