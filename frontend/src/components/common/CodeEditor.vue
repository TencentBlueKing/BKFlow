/** * Tencent is pleased to support the open source community by making
蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community * Edition) available. *
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved. *
Licensed under the MIT License (the "License"); you may not use this file except
in compliance with the License. * You may obtain a copy of the License at *
http://opensource.org/licenses/MIT * Unless required by applicable law or agreed
to in writing, software distributed under the License is distributed on * an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied. See the License for the * specific language governing permissions and
limitations under the License. */
<template>
  <section class="code-editor" />
</template>
<script>
  import * as monaco from 'monaco-editor';

  const DEFAULT_OPTIONS = {
    language: 'javascript',
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: {
      enabled: false,
    },
    wordWrap: 'on',
    wrappingIndent: 'same',
  };
  export default {
    name: 'CodeEditor',
    props: {
      value: {
        type: String,
        default: '',
      },
      options: {
        type: Object,
        default() {
          return {};
        },
      },
    },
    data() {
      const editorOptions = Object.assign({}, DEFAULT_OPTIONS, this.options, {
        value: this.value,
      });
      return {
        editorOptions,
        monacoInstance: null,
      };
    },
    watch: {
      value(val) {
        const valInEditor = this.monacoInstance.getValue();
        if (val !== valInEditor) {
          this.monacoInstance.setValue(val);
        }
      },
      options: {
        deep: true,
        handler(val) {
          this.editorOptions = Object.assign({}, DEFAULT_OPTIONS, val, {
            value: this.value,
          });
          this.updateOptions();
        },
      },
    },
    mounted() {
      this.initIntance();
    },
    beforeDestroy() {
      if (this.monacoInstance) {
        this.monacoInstance.dispose();
      }
    },
    methods: {
      initIntance() {
        this.monacoInstance = monaco.editor.create(
          this.$el,
          this.editorOptions
        );
        const model = this.monacoInstance.getModel();
        model.setEOL(0); // 设置编辑器在各系统平台下 EOL 统一为 \n
        if (this.value.indexOf('\r\n') > -1) {
          // 转换已保存的旧数据
          const textareaEl = document.createElement('textarea');
          textareaEl.value = this.value;
          this.$emit('input', textareaEl.value);
        }
        model.onDidChangeContent(() => {
          const value = this.monacoInstance.getValue();
          this.$emit('input', value);
        });
        // 监听失去焦点事件
        this.monacoInstance.onDidBlurEditorText(() => {
          this.$emit('blur');
        });
        this.monacoInstance.addCommand(
          monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_S,
          () => {
            const value = this.monacoInstance.getValue();
            this.$emit('saveContent', value);
          }
        );
        // 添加placeholder
        const { placeholder } = this.options;
        if (placeholder) {
          const value = typeof placeholder === 'string' ? placeholder : JSON.stringify(placeholder, null, 4);
          this.setPlaceholder(value);
        }
      },
      setPlaceholder(value) {
        const { monacoInstance: editor } = this;
        // 在编辑器中添加overlaywidget来显示placeholder文本
        const placeholderWidget = {
          getId() {
            return 'placeholder.widget';
          },
          getDomNode() {
            if (!this.domNode) {
              this.domNode = document.createElement('div');
              this.domNode.innerHTML = value;
              this.domNode.classList.add('editor-placeholder');
              this.domNode.style.display = editor.getValue() ? 'none' : '';
            }
            return this.domNode;
          },
          getPosition() {
            return null;
          },
        };

        // 添加widget到编辑器中
        editor.addOverlayWidget(placeholderWidget);

        // 监听编辑器内容改变，切换placeholder显示与否
        editor.onDidChangeModelContent(() => {
          placeholderWidget.getDomNode().style.display = editor.getValue() ? 'none' : '';
        });
      },
      updateOptions() {
        this.monacoInstance.updateOptions(this.editorOptions);
      },
      layoutInstance() {
        this.monacoInstance.layout();
      },
    },
  };
</script>
<style lang="scss" scoped>
.code-editor {
    height: 100%;
    ::v-deep .editor-placeholder {
      position: absolute;
      top: -2px;
      left: 65px;
      line-height: 22px;
      padding-right: 20px;
      word-break: break-all;
      color: rgb(117, 117, 117);
      pointer-events: none;
      white-space: pre-wrap;
    }
}
</style>
