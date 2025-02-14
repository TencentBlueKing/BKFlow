<template>
  <div class="value-assign-plugin">
    <bk-form
      ref="valueAssignForm"
      :label-width="0"
      :model="formData">
      <bk-form-item
        :label="$t('变量列表')"
        :label-width="100"
        :required="true">
        <div
          v-for="(item, index) in formData.value"
          :key="index"
          class="form-content-item">
          <bk-form-item
            label=""
            :property="`value.${index}.key`"
            :rules="rules.key">
            <bk-select
              v-model="item.key"
              ext-cls="value-selector"
              ext-popover-cls="value-selector-popover"
              :disabled="isViewMode"
              :placeholder="$t('被赋值变量')"
              searchable>
              <bk-option
                v-for="option in variableRenderList"
                :id="option.key"
                :key="option.index"
                :name="option.key">
                <span
                  v-bk-overflow-tips
                  class="key ellipsis">{{ option.key }}</span>
                <span
                  v-bk-overflow-tips
                  class="name ellipsis">{{ option.name }}</span>
              </bk-option>
            </bk-select>
          </bk-form-item>
          <span class="equal-sign">{{ '=' }}</span>
          <bk-form-item
            label=""
            :property="`value.${index}.value`"
            :rules="rules.required">
            <bk-input
              v-model="item.value"
              :disabled="isViewMode"
              :placeholder="$t('值')" />
          </bk-form-item>
          <template v-if="!isViewMode">
            <bk-button
              icon="icon-plus-line"
              class="mr5 ml5"
              @click="updateList(index, 'add')" />
            <bk-button
              icon="icon-minus-line"
              :disabled="formData.value.length === 1"
              @click="updateList(index, 'delete')" />
          </template>
        </div>
      </bk-form-item>
    </bk-form>
  </div>
</template>
<script>
  export default {
    props: {
      isViewMode: {
        type: Boolean,
        default: true,
      },
      variableList: {
        type: Array,
        default: () => ([]),
      },
      value: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      let { value: data = [{ key: '', value: '' }] } = this.value;
      data = data.map((item) => {
        if (item.key) {
          return { key: `\${${item.key}}`, value: item.value };
        }
        return item;
      });
      return {
        formData: { value: data },
        rules: {
          required: [{
            required: true,
            message: '必填项',
            trigger: 'blur',
          }],
          key: [
            {
              required: true,
              message: '必填项',
              trigger: 'blur',
            },
            {
              validator: (val) => {
                const keys = this.formData.value.map(item => item.key).filter(key => key === val);
                return keys.length <= 1;
              },
              message: '被赋值变量不能重复',
              trigger: 'change',
            },
          ],
        },
      };
    },
    computed: {
      variableRenderList() {
        if (this.isViewMode) {
          return this.variableList;
        }
        return this.variableList.reduce((acc, cur) => {
          if (['system', 'project'].includes(cur.source_type)) {
            return acc;
          }
          acc.push(cur);
          return acc;
        }, []);
      },
    },
    watch: {
      formData: {
        handler(val) {
          // 存的时候需要将【被赋值变量】解除变量格式
          const value = val.value.map(item => ({ key: item.key.slice(2, -1), value: item.value }));
          this.$emit('update', { value });
        },
        deep: true,
      },
    },
    methods: {
      updateList(index, type) {
        if (type === 'delete') {
          this.formData.value.splice(index, 1);
        } else {
          this.formData.value.splice(index + 1, 0, {
            key: '',
            value: '',
          });
        }
      },
      validate() {
        return this.$refs.valueAssignForm.validate();
      },
    },
  };
</script>
<style lang="scss" scoped>
  .value-assign-plugin {
    /deep/.form-content-item {
      display: flex;
      align-items: center;
      .bk-form-item {
        flex: 1;
      }
      .equal-sign {
        margin: 0 8px;
      }
      .bk-button {
        padding: 0;
        min-width: 32px;
        i {
          top: -1px;
          font-size: 12px;
        }
      }
      .value-selector {
        flex: 1;
        &.is-disabled {
          /deep/.bk-select-name {
            pointer-events: none;
            background: #fafbfd;
          }
        }
      }
      &:not(:last-child) {
        margin-bottom: 5px;
      }
    }
  }
</style>
<style lang="scss">
.value-selector-popover {
  .bk-option-content {
    display: flex;
    align-items: center;
    .key {
      max-width: 200px;
    }
    .name {
      color: #c4c6cc;
      margin-left: 16px;
    }
    .ellipsis {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
  }
}
</style>
