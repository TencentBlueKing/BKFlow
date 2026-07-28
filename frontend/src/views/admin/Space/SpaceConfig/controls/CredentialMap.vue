<template>
  <div class="credential-map">
    <div class="credential-warning">
      <i class="bk-icon icon-info-circle" />
      <span>
        {{ $t('调用网关时按此表取凭证鉴权，表中作用域未命中时回落到默认凭证。') }}
      </span>
      <div
        class="to-credential-manage"
        @click="goCredentialManage">
        <span>{{ $t('前往凭证管理') }}</span>
        <i class="common-icon-box-top-right-corner to-credential-manage-icon" />
      </div>
    </div>
    <bk-form
      ref="credentialForm"
      :label-width="300"
      :model="formData"
      form-type="vertical">
      <!-- 默认凭证 -->
      <bk-form-item
        :label="$t('默认凭证')"
        :required="true"
        :property="'defaultCred'"
        error-display-type="normal"
        :rules="rules.defaultCred">
        <bk-select
          v-model="formData.defaultCred"
          searchable
          :loading="loading"
          :placeholder="$t('请选择 BK_APP 凭证')"
          class="cm-select"
          @change="emitValue">
          <bk-option
            v-for="credential in credentialList"
            :id="credential.name"
            :key="credential.name"
            :name="credential.name">
            <span>{{ credential.name }}</span>
          </bk-option>
        </bk-select>
      </bk-form-item>

      <!-- 按作用域覆盖 -->
      <bk-form-item
        :label="$t('按作用域覆盖(可根据自身需要判断是否需要配置)')">
        <div
          class="cm-overrides">
          <div
            v-if="formData.overrides.length > 0"
            class="cm-overrides-header">
            <span class="cm-scope-header">{{ $t('作用域') }}</span>
            <span class="cm-cred-header">{{ $t('凭证') }}</span>
          </div>
          <div
            v-for="(row, index) in formData.overrides"
            :key="index"
            class="cm-override-row">
            <bk-form-item
              :property="`overrides.${index}.scope`"
              :rules="rules.scope"
              class="cm-cell-form-item cm-cell-scope">
              <bk-input
                v-model="row.scope"
                :clearable="true"
                :placeholder="$t('请输入作用域,如：{scope_type}_{scope_id}')"
                @change="emitValue" />
            </bk-form-item>
            <bk-form-item
              :property="`overrides.${index}.name`"
              :rules="rules.name"
              class="cm-cell-form-item cm-cell-cred">
              <bk-select
                v-model="row.name"
                searchable
                :placeholder="$t('请选择凭证')"
                @change="emitValue">
                <bk-option
                  v-for="credential in credentialList"
                  :id="credential.name"
                  :key="credential.name"
                  :name="credential.name" />
              </bk-select>
            </bk-form-item>
            <bk-icon
              type="minus-circle-shape"
              class="cm-del"
              @click="removeOverride(index)" />
          </div>
          <bk-button
            text
            theme="primary"
            class="cm-add-btn"
            @click="addOverride">
            <i class="commonicon-icon common-icon-add cm-add-icon" />
            <span>{{ $t('添加作用域覆盖') }}</span>
          </bk-button>
        </div>
      </bk-form-item>
    </bk-form>
  </div>
</template>

<script>
  import { mapActions } from 'vuex';
  import tools from '@/utils/tools.js';

  export default {
    name: 'CredentialMap',
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: [String, Object],
        default: '',
      },
      schema: {
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
        loading: false,
        credentialList: [],
        formData: {
          defaultCred: '',
          overrides: [],
        },
        rules: {
          defaultCred: [
            {
              required: true,
              message: this.$t('请选择默认凭证'),
              trigger: 'submit',
            },
          ],
          scope: [
            {
              required: true,
              message: this.$t('请输入作用域'),
              trigger: 'submit',
            },
          ],
          name: [
            {
              required: true,
              message: this.$t('请选择凭证'),
              trigger: 'submit',
            },
          ],
        },
        lastEmittedValue: undefined,
      };
    },
    watch: {
      value: {
        handler(newValue) {
          if (tools.isDataEqual(newValue, this.lastEmittedValue)) return;
          this.parseValue(newValue);
        },
        immediate: true,
        deep: true,
      },
      spaceId: {
        handler(newVal, oldVal) {
          if (newVal && newVal !== oldVal) {
            this.loadBkAppCredentialList();
          }
        },
      },
    },
    created() {
      this.loadBkAppCredentialList();
    },
    methods: {
      ...mapActions('credentialConfig', [
        'loadCredentialList',
      ]),
      async loadBkAppCredentialList() {
        if (!this.spaceId) return;
        try {
          this.loading = true;
          const response = await this.loadCredentialList({
            space_id: this.spaceId,
          });
          this.credentialList = response.data.results.filter(item => item.type === 'BK_APP');
          // 默认凭证为空时，自动回落到列表第一条
          if (!this.formData.defaultCred && this.credentialList.length) {
            this.formData.defaultCred = this.credentialList[0].name;
            this.emitValue();
          }
        } catch (e) {
          this.credentialList = [];
        } finally {
          this.loading = false;
        }
      },
      parseValue(newValue) {
        this.lastEmittedValue = newValue;
        if (newValue && typeof newValue === 'object') {
          this.formData.defaultCred = newValue.default || '';
          const overrides = Object.keys(newValue)
            .filter(key => key !== 'default')
            .map(key => ({ scope: key, name: newValue[key] }));
          this.formData.overrides = overrides.length ? overrides : [];
        } else {
          this.formData.defaultCred = newValue || '';
          this.formData.overrides = [];
        }
        // 默认凭证为空且列表已加载时，回落到凭证列表第一条
        if (!this.formData.defaultCred && this.credentialList.length) {
          this.formData.defaultCred = this.credentialList[0].name;
        }
      },
      addOverride() {
        this.formData.overrides.push({ scope: '', name: '' });
      },
      removeOverride(index) {
        this.formData.overrides.splice(index, 1);
        this.emitValue();
      },
      emitValue() {
        const obj = { default: this.formData.defaultCred || '' };
        this.formData.overrides.forEach((override) => {
          if (override.scope) {
            obj[override.scope] = override.name || '';
          }
        });
        this.lastEmittedValue = obj;
        this.$emit('change', obj);
      },
      goCredentialManage() {
        this.$router.push({
          name: 'spaceAdmin',
          query: {
            space_id: this.spaceId,
            activeTab: 'credential',
          },
        });
      },
      async validate() {
        if (!this.$refs.credentialForm) return true;
        try {
          await this.$refs.credentialForm.validate();
          return true;
        } catch (error) {
          return false;
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .credential-map {
    font-size: 12px;
  }
  .credential-warning {
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
    .to-credential-manage {
      color: #3a84ff;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      margin-left: 8px;
      .to-credential-manage-icon {
        margin-left: 5px;
      }
    }
  }
  .defalut-cred-form {
    margin-bottom: 24px;
  }
  ::v-deep .bk-form {
    .bk-form-item {
      margin: 6px 12px 6px 0px;
      .bk-label-text{
        font-size: 12px;
        font-weight: 700;
        line-height: 20px;
        color: #4d4f56;
      }
    }
  }
  .cm-select {
    width: 100%;
    max-width: 480px;
  }
  .cm-create {
    padding: 0 12px;
    line-height: 38px;
    color: #3a84ff;
    cursor: pointer;
  }
  .cm-dangling {
    display: block;
    color: #ea3636;
    margin-top: 4px;
    line-height: 20px;
  }
  .cm-overrides {
    width: 100%;
  }
  .cm-overrides-header {
    display: flex;
    align-items: center;
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;
  }
  .cm-scope-header {
    width: 280px;
    margin-right: 12px;
  }
  .cm-override-row {
    display: flex;
    align-items: center;
  }
  .cm-cell-scope{
    margin-right: 12px;
    ::v-deep .bk-form-input {
      width: 280px;
    }
  }
  .cm-cell-cred{
    ::v-deep .bk-select {
      width: 320px;
    }
  }
  .cm-del {
    font-size: 16px !important;
    color: #979ba5;
    cursor: pointer;
  }
  .cm-add-btn {
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    display: flex;
    align-items: center;
  }
  .cm-add-icon {
    font-size: 16px;
  }
</style>
