<template>
  <div class="api-plugin-config">
    <!-- 警告提示 -->
    <div class="apc-warning">
      <i class="bk-icon icon-info-circle" />
      <span>
        {{ $t('改动可能影响流程编排中「API插件」可选的接口与分类中已使用该接入的流程，请谨慎修改！') }}
      </span>
      <div
        v-if="docLink"
        class="apc-doc-link">
        <bk-link
          theme="primary"
          :href="docLink"
          target="_blank">
          {{ $t('查看文档') }}
        </bk-link>
        <i class="common-icon-box-top-right-corner" />
      </div>
    </div>
    <!-- api_key 卡片列表 -->
    <bk-form
      ref="apiForm"
      :model="formData"
      form-type="vertical"
      class="apc-form-root">
      <div
        v-for="(apiItem, index) in formData.apiList"
        :key="apiItem.id"
        class="apc-card">
        <div class="apc-card-head">
          <div class="apc-card-head-left">
            <span class="apc-key-label">api_key: </span>
            <bk-form-item
              :property="`apiList.${index}.apiKey`"
              :rules="rules.apiKey"
              class="apc-key-form-item">
              <bk-input
                v-model="apiItem.apiKey"
                class="apc-key-input"
                :placeholder="$t('请输入api_key，如 default')"
                behavior="simplicity"
                :clearable="true"
                @change="emitValue" />
            </bk-form-item>
          </div>
          <div class="apc-card-head-right">
            <span
              v-if="apiItem.badge"
              class="apc-key-badge">
              {{ apiItem.badge }}
            </span>
            <i
              class="bk-icon icon-delete apc-del"
              @click="removeApi(index)" />
          </div>
        </div>
        <div class="apc-form">
          <bk-form-item
            :label="$t('展示名称')"
            :required="true"
            :property="`apiList.${index}.display_name`"
            :rules="rules.display_name">
            <bk-input
              v-model="apiItem.display_name"
              :clearable="true"
              :placeholder="$t('请输入')"
              @change="emitValue" />
          </bk-form-item>
          <bk-form-item
            :label="$t('Meta 接口 URL')"
            :required="true"
            :property="`apiList.${index}.meta_apis`"
            :rules="rules.meta_apis"
            :clearable="true">
            <bk-input
              v-model="apiItem.meta_apis"
              :clearable="true"
              :placeholder="$t('如 apigw.example.com/api/{api_key}/meta')"
              @change="emitValue" />
          </bk-form-item>
          <bk-form-item
            :label="$t('分类接口 URL')"
            :required="true"
            :property="`apiList.${index}.api_categories`"
            :rules="rules.api_categories">
            <bk-input
              v-model="apiItem.api_categories"
              :clearable="true"
              :placeholder="$t('如 apigw.example.com/api/{api_key}/categories')"
              @change="emitValue" />
          </bk-form-item>
          <bk-form-item :label="$t('请求头')">
            <div
              v-for="(header, headerIndex) in apiItem.headers"
              :key="headerIndex"
              class="apc-header-row">
              <bk-form-item
                :property="`apiList.${index}.headers.${headerIndex}.key`"
                :rules="headerKeyRule(header)"
                class="apc-header-cell">
                <bk-input
                  v-model="header.key"
                  :placeholder="$t('请输入key')"
                  :clearable="true"
                  class="apc-h-input"
                  @change="emitValue" />
              </bk-form-item>
              <bk-form-item
                :property="`apiList.${index}.headers.${headerIndex}.value`"
                :rules="headerValueRule(header)"
                class="apc-header-cell apc-header-cell-value">
                <bk-input
                  v-model="header.value"
                  :placeholder="$t('请输入value')"
                  :clearable="true"
                  class="apc-h-input"
                  @change="emitValue" />
              </bk-form-item>
              <bk-icon
                type="minus-circle-shape"
                class="apc-header-del"
                @click="removeHeader(apiItem, headerIndex)" />
            </div>
            <div class="apc-header-actions">
              <bk-button
                text
                theme="primary"
                @click="addHeader(apiItem)">
                <i class="commonicon-icon common-icon-add api-add-icon" />
                <span class="apc-add-btn-text">{{ $t('添加请求头') }}</span>
              </bk-button>
            </div>
          </bk-form-item>
        </div>
        <div class="apc-test-wrap">
          <bk-button
            theme="primary"
            :disabled="apiItem.testLoading || !(apiItem.apiKey && apiItem.display_name && apiItem.meta_apis && apiItem.api_categories)"
            :icon="apiItem.testLoading ? 'loading' : ''"
            @click="testApi(apiItem)">
            {{ apiItem.testLoading ? $t('测试中') : (apiItem.testResult && apiItem.testResult.ok ? $t('重新测试') : $t('测试配置')) }}
          </bk-button>
          <template v-if="apiItem?.testResult">
            <i
              v-if="apiItem.testResult?.ok"
              class="bk-icon icon-check-circle-shape test-ok-icon" />
            <i
              v-else
              class="bk-icon icon-close-circle-shape test-fail-icon" />
            <span
              v-if="apiItem.testResult?.ok">
              <span class="test-text">{{ $t('测试成功：接口 {n} 个，分类 {m} 个', { n: apiItem.testResult.data.api_length || 0, m: apiItem.testResult.data.category_length || 0}) }}</span>
              <bk-popover
                v-if="apiItem.testResult.data.api_length > 0"
                theme="light"
                placement="bottom"
                width="520"
                ext-cls="example-popover">
                <span class="view-example-link">{{ $t('查看样例') }}</span>
                <div slot="content">
                  <bk-table
                    :data="apiItem.testResult.data.samples"
                    :max-height="300"
                    size="small">
                    <bk-table-column
                      label="ID"
                      prop="id" />
                    <bk-table-column
                      :label="$t('接口')"
                      prop="name" />
                    <bk-table-column
                      label="Method"
                      prop="method"
                      width="100" />
                  </bk-table>
                </div>
              </bk-popover>
            </span>
            <div
              v-else
              class="test-fail-text-warp">
              <span class="test-text">{{ $t('测试失败') }}</span>
              <span class="test-text test-text-colon">:</span>
              <div class="test-fail-text">
                {{ apiItem.testResult?.error || '' }}
              </div>
            </div>
          </template>
        </div>
      </div>
      <div class="add-api-key-wrap">
        <bk-button
          text
          theme="primary"
          class="apc-add-btn"
          @click="addApi">
          <i class="commonicon-icon common-icon-add api-add-icon" />
          <span class="apc-add-btn-text">{{ $t('新增 api_key') }}</span>
        </bk-button>
      </div>
    </bk-form>
  </div>
</template>
<script>
import { mapActions } from 'vuex';
  let uid = 0;
  const getNextUid = () => uid += 1;

  export default {
    name: 'ApiPluginConfig',
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
      verifying: {
        type: Boolean,
        default: false,
      },
      verifyResult: {
        type: Object,
        default: null,
      },
      docLink: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        formData: {
          apiList: [],
        },
        rules: {
          apiKey: [
            {
              required: true,
              message: this.$t('请输入 api_key'),
              trigger: 'submit',
            },
          ],
          display_name: [
            {
              required: true,
              message: this.$t('请输入展示名称'),
              trigger: 'submit',
            },
          ],
          meta_apis: [
            {
              required: true,
              message: this.$t('请输入Meta接口URL'),
              trigger: 'submit',
            },
          ],
          api_categories: [
            {
              required: true,
              message: this.$t('请输入分类接口URL'),
              trigger: 'submit',
            },
          ],
        },
      };
    },
    mounted() {
      this.parseValue(this.value);
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'verifySpaceConfig',
      ]),
      parseValue(newValue) {
        const api = (newValue && typeof newValue === 'object' && newValue.api) || {};
        this.formData.apiList = Object.keys(api).map((key) => {
          const apiEntry = api[key] || {};
          return {
            id: getNextUid(),
            apiKey: key,
            display_name: apiEntry.display_name || '',
            meta_apis: apiEntry.meta_apis || '',
            api_categories: apiEntry.api_categories || '',
            headers: (() => {
              const entries = Object.entries(apiEntry.headers || {});
              return entries.length
                ? entries.map(([headerKey, headerValue]) => ({ key: headerKey, value: headerValue }))
                : [{ key: '', value: '' }];
            })(),
            testLoading: false,
            testResult: null,
          };
        });
        if (!this.formData.apiList.length) {
          this.addApi();
        }
      },
      addApi() {
        this.formData.apiList.push({
          id: getNextUid(),
          apiKey: '',
          display_name: '',
          meta_apis: '',
          api_categories: '',
          headers: [{ key: '', value: '' }],
          testLoading: false,
          testResult: null,
        });
      },
      removeApi(idx) {
        this.formData.apiList.splice(idx, 1);
        this.emitValue();
      },
      addHeader(apiItem) {
        apiItem.headers.push({ key: '', value: '' });
      },
      removeHeader(apiItem, headerIndex) {
        apiItem.headers.splice(headerIndex, 1);
        this.emitValue();
      },
      emitValue() {
        const api = {};
        this.formData.apiList.forEach((apiItem) => {
          if (!apiItem.apiKey) return;
          const entry = {
            display_name: apiItem.display_name,
            meta_apis: apiItem.meta_apis,
          };
          if (apiItem.api_categories) entry.api_categories = apiItem.api_categories;
          const headers = {};
          apiItem.headers.forEach((header) => {
            if (header.key) headers[header.key] = header.value;
          });
          if (Object.keys(headers).length) entry.headers = headers;
          api[apiItem.apiKey] = entry;
        });
        const next = {
          ...(this.value && typeof this.value === 'object' ? this.value : {}),
          api,
        };
        this.$emit('change', next);
      },
      // 请求头 key/value 联动校验：同填同空
      headerKeyRule(header) {
        return [
          {
            validator: () => !header.value || !!header.key,
            message: this.$t('请输入key'),
            trigger: 'submit',
          },
        ];
      },
      headerValueRule(header) {
        return [
          {
            validator: () => !header.key || !!header.value,
            message: this.$t('请输入value'),
            trigger: 'submit',
          },
        ];
      },
      async validate() {
        if (!this.$refs.apiForm) return true;
        try {
          await this.$refs.apiForm.validate();
          return true;
        } catch (error) {
          return false;
        }
      },
      async testApi(apiItem) {
        const { apiKey } = apiItem;
        if (!apiKey) return;
        apiItem.testLoading = true;
        apiItem.testResult = null;
        try {
          const entry = {
            display_name: apiItem.display_name,
            meta_apis: apiItem.meta_apis,
          };
          if (apiItem.api_categories) {
            entry.api_categories = apiItem.api_categories;
          }
          const headers = {};
          apiItem.headers.forEach((header) => {
            if (header.key) {
              headers[header.key] = header.value;
            }
          });
          if (Object.keys(headers).length) entry.headers = headers;
          const resp = await this.verifySpaceConfig({
            space_id: this.spaceId,
            name: 'uniform_api',
            value: { api: { [apiItem.apiKey]: entry } },
            params: { api_key: apiKey },
          });
          apiItem.testResult = {
            ok: resp.ok,
            error: (resp.error && resp.error.message) || '',
            data: resp.data,
          };
        } catch (error) {
          console.log(error);
          apiItem.testResult = {
            ok: false,
            error: String(error),
          };
        } finally {
          apiItem.testLoading = false;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .api-plugin-config {
    font-size: 12px;
  }
  .apc-warning {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    margin-bottom: 16px;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;
    .bk-icon {
      color: #3a84ff;
      margin-right: 8px;
      font-size: 14px;
    }
    .apc-doc-link {
      color: #3a84ff;
      ::v-deep .bk-link-text {
        font-size: 12px;
      }
    }
  }
  .apc-card {
    border: 1px solid #dcdee5;
    border-radius: 2px;
    margin-bottom: 16px;
    background: #f5f7fa;
    width: 100%;
    max-width: 640px;
  }
  .apc-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 3px 16px;
    background: #f5f7fa;
    border-bottom: 1px solid #dcdee5;
  }
  .apc-card-head-left {
    display: flex;
    align-items: center;
  }
  .apc-card-head-right {
    display: flex;
    align-items: center;
  }
  .apc-key-label {
    display: inline-flex;
    -webkit-box-align: center;
    -ms-flex-align: center;
    align-items: center;
    color: #4d4f56;
    font-weight: bold;
    font-size: 12px;
    line-height: 20px;
  }
  .apc-key-value {
    color: #4d4f56;
    font-weight: bold;
    font-size: 12px;
    line-height: 20px;
  }
  .apc-key-input {
    width: 190px;
    margin-left: 5px;
    ::v-deep .bk-form-input {
      background: transparent;
    }
  }
  .apc-key-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    background: #ffe8e8;
    color: #ea3636;
    font-size: 12px;
    border-radius: 10px;
  }
  .apc-del {
    color: #ea3636;
    cursor: pointer;
    font-size: 14px;
  }
  .apc-form {
    padding: 16px;
    ::v-deep .bk-form-item {
      margin-top: 16px;
      &:first-child {
        margin-top: 0;
      }
    }
  }
  .apc-header-row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }
  .apc-header-cell {
    flex: 1 1 0;
    margin-top: 0 !important;
    margin-right: 12px;
  }
  .apc-key-form-item {
    margin-bottom: 0;
    display: inline-block;
    ::v-deep .bk-form-content {
      margin-left: 0 !important;
    }
  }
  .add-api-key-wrap{
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f0f5ff;
    border: #a3c5fd 1px dashed;
    padding: 6px 0;
    width: 100%;
    max-width: 640px;
  }
  .apc-header-del {
    flex: 0 0 auto;
    align-self: center;
    color: #979ba5;
    cursor: pointer;
    font-size: 16px !important;
  }
  .api-add-icon{
    font-size: 16px;
  }
  .apc-add-btn-text{
    font-size: 12px;
  }
  .apc-header-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .apc-test-wrap {
    padding: 0 16px 16px;
    display: flex;
    align-items: center;
    .bk-button {
      flex-shrink: 0;
    }
    .test-ok-icon {
      color: #2caf5e;
      font-size: 14px;
      margin-left: 12px;
      margin-right: 8px;
    }
    .test-fail-icon {
      color: #ea3636;
      font-size: 14px;
      margin-left: 12px;
      margin-right: 8px;
    }
    .test-text {
      color: #4d4f56;
      font-size: 12px;
      white-space: nowrap;
    }
    .test-text-colon{
      margin-right: 4px;
    }
    .test-fail-text-warp {
      display: flex;
      align-items: center;
    }
    .test-fail-text {
      color: #ea3636;
      font-size: 12px;
    }
    .view-example-link {
      margin-left: 8px;
      color: #3a84ff;
      font-size: 12px;
      cursor: pointer;
    }
  }
</style>
