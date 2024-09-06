<template>
  <section class="mock-config-section">
    <bk-alert
      type="info"
      :title="$t('你可以设置多份 Mock 数据方案，用于不同调试场景。')" />
    <bk-button
      class="add-btn"
      theme="default"
      icon="plus"
      :disabled="!tplActions.includes('MOCK')"
      @click="onAddScheme">
      {{ $t('新增数据方案') }}
    </bk-button>
    <bk-collapse
      v-if="mockDataList.length"
      v-model="activeName">
      <bk-collapse-item
        v-for="item in mockDataList"
        :key="item.uuid"
        :name="`'${item.uuid}'`">
        <div class="collapse-header">
          <div class="header-left">
            <i class="bk-icon icon-right-shape" />
            <template v-if="!item.isNameEditing">
              <span class="name">{{ item.name }}</span>
              <i
                class="bk-icon icon-edit-line"
                @click.stop="item.isNameEditing = true" />
            </template>
            <div
              v-else
              class="name-input"
              @click.stop>
              <bk-input
                v-model="item.name"
                :maxlength="64"
                :show-word-limit="true"
                v-validate="{ required: true }"
                data-vv-validate-on=" "
                :name="`mockName_${item.uuid}`"
                :class="[{ 'vee-error': veeErrors.has(`mockName_${item.uuid}`)}]"
                @blur="handleNameInputBlur(item)" />
                <span v-if="veeErrors.has(`mockName_${item.uuid}`)" class="error-msg">
                  {{ veeErrors.first(`mockName_${item.uuid}`) }}
                </span>
            </div>
          </div>
          <div
            class="header-right"
            @click.stop>
            <span
              :class="['default-label', { 'is-default': item.is_default }]"
              @click="toggleSchemeDefault(item)">
              {{ item.is_default ? $t('默认') : $t('设为默认') }}
            </span>
            <i
              class="bk-icon icon-copy"
              @click="copyScheme(item)" />
            <i
              class="bk-icon icon-delete"
              @click="deleteScheme(item)" />
          </div>
        </div>
        <div slot="content">
          <template v-if="hookedFormSchema.length || unhookedFormSchema.length">
            <RenderForm
              v-if="hookedFormSchema.length"
              v-model="item.data"
              :scheme="hookedFormSchema"
              :constants="constants"
              :form-option="renderOption" />
            <NoData
              v-else
              :message="$t('暂无字段可设置')"
              style="height: 180px" />
            <p
              v-if="unhookedFormSchema.length"
              class="unhooked-title"
              @click="item.isExpend = !item.isExpend">
              <i
                class="bk-icon icon-angle-double-down"
                :class="{ 'is-expend': item.isExpend }" />
              <span>{{ item.isExpend ? $t('收起未勾选的字段') : $t('显示未勾选的字段') }}</span>
            </p>
            <RenderForm
              v-show="item.isExpend"
              v-model="item.data"
              class="un-hooked-form"
              :scheme="unhookedFormSchema"
              :constants="constants"
              :form-option="renderOption" />
          </template>
          <NoData
            v-else
            :message="$t('暂无输出字段，Mock方案输出为空')" />
        </div>
      </bk-collapse-item>
    </bk-collapse>
    <bk-exception
      v-else
      class="exception-part"
      type="empty"
      scene="part">
      <p>{{ $t('暂无方案') }}</p>
      <bk-button
        :text="true"
        title="primary"
        :disabled="!tplActions.includes('MOCK')"
        @click="onAddScheme">
        {{ $t('立即新增') }}
      </bk-button>
    </bk-exception>
  </section>
</template>

<script>
  import renderFormSchema from '@/utils/renderFormSchema.js';
  import RenderForm from '@/components/common/RenderForm/RenderForm.vue';
  import NoData from '@/components/common/base/NoData.vue';
  import tools from '@/utils/tools.js';
  import { random4 } from '@/utils/uuid.js';
  export default {
    name: 'MockConfig',
    components: {
      RenderForm,
      NoData,
    },
    props: {
      nodeConfig: {
        type: Object,
        default: () => ({}),
      },
      outputs: {
        type: Array,
        default: () => ([]),
      },
      isApiPlugin: {
        type: Boolean,
        default: false,
      },
      constants: {
        type: Object,
        default: () => ({}),
      },
      spaceId: {
        type: [String, Number],
        default: '',
      },
      templateId: {
        type: [String, Number],
        default: '',
      },
      mockData: {
        type: Array,
        default: () => ([]),
      },
      tplActions: {
        type: Array,
        default: () => ([]),
      },
    },
    data() {
      const jsonFields = this.outputs.filter(item => ['object', 'json'].includes(item.type)).map(item => item.key);
      // json转字符串
      const mockDataList = tools.deepClone(this.mockData).map((item) => {
        Object.keys(item.data).forEach((key) => {
          const value = item.data[key];
          if (jsonFields.includes(key) && typeof value !== 'string') {
            item.data[key] = JSON.stringify(value, null, 4);
          }
        });
        return {
          ...item,
          uuid: item.id || item.uuid,
          isExpend: false,
          isNameEditing: false,
        };
      });
      return {
        activeName: [],
        mockDataList,
        initDataList: tools.deepClone(mockDataList),
        hookedFormSchema: {},
        unhookedFormSchema: {},
        renderOption: {
          showRequired: true,
          showGroup: true,
          showLabel: false,
          showHook: false,
          showDesc: true,
          formEdit: true,
        },
      };
    },
    watch: {
      outputs: {
        handler(val) {
          if (!val) return;
          const hookedForm = [];
          const unhookedForm = [];
          const varKeys = Object.keys(this.constants);
          this.outputs.forEach((item) => {
            // 过滤系统输出字段
            if (['_result', '_loop', '_inner_loop'].includes(item.key)) return;
            if (item.type === 'object') {
              item.type = 'json';
              item.default = JSON.stringify({}, null, 4);
            } else if (item.type === 'boolean') {
              item.type = 'list';
              item.form_type = 'radio';
              item.options = [true, false];
              item.default = false;
            }
            let matchKey = '';
            const isHooked = varKeys.some((key) => {
              const varItem = this.constants[key];
              if (varItem && varItem.source_type === 'component_outputs') {
                const sourceInfo = varItem.source_info[this.nodeConfig.id];
                const result = sourceInfo && sourceInfo.includes(item.key);
                if (result) {
                  matchKey = key;
                  return true;
                }
              }
              return false;
            });
            if (isHooked) {
              hookedForm.push({ ...item, varKey: matchKey });
            } else {
              unhookedForm.push(item);
            }
          });
          this.hookedFormSchema = hookedForm.length ? renderFormSchema(hookedForm) : [];
          this.unhookedFormSchema = unhookedForm.length ? renderFormSchema(unhookedForm) : [];
        },
        immediate: true,
      },
    },
    methods: {
      onAddScheme() {
        const defaultName = this.$t('Mock 数据方案');
        const regex = new RegExp(`^${defaultName}[0-9]*$`);
        const defaultNameList = this.mockDataList.reduce((acc, cur) => {
          if (regex.test(cur.name)) {
            acc.push(cur.name);
          }
          return acc;
        }, []);
        let name = defaultName + 1;
        if (defaultNameList.length) {
          const index = defaultNameList.map(item => (Number(item.split(defaultName)[1])));
          const maxIndex = Math.max(...index) + 1;
          name = defaultName + maxIndex;
        }
        this.mockDataList.push({
          uuid: random4(),
          name,
          is_default: false,
          isExpend: false,
          isNameEditing: false,
          data: {},
        });
      },
      handleNameInputBlur (val) {
        this.$validator.validateAll().then(result => {
          val.isNameEditing = !result
        })
      },
      toggleSchemeDefault(val) {
        if (val.is_default) {
          val.is_default = false;
          return;
        }
        this.mockDataList.forEach((item) => {
          item.is_default = val.uuid === item.uuid;
        });
      },
      copyScheme(val) {
        if (this.veeErrors.has(`mockName_${val.uuid}`)) {
          return
        }
        const index = this.mockDataList.findIndex(item => item.uuid === val.uuid);
        this.mockDataList.splice(index + 1, 0, {
          uuid: random4(),
          name: `${val.name}_clone`,
          is_default: false,
          isExpend: false,
          isNameEditing: false,
          data: { ...val.data },
        });
      },
      deleteScheme(val) {
        this.mockDataList = this.mockDataList.filter(item => item.uuid !== val.uuid);
      },
      validate () {
        return this.$validator.validateAll().then(valid => valid); 
      }
    },
  };
</script>

<style lang="scss" scoped>
.mock-config-section {
  .bk-alert{
    margin-bottom: 16px;
  }
  .add-btn {
    display: block;
    width: 136px;
    margin-bottom: 16px;
    .icon-plus {
      color: #979ba5;
    }
  }
  .bk-collapse-item {
    margin-bottom: 16px;
  }
  /deep/.bk-collapse-item-header {
    height: 40px;
    padding: 0;
    .fr {
      display: none;
    }
    .collapse-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 40px;
      font-size: 12px;
      padding: 0 16px 0 8px;
      background: #eae8f0;
      border-radius: 2px;
      .header-left {
        display: flex;
        align-items: center;
        color: #63656e;
        .icon-right-shape {
          display: inline-block;
          font-size: 16px;
          margin-right: 8px;
        }
        .icon-edit-line {
          display: none;
          color: #979ba5;
          margin-left: 8px;
        }
        .name-input {
          display: flex;
          align-items: center;
          .bk-form-control {
            width: 240px;
          }
          .bk-button-text {
            font-size: 12px;
            line-height: 34px;
            margin-left: 8px;
          }
          .vee-error .bk-form-input {
            border-color: #ea3636;
          }
          .error-msg {
            line-height: 0;
            margin-left: 4px;
            color: #ea3636;
          }
        }
      }
      .header-right {
        display: none;
        align-items: center;
        .default-label {
          line-height: 22px;
          padding: 0 8px;
          margin-right: 10px;
          color: #63656e;
          background: #fafbfd;
          border: 1px solid #dcdee5;
          border-radius: 2px;
          &.is-default {
            color: #3a84ff;
            background: #f0f5ff;
            border: 1px solid #a3c5fd;
          }
        }
        i {
          color: #979ba5;
          margin-left: 8px;
        }
      }
      .icon-copy,
      .icon-delete,
      .icon-edit-line {
        font-size: 16px;
        &:hover{
          color: #3a84ff;
        }
      }
      &:hover {
        .icon-edit-line {
          display: inline-block;
        }
        .header-right {
          display: flex;
        }
      }
    }
  }
  /deep/.bk-collapse-item-content{
    padding: 12px 16px 8px;
  }
  .unhooked-title {
    display: inline-flex;
    align-items: center;
    line-height: 20px;
    font-size: 12px;
    margin: 16px 0 8px;
    color: #3a84ff;
    cursor: pointer;
    .icon-angle-double-down {
      font-size: 20px;
      &.is-expend {
        transform: rotate(180deg);
      }
    }
  }
  .exception-part {
    height: 100%;
    margin-top: 32px;
    .bk-button-text {
      font-size: 12px;
      line-height: 20px;
      margin-top: 8px;
    }
  }
  .bk-collapse-item-active {
    .icon-right-shape {
      transform: rotate(90deg);
    }
  }
  /deep/.render-form {
    .rf-form-item:not(:last-child) {
      margin-bottom: 24px;
    }
    .rf-group-name {
      position: relative;
      display: inline-flex;
      align-items: center;
      margin-bottom: 6px;
      .name {
        color: #63656e;
        line-height: 20px;
        padding: 0;
        font-weight: normal;
      }
      .scheme-code {
        color: #979ba5;
        margin-left: 5px;
      }
      .required {
        position: absolute;
        right: -12px;
      }
      &::before {
        display: none;
      }
    }
    .el-input-number {
      line-height: 32px;
    }
    .tag-textarea[jsonAttr] {
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
    &.un-hooked-form {
      padding: 16px;
      background: #f5f7fa;
      border-radius: 2px;
    }
  }
}
</style>
