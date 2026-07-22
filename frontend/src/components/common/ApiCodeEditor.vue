<template>
  <div
    class="api-code-editor"
    :style="{ height: editorHeight }">
    <FullCodeEditor
      :value="value"
      :options="editorOptions"
      @blur="$emit('blur')"
      @input="$emit('input', $event)" />
  </div>
</template>

<script>
  import FullCodeEditor from './FullCodeEditor.vue';

  export default {
    name: 'ApiCodeEditor',
    components: {
      FullCodeEditor,
    },
    props: {
      value: {
        type: String,
        default: '',
      },
      language: {
        type: String,
        default: 'plaintext',
      },
      height: {
        type: [String, Number],
        default: '320px',
      },
      showMiniMap: {
        type: Boolean,
        default: false,
      },
      options: {
        type: Object,
        default: () => ({}),
      },
      disabled: {
        type: Boolean,
        default: false,
      },
      readonly: {
        type: Boolean,
        default: false,
      },
      readOnly: {
        type: Boolean,
        default: false,
      },
    },
    computed: {
      editorHeight() {
        return typeof this.height === 'number' ? `${this.height}px` : this.height;
      },
      editorOptions() {
        return {
          ...this.options,
          language: this.language,
          readOnly: this.disabled || this.readonly || this.readOnly,
          minimap: {
            ...(this.options.minimap || {}),
            enabled: this.showMiniMap,
          },
        };
      },
    },
  };
</script>

<style lang="scss" scoped>
  .api-code-editor {
    min-height: 160px;
  }
</style>
