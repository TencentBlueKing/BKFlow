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
  <div class="page-header">
    <span class="header-title">{{ $t('插件管理') }}</span>
    <div class="header-right">
      <div
        class="strategy-entry"
        @click="isStrategySliderShow = true">
        <i class="commonicon-icon common-icon-new new-icon" />
        <span class="entry-text">{{ $t('新插件策略') }}</span>
      </div>
    </div>
    <strategy-sideslider
      :visible.sync="isStrategySliderShow"
      :strategy="strategy"
      :categories="categories"
      @save="handleSave" />
  </div>
</template>

<script>
import StrategySideslider from './StrategySideslider.vue';
import { createDefaultStrategy } from './shared';


export default {
  name: 'PluginManageHeader',
  components: {
    StrategySideslider,
  },
  props: {
    strategy: {
      type: Object,
      default: createDefaultStrategy,
    },
    categories: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      isStrategySliderShow: false,
    };
  },
  methods: {
    handleSave(strategyDraft) {
      this.isStrategySliderShow = false;
      this.$emit('save', strategyDraft);
    },
  },
};
</script>

<style lang="scss" scoped>
.page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 52px;
    padding: 0 0 0 16px;
    background: #fff;
    box-shadow: 0 2px 4px 0 rgba(25, 25, 41, 0.08);
    position: relative;
    z-index: 1;
    flex-shrink: 0;

    .header-title {
        font-size: 16px;
        color: #313238;
    }

    .header-right {
        display: flex;
        align-items: center;
        align-self: stretch;
        .strategy-entry {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1px;
            height: 100%;
            padding: 0 16px;
            border-left: 1px solid #e4e9f2;
            cursor: pointer;
            .new-icon {
                font-size: 20px;
                color: #111214;
            }

            .entry-text {
                font-size: 12px;
                line-height: 20px;
                color: #111214;
            }
        }
    }
}
</style>
