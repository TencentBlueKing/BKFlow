<template>
  <div class="json-editor-control">
    <FullCodeEditor
      ref="editor"
      :value="text"
      :options="{ language: 'json', placeholder: placeholder }"
      @input="onInput" />
  </div>
</template>
<script>
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';

  export default {
    name: 'JsonEditorControl',
    components: {
      FullCodeEditor,
    },
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [Object, Array, String, Number, Boolean],
        default: '',
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
      examplePlaceholder: {
        type: [String, Object],
        default: '',
      },
    },
    computed: {
      placeholder() {
        const ex = this.examplePlaceholder;
        if (ex === undefined || ex === null) return '';
        return typeof ex === 'string' ? ex : JSON.stringify(ex, null, 2);
      },
      text() {
        if (typeof this.value === 'string') return this.value;
        return JSON.stringify(this.value, null, 4);
      },
    },
    mounted() {
      this.$nextTick(() => {
        const { editor } = this.$refs;
        if (editor && editor.layoutCodeEditorInstance) editor.layoutCodeEditorInstance();
      });
    },
    methods: {
      onInput(val) {
        this.$emit('change', val);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .json-editor-control {
    height: 300px;
    position: relative;
  }
</style>
