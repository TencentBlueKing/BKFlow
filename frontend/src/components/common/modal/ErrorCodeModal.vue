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
  <bk-dialog
    width="600"
    ext-cls="error-content-dialog"
    header-position="left"
    :title="title"
    :mask-close="false"
    :show-footer="false"
    :value="isModalShow"
    @cancel="onCloseDialog">
    <div class="error-content">
      <div
        v-if="code === 500"
        class="pic-wrapper">
        <img
          :src="expPic500"
          class="error-pic"
          alt="error-pic">
      </div>
      <ErrorCode403 v-if="code === 403" />
      <ErrorCode500
        v-if="code === 500"
        :response-text="responseText" />
      <div
        v-if="code === 'default'"
        class="default-modal"
        v-html="filterXSS(responseText)" />
    </div>
  </bk-dialog>
</template>
<script>
  import ErrorCode403 from './ErrorCode403.vue';
  import ErrorCode500 from './ErrorCode500.vue';
  export default {
    name: 'ErrorCodeModal',
    components: {
      ErrorCode403,
      ErrorCode500,
    },
    data() {
      return {
        isModalShow: false,
        code: '',
        responseText: '',
        title: ' ',
        expPic500: require('@/assets/images/expre_500.png'),
      };
    },
    methods: {
      show(code, responseText, title = ' ') {
        this.code = code;
        this.responseText = responseText;
        this.isModalShow = true;
        this.title = title;
      },
      onCloseDialog() {
        this.isModalShow = false;
      },
    },
  };
</script>
<style lang="scss" scoped>
.error-content-dialog {
  z-index: 2501;
  .error-content {
    padding-bottom: 40px;
    ::v-deep .error-title {
      margin: 10px 0;
      font-weight: bold;
    }
    .pic-wrapper {
      text-align: center;
      .error-pic {
        width: 360px;
        height: 168px;
      }
    }
  }
}

</style>
