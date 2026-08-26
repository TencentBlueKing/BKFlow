<template>
  <div class="plugin-scope">
    <bk-radio-group
      v-model="mode"
      class="ps-mode"
      @change="emitValue">
      <bk-radio
        value="allow_all"
        class="ps-radio">
        {{ $t('所有插件可用') }}
      </bk-radio>
      <bk-radio
        value="allow_list"
        class="ps-radio">
        {{ $t('允许名单:仅所列插件可用') }}
      </bk-radio>
      <bk-radio
        value="deny_list"
        class="ps-radio">
        {{ $t('屏蔽名单:屏蔽所列插件，其余可用') }}
      </bk-radio>
    </bk-radio-group>
    <bk-select
      v-show="mode !== 'allow_all'"
      v-model="pluginCodes"
      multiple
      searchable
      display-tag
      allow-create
      :loading="loading"
      :placeholder="$t('选择或输入插件 code')"
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
          const excludedCodes = ['subcanvs_plugin', 'subprocess_plugin'];
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
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .ps-radio {
    margin-right: 24px;
    color: #4d4f56;
    font-size: 12px;
    line-height: 20px;
  }
  .ps-select {
    max-width: 480px;
    width: 100%;
  }
</style>
