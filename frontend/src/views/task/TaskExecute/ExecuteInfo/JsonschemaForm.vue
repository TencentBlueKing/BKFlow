<template>
  <div class="jsonschema-input-params">
    <bkui-form
      form-type="horizontal"
      readonly
      :value="formData"
      :schema="schema"
      :layout="{ group: [], container: { gap: '14px' } }" />
  </div>
</template>

<script>
  import createForm from '@blueking/bkui-form';
  import '@blueking/bkui-form/dist/bkui-form.css';
  import tools from '@/utils/tools.js';

  const BkuiForm = createForm();
  export default {
    name: 'JsonSchemaForm',
    components: {
      BkuiForm,
    },
    props: {
      schema: {
        type: Object,
        default: () => ({}),
      },
      value: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        formData: tools.deepClone(this.value),
      };
    },
    watch: {
      value(val) {
        this.formData = tools.deepClone(val);
      },
    },
  };
</script>
<style lang="scss" scoped>
    .jsonschema-input-params {
        ::v-deep .bk-form-item {
            .bk-label {
                width: 100px !important;
                font-size: 12px;
            }
            .bk-form-radio {
                margin-right: 30px;
                .bk-radio-text {
                    font-size: 12px;
                }
            }
            .bk-form-checkbox {
                margin-right: 30px;
                .bk-checkbox-text {
                    font-size: 12px;
                }
            }
            & + .bk-form-item {
                margin-top: 0;
            }
        }
      ::v-deep .bk-schema-form-group {
        .bk-schema-form-item-auto-height,
        .bk-schema-form-group-delete {
          display: none;
        }
      }
    }
</style>
