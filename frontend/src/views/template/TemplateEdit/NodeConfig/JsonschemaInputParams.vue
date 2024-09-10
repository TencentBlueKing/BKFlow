<template>
  <div
    class="jsonschema-input-params"
    :class="{ 'api-ui-form': isApiPlugin, 'edit-mode': !isViewMode }">
    <bkui-form
      ref="bkSchemaForm"
      :value="formData"
      :form-type="formType"
      :schema="formSchema"
      :layout="{ group: [], container: { gap: '14px' } }"
      @change="$emit('update', $event)">
      <template
        v-if="isApiPlugin"
        #suffix="{ path, schema: fieldSchema }">
        <div
          v-if="fieldSchema.extend && fieldSchema.extend.can_hook"
          class="rf-tag-hook">
          <i
            v-bk-tooltips="{
              content: fieldSchema.extend.hook ? $t('取消变量引用') : $t('设置为变量'),
              placement: 'top',
              zIndex: 3000
            }"
            :class="[
              'common-icon-variable-hook hook-icon',
              {
                active: fieldSchema.extend.hook, disabled: isViewMode
              }
            ]"
            @click="$emit('onHookForm', path, fieldSchema)" />
        </div>
      </template>
    </bkui-form>
  </div>
</template>

<script>
  import createForm from '@blueking/bkui-form';
  import '@blueking/bkui-form/dist/bkui-form.css';
  import tools from '@/utils/tools.js';

  const BkuiForm = createForm();
  export default {
    name: 'JsonSchemaInputParams',
    components: {
      BkuiForm,
    },
    props: {
      formData: {
        type: Object,
        default: () => ({}),
      },
      schema: {
        type: Object,
        default: () => ({}),
      },
      isViewMode: {
        type: Boolean,
        default: false,
      },
      isApiPlugin: {
        type: Boolean,
        default: false,
      },
      formType: {
        type: String,
        default: 'horizontal',
      },
    },
    computed: {
      formSchema() {
        const schema = tools.deepClone(this.schema);
        if (this.isViewMode) {
          const { properties = {} } = schema || schema.items || {};
          this.setDisabledProps(properties);
        }
        return schema;
      },
    },
    methods: {
      validate() {
        return this.$refs.bkSchemaForm.validateForm();
      },
      setDisabledProps(properties) {
        Object.keys(properties).forEach((form) => {
          const component = properties[form]['ui:component'];
          if (!component) {
            properties[form]['ui:component'] = {
              props: { disabled: true },
            };
          } else if ('props' in component) {
            component.props.disabled = true;
          } else {
            component.props = { disabled: true };
          }
          if (properties[form].items?.properties) {
            this.setDisabledProps(properties[form].items?.properties);
          }
        });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .jsonschema-input-params {
    /deep/ .bk-form-item {
      .bk-label {
        width: 130px !important;
        font-size: 12px;
        word-wrap: break-word;
        word-break: break-all;
      }
      .bk-form-content {
        margin-left: 130px !important;
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
    }
    /deep/.bk-schema-form-group {
      .bk-schema-form-group-delete {
        display: none;
      }
      .bk-schema-form-item-auto-height {
        display: none;
      }
    }
  }
  .edit-mode {
    /deep/.bk-schema-form-group {
      .bk-schema-form-group {
        width: calc(100% - 10px);
      }
      .bk-schema-form-group-delete {
        display: inline-block;
        font-size: 14px;
        top: 50% !important;
        right: -20px !important;
        transform: translateY(-50%)
      }
      .bk-schema-form-item-auto-height {
        display: block;
      }
    }
  }
  .api-ui-form {
    /deep/.bk-form-content {
      width: calc(100% - 180px);
      .rf-tag-hook {
        position: absolute;
        top: 0;
        right: -47px;
        padding: 0 8px;
        height: 32px;
        background: #f0f1f5;
        border-radius: 2px;
        z-index: 1;
        .hook-icon {
          font-size: 16px;
          color: #979ba5;
          cursor: pointer;
          &.disabled {
            color: #c4c6cc;
            cursor: not-allowed;
          }
          &.active {
            color: #3a84ff;
          }
        }
      }
    }
    /deep/.json-textarea {
      textarea {
        min-height: 300px !important;
        background: #313238 !important;
        padding: 10px;
        border: none;
        color: #fff;
        &:focus {
          background-color: #313238 !important;
          border: none;
          color: #fff;
        }
      }
    }
    /deep/.bk-date-picker {
      width: 100%;
    }
    /deep/.bk-table {
      .bk-form-content {
        margin-left: 0 !important;
        width: auto;
      }
    }
  }
</style>
