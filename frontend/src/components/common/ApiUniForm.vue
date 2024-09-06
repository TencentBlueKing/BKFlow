<template>
  <div class="api-uniform">
    <bk-form
      ref="uniForm"
      :label-width="100"
      :model="formData"
      :rules="rules">
      <bk-form-item
        v-if="formData.category || !formData.url"
        :label="$t('分类')"
        property="category"
        :required="true">
        <div
          v-if="readonly"
          class="readonly-text">
          {{ categoryReadOnlyText }}
        </div>
        <bk-select
          v-else
          v-model="formData.category"
          :disabled="isViewMode"
          :loading="categoryLoading"
          searchable
          @selected="handleCategorySelected">
          <bk-option
            v-for="option in categoryList"
            :id="option.id"
            :key="option.id"
            :name="option.name" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        :label="$t('api列表')"
        property="url"
        :required="true">
        <div
          v-if="readonly"
          class="readonly-text">
          {{ value.api_meta ? value.api_meta.name : '--' }}
        </div>
        <bk-select
          v-else
          v-model="formData.url"
          :disabled="isViewMode || categoryLoading || (!formData.category && !formData.url)"
          :loading="apiLoading"
          enable-scroll-load
          ext-popover-cls="api-popover-content"
          searchable
          :remote-method="onApiSearch"
          :scroll-loading="bottomLoadingOptions"
          @scroll-end="handleScrollToBottom"
          @selected="handleSelected">
          <i
            v-bk-tooltips.top="$t('统一 API 列表搜索功能需要 API 提供方支持，如果提供方不支持，则列表过滤不生效')"
            class="bk-icon icon-info-circle-shape" />
          <bk-option
            v-for="option in apiList"
            :id="option.id"
            :key="option.id"
            :name="option.name" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        v-if="formData.url"
        :label="$t('请求方法')"
        property="method"
        :required="true">
        <div
          v-if="readonly"
          class="readonly-text">
          {{ formData.method }}
        </div>
        <bk-select
          v-else
          v-model="formData.method"
          :disabled="isViewMode">
          <bk-option
            v-for="option in methodList"
            :id="option"
            :key="option"
            :name="option" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        v-if="formData.url"
        :label="$t('api参数')"
        property="params">
        <div
          v-bkloading="{ isLoading: apiLoading }"
          class="params-wrapper">
          <BkUniForm
            ref="bkSchemaForm"
            v-model="formData.params"
            form-type="horizontal"
            :schema="renderConfig"
            :readonly="readonly"
            :layout="{ group: [], container: { gap: '14px' } }">
            <template #suffix="{ path, schema: fieldSchema }">
              <div
                v-if="fieldSchema.extend && fieldSchema.extend.can_hook"
                class="rf-tag-hook">
                <i
                  v-bk-tooltips="{
                    content: fieldSchema.extend.hook ? $t('取消变量引用') : $t('设置为变量'),
                    placement: 'bottom',
                    zIndex: 3000
                  }"
                  :class="[
                    'common-icon-variable-cite hook-icon',
                    {
                      active: fieldSchema.extend.hook, disabled: isViewMode
                    }
                  ]"
                  @click="onHookForm(path, fieldSchema)" />
              </div>
            </template>
          </BkUniForm>
        </div>
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import jsonFormSchema from '@/utils/jsonFormSchema.js';
  import tools from '@/utils/tools.js';
  import createForm from '@blueking/bkui-form';
  import '@blueking/bkui-form/dist/bkui-form.css';
  const BkUniForm = createForm();
  export default {
    name: '',
    components: {
      BkUniForm,
    },
    props: {
      value: {
        type: Object,
        default: () => ({}),
      },
      readonly: {
        type: Boolean,
        default: false,
      },
      isViewMode: {
        type: Boolean,
        default: false,
      },
      spaceId: {
        type: Number,
        default: 0,
      },
      scopeInfo: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      const { api_meta: apiMeta = {}, api_config: apiConfig = {} } = this.value;
      const params = apiConfig.params?.reduce((acc, cur) => {
        acc[cur.key] = cur.value || '';
        return acc;
      }, {});
      const data = {
        category: apiMeta.category?.id,
        url: apiMeta.id,
        method: apiConfig.method,
        params,
      };
      return {
        formData: data,
        rules: {
          url: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
          method: [
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
          ],
        },
        initParams: tools.deepClone(params),
        categoryLoading: false,
        categoryList: [],
        apiLoading: false,
        apiList: [],
        apiKeyWord: '',
        pagination: {
          current: 1,
          count: 0,
          limit: 30,
        },
        bottomLoadingOptions: {
          size: 'small',
          isLoading: true,
        },
        methodList: [],
        renderConfig: {},
        initRenderConfig: {},
        onApiSearch: null,
        realMetaUrl: null,
      };
    },
    computed: {
      categoryReadOnlyText() {
        const apiMeta = this.value.api_meta || {};
        const { name = '--' } = apiMeta.category || {};
        return name;
      },
    },
    watch: {
      formData: {
        handler(val) {
          const meta = this.apiList.find(item => item.id === val.url) || {};
          const params = Object.keys(val.params).map(key => ({
            key,
            value: val.params[key],
            hook: val.params.hook || false,
          })) || [];
          const category = this.categoryList.find(item => item.id === val.category) || {};
          params;
          const data = {
            api_meta: {
              ...meta,
              category,
            },
            api_config: {
              url: this.realMetaUrl,
              method: val.method,
              params,
            },
          };
          this.$emit('update', data);
        },
        deep: true,
      },
    },
    created() {
      const { category, url } = this.formData;
      if (category || !url) {
        this.categoryLoading = true;
        this.getUniformCategoryList();
        this.onApiSearch = tools.debounce(this.handleApiSearch, 500);
      }
      if (url) {
        this.getUniformApiList();
      }
    },
    methods: {
      ...mapActions('template', [
        'loadUniformCategoryList',
        'loadUniformApiList',
        'loadUniformApiMeta',
      ]),
      async getUniformCategoryList() {
        try {
          const resp = await this.loadUniformCategoryList({
            ...this.scopeInfo,
            spaceId: this.spaceId,
          });
          this.categoryList = resp.data;
        } catch (error) {
          console.warn(error);
        } finally {
          this.categoryLoading = false;
        }
      },
      handleCategorySelected() {
        this.apiLoading = true;
        this.formData.url = '';
        this.apiList = [];
        this.formData.method = '';
        this.formData.params = {};
        this.getUniformApiList();
      },
      async getUniformApiList() {
        try {
          const { current, limit } = this.pagination;
          const { url, category } = this.formData;
          const resp = await this.loadUniformApiList({
            offset: (current - 1) * limit,
            limit,
            spaceId: this.spaceId,
            ...this.scopeInfo,
            category,
            key: this.apiKeyWord || undefined,
          });
          if (this.apiKeyWord) {
            this.apiList = resp.data.apis;
          } else {
            this.apiList.push(...resp.data.apis);
          }
          this.pagination.count = resp.data.total;
          // 加载列表后，如果meteUrl存在
          if (url) {
            this.selectedApiUrl(url);
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.apiLoading = false;
          this.bottomLoadingOptions.isLoading = false;
        }
      },
      handleApiSearch(val) {
        this.apiKeyWord = val;
        this.pagination.current = 1;
        this.getUniformApiList();
      },
      handleScrollToBottom() {
        if (this.pagination.count === this.apiList.length) {
          return;
        }
        this.bottomLoadingOptions.isLoading = true;
        this.pagination.current += 1;
        this.getUniformApiList();
      },
      handleSelected(url) {
        this.formData.method = '';
        this.formData.params = {};
        this.selectedApiUrl(url);
      },
      async selectedApiUrl(value) {
        try {
          const config = this.apiList.find(item => item.id === value) || {};
          const resp = await this.loadUniformApiMeta({
            spaceId: this.spaceId,
            meta_url: config.meta_url,
            ...this.scopeInfo,
          });
          const { methods, url } = resp.data;
          // 请求方法只有一个时，默认选中
          if (methods.length === 1) {
            const [method] = methods;
            this.formData.method = method;
          }
          this.methodList = methods;
          this.realMetaUrl = url;
          this.renderConfig = jsonFormSchema(resp.data, { disabled: this.isViewMode });
          this.initRenderConfig = tools.deepClone(this.renderConfig);
        } catch (error) {
          console.warn(error);
        }
      },
      async validate() {
        return this.$refs.uniForm.validate().then((result) => {
          let valid = result;
          if (this.$refs.bkSchemaForm) {
            valid = this.$refs.bkSchemaForm.validateForm();
          }
          return valid;
        });
      },
      onHookForm(path, schema) {
        if (this.isViewMode) return;
        console.log(path, schema);
        // this.$emit('onHook', this.scheme.tag_code, val)
      },
    },
  };
</script>

<style lang="scss" scoped>
  .api-uniform {
    /deep/.params-wrapper {
      border: 1px solid #c4c6cc;
      padding: 20px;
      .bk-form-item::before {
        display: none;
      }
      .bk-form-content {
        width: calc(100% - 197px);
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
            font-size: 19px;
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
      .bk-label {
        white-space: nowrap;
      }
    }
    .readonly-text {
      font-size: 12px;
      line-height: 32px;
      color: #63656e;
    }
  }
</style>
<style lang="scss">
  .api-popover-content {
    .bk-select-search-input {
      padding: 0 30px;
    }
    .icon-info-circle-shape {
      position: absolute;
      z-index: 2;
      right: 10px;
      top: -24px;
      color: #c4c6cc;
      font-size: 16px;
    }
  }
</style>
