<template>
  <div class="select-panel">
    <subflow
      v-if="nodeConfig.type === 'SubProcess'"
      :common="common"
      :space-id="spaceId"
      :node-config="nodeConfig"
      :template-labels="templateLabels"
      @select="$emit('select', $event)" />
    <plugin
      v-else
      :crt-plugin="isApiPlugin ? basicInfo.pluginId : basicInfo.plugin"
      :crt-group="basicInfo.groupId"
      :built-in-plugin="atomTypeList.tasknode"
      :is-third-party="isThirdParty"
      :is-api-plugin="isApiPlugin"
      :api-key="basicInfo.apiKey"
      :scope-info="scopeInfo"
      :space-id="spaceId"
      :space-related-config="spaceRelatedConfig"
      @select="$emit('select', $event)" />
  </div>
</template>
<script>
  import Plugin from './plugin.vue';
  import Subflow from './subflow.vue';

  export default {
    name: 'SelectPanel',
    components: {
      Plugin,
      Subflow,
    },
    props: {
      projectId: {
        type: [String, Number],
        default: '',
      },
      templateLabels: {
        type: Array,
        default: () => ([]),
      }, // 模板标签
      atomTypeList: {
        type: Object,
        default: () => ({}),
      },
      isThirdParty: Boolean,
      nodeConfig: {
        type: Object,
        default: () => ({}),
      },
      basicInfo: {
        type: Object,
        default: () => ({}),
      },
      common: {
        type: [String, Number],
        default: '',
      },
      isApiPlugin: Boolean,
      spaceId: {
        type: [String, Number],
        default: '',
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
      spaceRelatedConfig: {
        type: Object,
        default: () => ({}),
      },
    },
  };
</script>
<style lang="scss" scoped>
.select-panel {
    position: relative;
}
</style>
