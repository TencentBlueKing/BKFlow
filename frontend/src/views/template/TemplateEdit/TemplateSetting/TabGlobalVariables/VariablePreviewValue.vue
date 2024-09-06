/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
<template>
  <div
    v-bkloading="{ isLoading: loading, zIndex: 100 }"
    class="variable-preview-value">
    <div
      v-if="valueStr"
      class="content">
      {{ valueStr }}
    </div>
    <bk-alert
      v-else-if="!loading"
      type="warning"
      :title="$t('暂无数据')" />
  </div>
</template>
<script>
  import { mapActions } from 'vuex';

  export default {
    name: 'VariablePreviewValue',
    props: {
      keyId: {
        type: String,
        default: '',
      },
      params: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        valueStr: '',
        loading: false,
      };
    },
    created() {
      if (this.keyId) {
        this.getVariableValue();
      }
    },
    methods: {
      ...mapActions('template', [
        'getConstantsPreviewResult',
      ]),
      async getVariableValue() {
        try {
          this.loading = true;
          const resp = await this.getConstantsPreviewResult(this.params);
          if (resp.result) {
            this.valueStr = resp.data[this.keyId];
          }
        } catch (e) {
          console.log(e);
        } finally {
          this.loading = false;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
    .variable-preview-value {
        position: relative;
        margin: 10px 30px;
        background: #f0f1f5;
        border: 1px solid #dcdee5;
        border-radius: 2px;
        min-height: 50px;

        &:after {
            content: '';
            position: absolute;
            top: -5px;
            right: 260px;
            width: 8px;
            height: 8px;
            background: #f0f1f5;
            border-style: solid;
            border-width: 1px 1px 0 0;
            border-color: #dcdee5 #dcdee5 transparent transparent;
            transform: rotate(-45deg);
            border-radius: 1px;
        }
        .content {
            padding: 16px;
            max-height: 200px;
            word-break: break-all;
            overflow: auto;
        }
        .bk-alert-warning {
            margin: 8px;
        }
    }
</style>
