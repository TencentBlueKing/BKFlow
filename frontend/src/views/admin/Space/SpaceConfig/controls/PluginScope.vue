<template>
  <div class="plugin-scope">
    <bk-radio-group
      v-model="mode"
      class="ps-mode"
      @change="emitValue">
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
        mode: 'allow_list',
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
        const defaultConfig = (newValue && typeof newValue === 'object' && newValue.default) || {};
        this.mode = defaultConfig.mode || 'allow_list';
        this.pluginCodes = Array.isArray(defaultConfig.plugin_codes)
          ? [...defaultConfig.plugin_codes]
          : [];
      },
      async loadCandidates() {
        if (!this.spaceId) return;
        try {
          this.loading = true;
          const pluginList = await this.loadSingleAtomList({ space_id: this.spaceId });
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
