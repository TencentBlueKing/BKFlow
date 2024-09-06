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
  <bk-exception
    class="exception-wrap"
    type="500">
    <p class="title">
      {{ $t('访问异常') }}
    </p>
    <p class="sub-title">
      {{ $t('仅提供从已认证平台发起访问') }}
    </p>
    <p class="sub-title">
      {{ $t('不支持直接请求本系统页面') }}
    </p>
    <p class="sub-title">
      {{ $t('如有接入需求，请联系管理员') }}
    </p>
  </bk-exception>
</template>
<script>
  export default {
    name: 'ErrorCode403',
  };
</script>
<style lang="scss" scoped>
  .exception-wrap {
    /deep/.bk-exception-img {
      width: 440px;
      height: 200px;
    }
    .title {
      font-size: 24px;
      color: #313238;
      margin-bottom: 12px;
    }
    .sub-title {
      font-size: 14px;
      color: #63656e;
    }
  }
</style>
