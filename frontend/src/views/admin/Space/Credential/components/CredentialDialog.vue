<template>
  <bk-dialog
    :value="isShow"
    theme="primary"
    header-position="left"
    ext-cls="credential-dialog"
    :mask-close="false"
    :width="640"
    :esc-close="false"
    :confirm-close="false"
    render-directive="if"
    :title="detail.id ? $t('编辑凭证') : $t('新建凭证')"
    @confirm="handleConfirm"
    @cancel="handleCancel">
    <bk-form
      ref="credentialFormRef"
      :model="formData"
      :rules="rules"
      form-type="vertical">
      <bk-form-item
        :label="$t('名称')"
        :required="true"
        property="name"
        error-display-type="normal">
        <bk-input
          v-model.trim="formData.name"
          :allow-emoji="false"
          :clearable="true"
          :show-clear-only-hover="true"
          :maxlength="32"
          :placeholder="
            $t(
              '中英文字符、数字或以下字符-)().，以中英文字符、数字开头，32个字符内'
            )
          " />
      </bk-form-item>
      <bk-form-item
        :label="!isShowPreviewImage ? $t('类型') : ''"
        :required="true"
        property="type">
        <div
          v-if="isShowPreviewImage"
          class="custom-type-form-item">
          <div class="label">
            {{ $t("类型") }}
          </div>
          <bk-button
            text
            type="primary"
            @click="handleShowImage">
            {{ $t("查看凭证获取指引") }}
          </bk-button>
        </div>
        <div class="credential-type-list">
          <div
            v-for="item of CREDENTIAL_TYPE_LIST"
            :key="item.value"
            :class="[
              'credential-type-item',
              {
                'is-active': item.value === formData.type,
              },
            ]"
            @click="handleTypeChange(item)">
            {{ item.text }}
          </div>
        </div>
      </bk-form-item>
      <template v-if="isApp">
        <bk-form-item
          label="bk_app_code"
          :required="true"
          property="content.bk_app_code"
          error-display-type="normal">
          <bk-input
            v-model.trim="formData.content.bk_app_code"
            :allow-emoji="false"
            :show-clear-only-hover="true"
            :clearable="true"
            :placeholder="$t('仅支持字母、数字、下划线、连字符')" />
        </bk-form-item>
        <bk-form-item
          label="bk_app_secret"
          :required="true"
          property="content.bk_app_secret"
          error-display-type="normal">
          <bk-input
            v-model.trim="formData.content.bk_app_secret"
            type="password"
            :allow-emoji="false"
            :clearable="true"
            :show-clear-only-hover="true"
            :placeholder="$t('仅支持字母、数字、下划线、连字符')" />
        </bk-form-item>
      </template>
      <template v-if="isAccessToken">
        <bk-form-item
          label="access_token"
          :required="true"
          property="content.access_token"
          error-display-type="normal">
          <bk-input
            v-model.trim="formData.content.access_token"
            type="password"
            :allow-emoji="false"
            :clearable="true"
            :show-clear-only-hover="true"
            :placeholder="$t('仅支持字母、数字、下划线、连字符')" />
        </bk-form-item>
      </template>
      <template v-if="isBasicAuth">
        <bk-form-item
          label="username"
          :required="true"
          property="content.username"
          error-display-type="normal">
          <bk-input
            v-model.trim="formData.content.username"
            :allow-emoji="false"
            :clearable="true"
            :show-clear-only-hover="true"
            :placeholder="$t('仅支持字母、数字、下划线、连字符')" />
        </bk-form-item>
        <bk-form-item
          label="password"
          :required="true"
          property="content.password"
          error-display-type="normal">
          <bk-input
            v-model.trim="formData.content.password"
            type="password"
            :allow-emoji="false"
            :clearable="true"
            :show-clear-only-hover="true"
            :placeholder="$t('仅支持字母、数字、下划线、连字符')" />
        </bk-form-item>
      </template>
      <template v-if="isCustom">
        <bk-form-item
          :label="$t('凭证内容')"
          :required="true"
          property="content"
          error-display-type="normal">
          <CredentialContentTable
            ref="credentialContentTableRef"
            empty-tip="第n项凭证内容不能为空"
            error-tip="第n项凭证内容格式错误, 仅支持字母、数字、下划线、连字符"
            :select-list="customContentList"
            :table-fields="tableFields" />
        </bk-form-item>
      </template>
      <bk-form-item
        :label="$t('描述')"
        property="desc">
        <bk-input
          v-model="formData.desc"
          type="textarea"
          class="form-item-desc"
          :clearable="true"
          :show-clear-only-hover="true"
          :maxlength="100" />
      </bk-form-item>
    </bk-form>
    <ImageViewer
      :image-url="getImageUrl"
      :visible.sync="showViewer" />
    <template #footer>
      <div class="dialog-btn">
        <bk-button
          theme="primary"
          :loading="confirmLoading"
          @click="handleConfirm">
          {{ $t("确定") }}
        </bk-button>
        <bk-button
          :disabled="confirmLoading"
          @click="handleCancel">
          {{ $t("取消") }}
        </bk-button>
      </div>
    </template>
  </bk-dialog>
</template>

<script>
import { cloneDeepWith } from 'lodash';
import { mapActions } from 'vuex';
import { CREDENTIAL_TYPE_LIST } from '@/constants';
import ImageViewer from './ImageViewer.vue';
import CredentialContentTable from './CredentialContentTable.vue';

export default {
  components: { CredentialContentTable, ImageViewer },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    detail: {
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
      CREDENTIAL_TYPE_LIST,
      confirmLoading: false,
      showViewer: false,
      formData: {
        name: '',
        desc: '',
        type: 'BK_APP',
        content: {
          bk_app_code: '',
          bk_app_secret: '',
          access_token: '',
          username: '',
          password: '',
        },
      },
      rules: {
        name: [
          {
            required: true,
            message: this.$t('名称不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9][a-zA-Z0-9\-)().，]*$/;
              return reg.test(val);
            },
            message: this.$t('中英文字符、数字或以下字符-)().，以中英文字符、数字开头，32个字符内'),
            trigger: 'blur',
          },
        ],
        'content.bk_app_code': [
          {
            required: true,
            message: this.$t('bk_app_code不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9_-]+$/;
              return reg.test(val);
            },
            message: this.$t('仅支持字母、数字、下划线、连字符'),
            trigger: 'blur',
          },
        ],
        'content.bk_app_secret': [
          {
            required: true,
            message: this.$t('bk_app_secret不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9_-]+$/;
              return reg.test(val);
            },
            message: this.$t('仅支持字母、数字、下划线、连字符'),
            trigger: 'blur',
          },
        ],
        'content.access_token': [
          {
            required: true,
            message: this.$t('access_token不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9_-]+$/;
              return reg.test(val);
            },
            message: this.$t('仅支持字母、数字、下划线、连字符'),
            trigger: 'blur',
          },
        ],
        'content.username': [
          {
            required: true,
            message: this.$t('username不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9_-]+$/;
              return reg.test(val);
            },
            message: this.$t('仅支持字母、数字、下划线、连字符'),
            trigger: 'blur',
          },
        ],
        'content.password': [
          {
            required: true,
            message: this.$t('password不能为空'),
            trigger: 'blur',
          },
          {
            validator(val) {
              const reg = /^[a-zA-Z0-9_-]+$/;
              return reg.test(val);
            },
            message: this.$t('仅支持字母、数字、下划线、连字符'),
            trigger: 'blur',
          },
        ],
      },
      allowFieldsByType: {
        BK_APP: ['bk_app_code', 'bk_app_secret'],
        BK_ACCESS_TOKEN: ['access_token'],
        BASIC_AUTH: ['username', 'password'],
        CUSTOM: ['key', 'value'],
      },
      tableFields: [
        {
          prop: 'key',
          label: 'key',
          inputType: 'text',
        },
        {
          prop: 'value',
          label: 'value',
          inputType: 'password',
        },
      ],
      customContentList: [],
    };
  },
  computed: {
    isApp() {
      return ['BK_APP'].includes(this.formData.type);
    },
    isAccessToken() {
      return ['BK_ACCESS_TOKEN'].includes(this.formData.type);
    },
    isBasicAuth() {
      return ['BASIC_AUTH'].includes(this.formData.type);
    },
    isCustom() {
      return ['CUSTOM'].includes(this.formData.type);
    },
    isShowPreviewImage() {
      return this.isApp || this.isAccessToken;
    },
    getImageUrl() {
      if (this.isApp) {
        return require('@/assets/images/apigw.png');
      }

      if (this.isAccessToken) {
        return require('@/assets/images/apigw_access_token.png');
      }

      return '';
    },
  },
  watch: {
    detail: {
      handler(rowData) {
        if (Object.keys(rowData).length) {
          Object.keys(rowData).forEach((key) => {
            if (Object.prototype.hasOwnProperty.call(this.formData, key)) {
              if (['content'].includes(key)) {
                this.formData.content = Object.assign(
                  this.formData.content,
                  rowData[key]
                );
                // 如果是自定义需要转换成表格渲染格式
                if (this.isCustom) {
                  this.customContentList = Object.entries(rowData.content).map(([key, value]) => ({
                      key,
                      value,
                    }));
                }
              } else {
                this.formData[key] = rowData[key];
              }
            }
          });
        }
      },
      immediate: true,
    },
  },
  methods: {
    ...mapActions('credentialConfig', ['createCredential', 'updateCredential']),
    // 校验是否存在重复凭证内容key
    getCredentialContent(list) {
      const content = {};
      const keys = new Set();
      for (const item of list) {
        const { key, value } = item;
        // 校验key是否重复
        if (keys.has(key)) {
          return false;
        }
        keys.add(key);
        content[key] = value;
      }
      return content;
    },
    handleTypeChange(tab) {
      if (tab.value === this.formData.type) {
        return;
      }
      this.formData.type = tab.value;
      this.$refs.credentialFormRef.clearError();
    },
    handleShowImage() {
      this.showViewer = true;
    },
    handleCancel() {
      this.formData = Object.assign({}, {
        name: '',
        type: 'BK_APP',
        desc: '',
        content: {
          bk_app_code: '',
          bk_app_secret: '',
          access_token: '',
          username: '',
          password: '',
        },
      });
      this.customContentList = [];
      const customRef = this.$refs.credentialContentTableRef;
      customRef?.clearValidate();
      customRef?.setCredentialField(this.tableFields);
      this.$emit('cancel');
    },
    async handleConfirm() {
      try {
        await this.$refs.credentialFormRef.validate();
        let isCustomValidate = true;
        const { credentialList, validate } = this.$refs.credentialContentTableRef ?? {};
        // 自定义需要校验表格内容是否存在空项
        if (this.isCustom) {
          isCustomValidate = validate();
        }
        if (isCustomValidate) {
          const params = Object.assign(cloneDeepWith(this.formData), {
            id: this.detail.id,
            space_id: this.spaceId,
          });
          // 根据不同类型去掉要过滤的字段
          Object.keys(params.content).forEach((key) => {
            if (!this.allowFieldsByType[this.formData.type].includes(key)) {
              delete params.content[key];
            }
          });
          if (this.isCustom) {
            const customContent = this.getCredentialContent(credentialList);
            if (typeof customContent === 'boolean') {
              return;
            }
            params.content = customContent;
          }
          this.confirmLoading = true;
          const res = params.id
            ? await this.updateCredential(params)
            : await this.createCredential(params);
          if (res?.result) {
            this.$bkMessage({
              message: this.$t(params.id ? '修改成功！' : '新增成功！'),
              theme: 'success',
            });
            this.handleCancel();
            this.$emit('confirm', !params.id);
          }
        }
      } finally {
        this.confirmLoading = false;
      }
    },
  },
};
</script>

<style lang="scss" scoped>
@import "@/scss/mixins/credentialScope.scss";

.credential-type-list {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  box-sizing: border-box;
  .credential-type-item {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    border: 1px solid #dcdee5;
    border-right: 0;
    border-radius: 0 2px 2px 0;
    box-sizing: border-box;
    padding: 0 16px;
    text-align: center;
    line-height: 32px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: pointer;
    &:nth-child(2) {
      min-width: 179px;
    }
    &:last-child {
      min-width: 118px;
      border-right: 1px solid #dcdee5;
    }
    &.is-active {
      background-color: #e1ecff;
      border-color: #3a84ff;
      color: #3a84ff;
      border-radius: 2px 0 0 2px;
      &.is-active + .credential-type-item {
        border-left: 1px solid #3a84ff;
      }
    }
  }
}
.custom-type-form-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  line-height: 32px;
  .label::after {
    @include required-asterisk;
  }
  .bk-button-text {
    height: 32px;
  }
}
::v-deep .form-item-desc {
  .bk-form-textarea {
    min-height: 54px;
  }
}
</style>
