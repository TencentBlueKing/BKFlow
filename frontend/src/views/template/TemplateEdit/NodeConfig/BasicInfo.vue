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
  <div class="basic-info">
    <!-- 普通插件 -->
    <bk-form
      v-if="!isSubflow"
      ref="pluginForm"
      :label-width="130"
      :model="formData"
      :rules="pluginRules">
      <bk-form-item
        :label="isApiPlugin ? 'API' : $t('标准插件')"
        :required="true"
        property="plugin"
        class="choose-plugin-input">
        <bk-input
          :value="formData.name"
          readonly>
          <template slot="append">
            <div
              :class="['operate-btn', { 'is-disabled': isViewMode }]"
              @click="openSelectorPanel">
              {{ formData.plugin ? $t('重选') : $t('选择') }}
            </div>
          </template>
        </bk-input>
        <p
          v-if="formData.desc"
          class="plugin-info-desc"
          v-html="transformPluginDesc(formData.desc)" />
        <!-- API插件轮询提示 -->
        <p
          v-if="isApiPlugin && formData.polling"
          class="plugin-info-desc">
          {{ '当前 API 开启 Polling 轮询功能，如果 Polling 时间超过一天仍未结束，节点将自动失败' }}
        </p>
      </bk-form-item>
      <bk-form-item
        v-if="isApiPlugin"
        :label="$t('请求方法')"
        property="method"
        :required="true">
        <bk-select
          v-model="formData.method"
          :disabled="isViewMode">
          <bk-option
            v-for="option in formData.methodList"
            :id="option"
            :key="option"
            :name="option" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        v-else
        :label="$t('插件版本')"
        data-test-id="templateEdit_form_pluginVersion"
        :required="true"
        property="version">
        <bk-select
          v-model="formData.version"
          :clearable="false"
          :disabled="isViewMode"
          @selected="$emit('versionChange', $event)">
          <bk-option
            v-for="item in versionList"
            :id="item.version"
            :key="item.version"
            :name="item.version" />
        </bk-select>
      </bk-form-item>
      <bk-form-item
        :label="$t('节点名称')"
        data-test-id="templateEdit_form_nodeName"
        :required="true"
        property="nodeName">
        <bk-input
          v-model="formData.nodeName"
          :readonly="isViewMode"
          @change="updateData" />
      </bk-form-item>
      <!-- <bk-form-item :label="$t('步骤名称')" data-test-id="templateEdit_form_stageName" property="stageName">
        <bk-input :readonly="isViewMode" v-model="formData.stageName" @change="updateData"></bk-input>
      </bk-form-item> -->
      <!-- <bk-form-item :label="$t('节点标签')" data-test-id="templateEdit_form_nodeLabel" property="label">
                <bk-search-select
                    primary-key="code"
                    :ext-cls="isViewMode ? 'disabled-search' : ''"
                    :clearable="true"
                    :popover-zindex="2300"
                    :data="labelList"
                    :show-condition="false"
                    :show-popover-tag-change="false"
                    :values="filterLabelTree(formData.nodeLabel)"
                    @change="onLabelChange"
                    @clear="onLabelClear">
                </bk-search-select>
            </bk-form-item> -->
      <bk-form-item>
        <div
          slot="tip"
          class="bk-label slot-bk-label">
          <span
            v-bk-tooltips="errorHandleTipsConfig"
            class="form-item-tips">{{ $t('失败处理') }}</span>
        </div>
        <div class="error-handle">
          <bk-checkbox
            :value="formData.ignorable"
            :disabled="isViewMode || formData.autoRetry.enable || formData.timeoutConfig.enable"
            @change="onErrorHandlerChange($event, 'ignorable')">
            <span class="error-handle-icon"><span class="text">AS</span></span>
            {{ $t('自动跳过') }}
          </bk-checkbox>
          <bk-checkbox
            :value="formData.skippable"
            :disabled="isViewMode || formData.ignorable"
            @change="onErrorHandlerChange($event, 'skippable')">
            <span class="error-handle-icon"><span class="text">MS</span></span>
            {{ $t('手动跳过') }}
          </bk-checkbox>
          <bk-checkbox
            :value="formData.retryable"
            :disabled="isViewMode || formData.ignorable || formData.autoRetry.enable"
            @change="onErrorHandlerChange($event, 'retryable')">
            <span class="error-handle-icon"><span class="text">MR</span></span>
            {{ $t('手动重试') }}
          </bk-checkbox>
          <bk-checkbox
            :value="formData.autoRetry.enable"
            :disabled="isViewMode || formData.ignorable || formData.timeoutConfig.enable"
            @change="onErrorHandlerChange($event, 'autoRetry')">
            <span class="error-handle-icon"><span class="text">AR</span></span>
          </bk-checkbox>
          <span class="auto-retry-times">
            {{ $t('在') }}
            <div
              class="number-input"
              style="margin: 0 4px;">
              <bk-input
                v-model.number="formData.autoRetry.interval"
                type="number"
                style="width: 68px;"
                :placeholder="' '"
                :disabled="isViewMode || !formData.autoRetry.enable"
                :max="10"
                :min="0"
                :precision="0"
                @change="updateData" />
              <span class="unit">{{ $tc('秒', 0) }}</span>
            </div>
            {{ $t('后') }}{{ $t('，') }}{{ $t('自动重试') }}
            <div
              class="number-input"
              style=" margin-left: 4px;">
              <bk-input
                v-model.number="formData.autoRetry.times"
                type="number"
                style="width: 68px;"
                :placeholder="' '"
                :disabled="isViewMode || !formData.autoRetry.enable"
                :max="10"
                :min="1"
                :precision="0"
                @change="updateData" />
              <span class="unit">{{ $t('次') }}</span>
            </div>
          </span>
        </div>
        <p
          v-if="!formData.ignorable && !formData.skippable && !formData.retryable && !formData.autoRetry.enable"
          class="error-handle-tips">
          {{ $t('未选择失败处理方式，标准插件节点如果执行失败，会导致任务中断后不可继续') }}
        </p>
        <div
          id="html-error-ingored-tootip"
          class="tips-item"
          style="white-space: normal;">
          <p>{{ $t('自动跳过：标准插件节点如果执行失败，会自动忽略错误并把节点状态设置为成功。') }}</p><br>
          <p>{{ $t('手动跳过：标准插件节点如果执行失败，可以人工干预，直接跳过节点的执行。') }}</p><br>
          <p>{{ $t('手动重试：标准插件节点如果执行失败，可以人工干预，填写参数后重试节点。') }}</p><br>
          <p>{{ $t('自动重试：标准插件节点如果执行失败，系统会自动以原参数进行重试。') }}</p>
        </div>
      </bk-form-item>
      <bk-form-item :label="$t('超时控制')">
        <div class="timeout-setting-wrap">
          <bk-switcher
            theme="primary"
            size="small"
            style="margin-right: 8px;"
            :value="formData.timeoutConfig.enable"
            :disabled="isViewMode || formData.ignorable || formData.autoRetry.enable"
            @change="onTimeoutChange" />
          <template v-if="formData.timeoutConfig.enable">
            {{ $t('超时') }}
            <div
              class="number-input"
              style="margin: 0 4px;">
              <bk-input
                v-model.number="formData.timeoutConfig.seconds"
                type="number"
                style="width: 75px;"
                :placeholder="' '"
                :min="10"
                :max="maxNodeExecuteTimeout"
                :precision="0"
                :readonly="isViewMode"
                @change="updateData" />
              <span class="unit">{{ $tc('秒', 0) }}</span>
            </div>
            {{ $t('后') }}{{ $t('，') }}{{ $t('则') }}
            <bk-select
              v-model="formData.timeoutConfig.action"
              style="width: 160px; margin-left: 4px;"
              :disabled="isViewMode"
              :clearable="false"
              @change="updateData">
              <bk-option
                id="forced_fail"
                :name="$t('强制终止')" />
              <bk-option
                id="forced_fail_and_skip"
                :name="$t('强制终止后跳过')" />
            </bk-select>
          </template>
        </div>
      </bk-form-item>
      <!-- <bk-form-item :label="$t('是否可选')">
        <bk-switcher
          theme="primary"
          size="small"
          :value="formData.selectable"
          :disabled="isViewMode"
          @change="onSelectableChange">
        </bk-switcher>
      </bk-form-item>
      <bk-form-item v-if="common" :label="$t('执行代理人')" data-test-id="templateEdit_form_executor_proxy">
        <bk-user-selector
          :disabled="isViewMode"
          v-model="formData.executor_proxy"
          :placeholder="$t('请输入用户')"
          :api="userApi"
          :multiple="false"
          @change="onUserSelectChange">
        </bk-user-selector>
      </bk-form-item> -->
    </bk-form>
    <!-- 子流程 -->
    <bk-form
      v-else
      ref="subflowForm"
      :label-width="130"
      :model="formData"
      :rules="subflowRules">
      <bk-form-item
        :label="$t('流程模板')"
        :required="true"
        property="tpl">
        <bk-input
          :value="formData.name"
          readonly>
          <template slot="append">
            <div
              class="view-subflow">
              <JumpLinkBKFlowOrExternal
                v-if="basicInfo.tpl"
                :query="{ id:basicInfo.tpl, type:'template' }"
                :get-target-url="() => onViewSubflow(basicInfo.tpl)">
                <i class="bk-icon common-icon-box-top-right-corner" />
              </JumpLinkBKFlowOrExternal>
            </div>
            <div
              :class="['operate-btn', { 'is-disabled': isViewMode }]"
              @click="openSelectorPanel">
              {{ formData.tpl ? $t('重选') : $t('选择') }}
            </div>
          </template>
        </bk-input>
        <!-- 子流程版本更新 -->
        <p
          v-if="!inputLoading && subflowHasUpdate && !subflowUpdated"
          class="update-tooltip">
          <bk-icon
            type="exclamation-circle"
            class="icon-tip" />
          <span>{{ $t('子流程有更新，更新时若存在相同表单数据则获取原表单的值。') }}</span>
          <bk-button
            :text="true"
            title="primary"
            :disabled="isViewMode"
            @click="onUpdateSubflowVersion">
            {{ $t('更新子流程') }}
          </bk-button>
        </p>
      </bk-form-item>
      <bk-form-item
        :label="$t('节点名称')"
        :required="true"
        property="nodeName">
        <bk-input
          v-model="formData.nodeName"
          :readonly="isViewMode"
          @change="updateData" />
      </bk-form-item>
      <bk-form-item
        v-if="isEnableVersionManage"
        :label="$t('版本号')"
        :required="true"
        property="version">
        <bk-select
          ref="versionSelect"
          v-model="subVersionSelectValue"
          :disabled="isViewMode"
          ext-popover-cls="select-sub-version-popover-custom"
          :popover-min-width="577"
          :popover-width="577"
          :clearable="false"
          :placeholder="$t('请选择版本')"
          ext-cls="subflow-select"
          :searchable="subVersionlistData.length>0"
          @change="changeSubNodeVersion">
          <bk-option
            v-for="option in subVersionlistData"
            :id="option.version"
            :key="option.id"
            :name="option.version ?? '--'"
            :disabled="!(option.version == formData.latestVersion || option.version == initVersion)">
            <div class="option-title">
              <span>{{ option.version ? option.version : option.desc }}</span>
              <div
                v-if="option.version === formData.latestVersion"
                class="latest-version">
                <div class="text">
                  {{ $t('最新') }}
                </div>
              </div>
            </div>
            <div class="version-desc">
              <p
                v-bk-overflow-tips
                class="version-desc-text">
                {{ option.desc }}
              </p>
            </div>
          </bk-option>
        </bk-select>
        <div
          v-if="formData.latestVersion === formData.version "
          class="sub-latest-version">
          <div class="text">
            {{ $t('最新') }}
          </div>
        </div>
      </bk-form-item>
      <bk-form-item
        :label="$t('步骤名称')"
        property="stageName">
        <bk-input
          v-model="formData.stageName"
          :readonly="isViewMode"
          @change="updateData" />
      </bk-form-item>
      <template>
        <bk-form-item>
          <div
            slot="tip"
            class="bk-label slot-bk-label">
            <span
              v-bk-tooltips="errorHandleTipsConfig"
              class="form-item-tips">
              {{ $t('失败处理') }}
            </span>
          </div>
          <div class="error-handle">
            <bk-checkbox
              :value="formData.ignorable"
              :disabled="isViewMode || formData.autoRetry.enable || formData.timeoutConfig.enable"
              @change="onErrorHandlerChange($event, 'ignorable')">
              <span class="error-handle-icon"><span class="text">AS</span></span>
              {{ $t('自动跳过') }}
            </bk-checkbox>
            <bk-checkbox
              :value="formData.skippable"
              :disabled="isViewMode || formData.ignorable"
              @change="onErrorHandlerChange($event, 'skippable')">
              <span class="error-handle-icon"><span class="text">MS</span></span>
              {{ $t('手动跳过') }}
            </bk-checkbox>
            <bk-checkbox
              :value="formData.retryable"
              :disabled="isViewMode || formData.ignorable || formData.autoRetry.enable"
              @change="onErrorHandlerChange($event, 'retryable')">
              <span class="error-handle-icon"><span class="text">MR</span></span>
              {{ $t('手动重试') }}
            </bk-checkbox>
            <bk-checkbox
              :value="formData.autoRetry.enable"
              :disabled="isViewMode || formData.ignorable || formData.timeoutConfig.enable"
              @change="onErrorHandlerChange($event, 'autoRetry')">
              <span class="error-handle-icon"><span class="text">AR</span></span>
            </bk-checkbox>
            <span class="auto-retry-times">
              {{ $t('在') }}
              <div
                class="number-input"
                style="margin: 0 4px;">
                <bk-input
                  v-model.number="formData.autoRetry.interval"
                  type="number"
                  style="width: 68px;"
                  :placeholder="' '"
                  :disabled="isViewMode || !formData.autoRetry.enable"
                  :min="0"
                  :precision="0"
                  @change="updateData" />
                <span class="unit">{{ $tc('秒', 0) }}</span>
              </div>
              {{ $t('后') }}{{ $t('，') }}{{ $t('自动重试') }}
              <div
                class="number-input"
                style=" margin-left: 4px;">
                <bk-input
                  v-model.number="formData.autoRetry.times"
                  type="number"
                  style="width: 68px;"
                  :placeholder="' '"
                  :disabled="isViewMode || !formData.autoRetry.enable"
                  :min="0"
                  :precision="0"
                  @change="updateData" />
                <span class="unit">{{ $t('次') }}</span>
              </div>
            </span>
          </div>
          <p
            v-if="!formData.ignorable && !formData.skippable && !formData.retryable && !formData.autoRetry.enable"
            class="error-handle-tips">
            {{ $t('未选择失败处理方式，标准插件节点如果执行失败，会导致任务中断后不可继续') }}
          </p>
          <div
            id="html-error-ingored-tootip"
            class="tips-item"
            style="white-space: normal;">
            <p>{{ $t('自动跳过：标准插件节点如果执行失败，会自动忽略错误并把节点状态设置为成功。') }}</p><br>
            <p>{{ $t('手动跳过：标准插件节点如果执行失败，可以人工干预，直接跳过节点的执行。') }}</p><br>
            <p>{{ $t('手动重试：标准插件节点如果执行失败，可以人工干预，填写参数后重试节点。') }}</p><br>
            <p>{{ $t('自动重试：标准插件节点如果执行失败，系统会自动以原参数进行重试。') }}</p>
          </div>
        </bk-form-item>
        <!-- <bk-form-item :label="$t('超时控制')">
          <div class="timeout-setting-wrap">
            <bk-switcher
              theme="primary"
              size="small"
              style="margin-right: 8px;"
              :value="formData.timeoutConfig.enable"
              :disabled="isViewMode || formData.ignorable || formData.autoRetry.enable"
              @change="onTimeoutChange">
            </bk-switcher>
            <template v-if="formData.timeoutConfig.enable">
              {{ $t('超时') }}
              <div class="number-input" style="margin: 0 4px;">
                <bk-input
                  v-model.number="formData.timeoutConfig.seconds"
                  type="number"
                  style="width: 75px;"
                  :placeholder="' '"
                  :min="10"
                  :max="maxNodeExecuteTimeout"
                  :precision="0"
                  :readonly="isViewMode"
                  @change="updateData">
                </bk-input>
                <span class="unit">{{ $tc('秒', 0) }}</span>
              </div>
              {{ $t('后') }}{{ $t('，') }}{{ $t('则') }}
              <bk-select
                style="width: 160px; margin-left: 4px;"
                v-model="formData.timeoutConfig.action"
                :disabled="isViewMode"
                :clearable="false" @change="updateData">
                <bk-option id="forced_fail" :name="$t('强制终止')"></bk-option>
                <bk-option id="forced_fail_and_skip" :name="$t('强制终止后跳过')"></bk-option>
              </bk-select>
            </template>
          </div>
          <p v-if="formData.timeoutConfig.enable" class="error-handle-tips" style="margin-top: 6px;">
            {{ $t('该功能仅对V2引擎生效') }}
          </p>
        </bk-form-item> -->
      </template>
      <!-- <bk-form-item :label="$t('是否可选')">
        <bk-switcher
          theme="primary"
          size="small"
          :disabled="isViewMode"
          :value="formData.selectable"
          @change="onSelectableChange">
        </bk-switcher>
      </bk-form-item> -->
      <bk-form-item>
        <div
          slot="tip"
          class="bk-label slot-bk-label">
          <span
            v-bk-tooltips="alwaysUseLastestTipsConfig"
            class="form-item-tips">
            {{ $t('总是使用最新版本') }}
          </span>
        </div>
        <bk-switcher
          theme="primary"
          size="small"
          :disabled="isViewMode"
          :value="formData.alwaysUseLatest"
          @change="onAlwaysUseLatestChange" />
        <div
          id="html-always-use-latest-tootip"
          class="tips-item"
          style="white-space: normal;">
          <p>{{ $t('打开此功能后，每次创建任务会尝试使用子流程的最新版本，并且不会再提示该节点需要更新。') }}</p><br>
          <p>{{ $t('若子流程中发生变动，标准运维会采用以下处理策略，如处理不符合预期，请谨慎使用。') }}</p><br>
          <p>{{ $t('1. 若子流程中增加了新的变量，在未手动更新子流程版本的情况下，将使用新变量默认值。') }}</p><br>
          <p>{{ $t('2. 若子流程中修改了变量的默认值，在未手动更新子流程版本的情况下，将继续使用修改前变量的原有值。') }}</p>
        </div>
      </bk-form-item>
      <bk-form-item
        :label="$t('执行控制')"
        :required="true"
        property="executeControl">
        <div class="bk-button-group">
          <bk-button
            :class="executeControlActive === 'single' ? 'is-selected' : ''"
            :disabled="isViewMode"
            @click="onExecuteControlChange('single')">
            {{ $t('单次执行') }}
          </bk-button>
          <bk-button
            :class="executeControlActive === 'loop' ? 'is-selected' : ''"
            :disabled="isViewMode"
            @click="onExecuteControlChange('loop')">
            {{ $t('循环执行') }}
          </bk-button>
          <!-- 一期先不做 -->
          <!-- <bk-button
            :class="executeControlActive === 'batch' ? 'is-selected' : ''"
            :disabled="isViewMode"
            @click="onExecuteControlChange('batch')">
            {{ $t('批量执行') }}
          </bk-button> -->
        </div>
      </bk-form-item>
      <bk-form-item
        v-if="executeControlActive !== 'single'"
        :label="$t('循环类型')"
        :required="true"
        property="loopType">
        <div class="execute-control-config">
          <LoopExecutionConfig
            v-if="executeControlActive === 'loop'"
            ref="loopExecutionConfigRef"
            :loop-config="formData.loopConfig"
            :is-view-mode="isViewMode"
            @change="onLoopConfigChange" />
          <!-- <div
            v-if="executeControlActive === 'batch'"
            class="batch-config">
            <div class="batch-config-count">
              <span class="count-label">{{ $t('最大并行数') }}</span>
              <bk-slider
                v-model="formData.loopConfig"
                class="count-slider"
                :show-input="true" />
            </div>
            <LoopVar
              :is-view-mode="isViewMode"
              :var-list="formData.loopConfig"
              @change="onBatchVarListChange" />
          </div> -->
        </div>
      </bk-form-item>
      <bk-form-item
        v-if="executeControlActive === 'loop'"
        :label="$t('循环控制')">
        <div class="loop-control">
          <bk-checkbox
            v-model="formData.loopConfig.fail_skip"
            @change="onLoopControlChange" />
          <span class="control-text">{{ $t('循环内失败跳过') }}</span>
        </div>
      </bk-form-item>
      <!-- <bk-form-item v-if="common" :label="$t('执行代理人')" data-test-id="templateEdit_form_executor_proxy">
        <bk-user-selector
          :disabled="isViewMode"
          v-model="formData.executor_proxy"
          :placeholder="$t('请输入用户')"
          :api="userApi"
          :multiple="false"
          @change="onUserSelectChange">
        </bk-user-selector>
      </bk-form-item> -->
    </bk-form>
  </div>
</template>
<script>
  import i18n from '@/config/i18n/index.js';
  import tools from '@/utils/tools.js';
  // import BkUserSelector from '@blueking/user-selector'
  import { mapState, mapActions, mapMutations, mapGetters } from 'vuex';
  import { NAME_REG, STRING_LENGTH, INVALID_NAME_CHAR } from '@/constants/index.js';
  import JumpLinkBKFlowOrExternal from '@/components/common/JumpLinkBKFlowOrExternal.vue';
  import LoopExecutionConfig from './LoopTypeInfo/LoopExecutionConfig.vue';
  // import LoopVar from './LoopTypeInfo/LoopVar.vue';

  export default {
    name: 'BasicInfo',
    components: {
      // BkUserSelector,
      JumpLinkBKFlowOrExternal,
      LoopExecutionConfig,
      // LoopVar,
    },
    props: {
      projectId: {
        type: [String, Number],
        default: '',
      },
      nodeConfig: {
        type: Object,
        default: () => ({}),
      },
      basicInfo: {
        type: Object,
        default: () => ({}),
      },
      versionList: {
        type: Array,
        default: () => ([]),
      },
      isSubflowNeedToUpdate: {
        type: Boolean,
        default: false,
      },
      isSubflow: Boolean,
      inputLoading: Boolean,
      subflowUpdated: Boolean,
      common: {
        type: [String, Number],
        default: '',
      },
      isViewMode: Boolean,
      isApiPlugin: Boolean,
      isEnableVersionManage: Boolean,
      spaceId: {
        type: [String, Number],
        default: '',
      },
    },
    data() {
      return {
        labelData: [],
        labelLoading: false,
        subflowLoading: false,
        version: this.basicInfo.version,
        formData: tools.deepClone(this.basicInfo),
        initVersion: tools.deepClone(this.basicInfo.version),
        maxNodeExecuteTimeout: window.MAX_NODE_EXECUTE_TIMEOUT,
        schemeList: [],
        schemeListLoading: true,
        pluginRules: {
          plugin: [
            {
              required: true,
              message: i18n.t('请选择插件'),
              trigger: 'blur',
            },
          ],
          version: [
            {
              required: true,
              message: i18n.t('请选择插件版本'),
              trigger: 'blur',
            },
          ],
          nodeName: [
            {
              required: true,
              message: i18n.t('节点名称不能为空'),
              trigger: 'blur',
            },
            {
              regex: NAME_REG,
              message: i18n.t('节点名称不能包含') + INVALID_NAME_CHAR + i18n.t('非法字符'),
              trigger: 'blur',
            },
            {
              max: STRING_LENGTH.TEMPLATE_NODE_NAME_MAX_LENGTH,
              message: i18n.t('节点名称长度不能超过') + STRING_LENGTH.TEMPLATE_NODE_NAME_MAX_LENGTH + i18n.t('个字符'),
              trigger: 'blur',
            },
          ],
          stageName: [
            {
              max: STRING_LENGTH.STAGE_NAME_MAX_LENGTH,
              message: i18n.t('步骤名称长度不能超过') + STRING_LENGTH.STAGE_NAME_MAX_LENGTH + i18n.t('个字符'),
              trigger: 'blur',
            },
          ],
        },
        subflowRules: {
          tpl: [
            {
              required: true,
              message: i18n.t('请选择流程模板'),
              trigger: 'blur',
            },
          ],
          nodeName: [
            {
              required: true,
              message: i18n.t('节点名称不能为空'),
              trigger: 'blur',
            },
            {
              regex: NAME_REG,
              message: i18n.t('节点名称不能包含') + INVALID_NAME_CHAR + i18n.t('非法字符'),
              trigger: 'blur',
            },
            {
              max: STRING_LENGTH.TEMPLATE_NODE_NAME_MAX_LENGTH,
              message: i18n.t('节点名称长度不能超过') + STRING_LENGTH.TEMPLATE_NODE_NAME_MAX_LENGTH + i18n.t('个字符'),
              trigger: 'blur',
            },
          ],
          stageName: [
            {
              max: STRING_LENGTH.STAGE_NAME_MAX_LENGTH,
              message: i18n.t('步骤名称长度不能超过') + STRING_LENGTH.STAGE_NAME_MAX_LENGTH + i18n.t('个字符'),
              trigger: 'blur',
            },
          ],
        },
        errorHandleTipsConfig: {
          allowHtml: true,
          theme: 'light',
          extCls: 'info-label-tips',
          content: '#html-error-ingored-tootip',
          placement: 'top-start',
        },
        alwaysUseLastestTipsConfig: {
          allowHtml: true,
          theme: 'light',
          extCls: 'info-label-tips',
          content: '#html-always-use-latest-tootip',
          placement: 'top-start',
        },
        userApi: `${window.MEMBER_SELECTOR_DATA_HOST}/api/c/compapi/v2/usermanage/fs_list_users/`,
        subflowVersion: '',
        subVersionSelectValue: '',
        subVersionlistData: [],
        executeControlActive: 'single',
      };
    },
    computed: {
      ...mapState({
        subprocessInfo: state => state.template.subprocess_info,
      }),
      subflowHasUpdate() {
        if (!this.formData.alwaysUseLatest) {
          return this.version !== this.basicInfo.version || this.subprocessInfo.some((subflow) => {
            let result = false;
            if (
              subflow.expired
              && subflow.subprocess_template_id === Number(this.formData.tpl)
              && subflow.subprocess_node_id === this.nodeConfig.id
            ) {
              result = true;
            }
            return result;
          });
        }
        return false;
      },
      labelList() {
        if (this.labelLoading || this.labelData.length === 0) {
          return [];
        }
        return this.labelData.filter(groupItem => !this.formData.nodeLabel.find(item => groupItem.code === item.group));
      },
    },
    watch: {
      basicInfo: {
        handler(val) {
          this.formData = tools.deepClone(val);
          if (this.formData.loopConfig && Object.keys(this.formData.loopConfig).length > 0) {
            if (this.formData.loopConfig.enable) {
              this.executeControlActive = 'loop';
            } else {
              this.executeControlActive = 'single';
            }
          } else {
            // 初始化执行控制数据结构
            this.formData.loopConfig = {
              enable: false,
              type: 'array_loop', // 数组循环array_loop 次数循环time_loop
              loop_times: 3, // 默认为3
              loop_params: [{ name: '', source: '' }],
              fail_skip: false,
            };
            this.executeControlActive = 'single';
          }
          if (this.formData.loopConfig.loop_params && !Array.isArray(this.formData.loopConfig.loop_params)) {
              this.formData.loopConfig.loop_params = Object.entries(this.formData.loopConfig.loop_params).map(([key, value]) => ({
                name: key,
                source: value,
              }));
          }
          // 如果有执行方案，默认选中<不使用执行方案>
          if (this.schemeList.length && !this.formData.schemeIdList.length) {
            this.formData.schemeIdList = [0];
          }
          if (this.isSubflow) {
            this.version = this.basicInfo.latestVersion;
          }
        },
        deep: true,
        immediate: true,
      },
      // 'formData.loopConfig.batch.batchLoopCount': {
      //   handler(newVal, oldVal) {
      //     if (newVal !== oldVal) {
      //       this.updateData();
      //     }
      //   },
      // },
    },
    mounted() {
      if (this.isSubflow) {
        this.getSubVersionList();
      }
    },
    methods: {
      ...mapMutations('template/', [
        'setNodeBasicInfo',
      ]),
      ...mapActions('task', [
        'loadTaskScheme',
        'loadSubflowConfig',
      ]),
      ...mapActions('template/', [
        'getLabels',
        'getProcessOpenRetryAndTimeout',
        'getTemplateVersionSnapshotList',
      ]),
      ...mapGetters('template/', [
        'getPipelineTree',
      ]),
      // 修改子流程版本
      changeSubNodeVersion(val) {
        this.$emit('changeSubNodeVersion', { id: this.formData.tpl, version: val });
      },
      async getSubVersionList() {
        try {
          const res = await this.getTemplateVersionSnapshotList({ template_id: this.formData.tpl, space_id: this.spaceId });
          this.subVersionlistData = res.data.results.filter(item => item.version);
        } catch (e) {
          console.log(e);
          this.subVersionlistData = [];
        }
      },
      // 加载子流程详情，拿到最新版本子流程的version字段
      async getSubflowDetail() {
        this.subflowLoading = true;
        try {
          const data = {
              templateId: this.basicInfo.tpl,
              is_all_nodes: true,
          };
          const resp = await this.loadSubflowConfig(data);
          this.version = resp.data.version;
        } catch (e) {
          console.log(e);
        } finally {
          this.subflowLoading = false;
        }
      },
      // 加载节点标签列表
      async getNodeLabelList() {
        try {
          this.labelLoading = true;
          const resp = await this.getLabels();
          this.labelData = this.transLabelListToGroup(resp.results);
        } catch (e) {
          console.log(e);
        } finally {
          this.labelLoading = false;
        }
      },

      // 标签分组
      transLabelListToGroup(list) {
        const data = [];
        const groups = [];
        list.forEach((item) => {
          const index = groups.findIndex(code => code === item.group.code);
          if (index > -1) {
            data[index].children.push(item);
          } else {
            const { code, name } = item.group;
            data.push({
              code,
              name,
              children: [{ ...item }],
            });
            groups.push(item.group.code);
          }
        });
        return data;
      },
      /**
       * 由节点保存的标签数据格式，转换成 searchSelect 组件要求的 values 格式
       */
      filterLabelTree(val) {
        // 等待节点标签列表加载完成，再做筛选
        if (this.labelLoading) {
          return [];
        }

        const data = [];
        val.forEach((item) => {
          const group = this.labelData.find(g => g.code === item.group);
          const label = group.children.find(l => l.code === item.label);
          data.push({
            code: group.code,
            name: group.name,
            values: [
              {
                code: label.code,
                name: label.name,
              },
            ],
          });
        });
        return data;
      },
      openSelectorPanel() {
        if (this.isViewMode) return;
        this.$emit('openSelectorPanel');
      },
      onLabelChange(list) {
        const val = [];
        list.forEach((item) => {
          if (item.values && item.values.length > 0) {
            val.push({
              label: item.values[0].code,
              group: item.code,
            });
          }
        });
        this.formData.nodeLabel = val;
        this.updateData();
      },
      onLabelClear() {
        this.formData.nodeLabel = [];
        this.updateData();
      },
      onErrorHandlerChange(val, type) {
        this.formData.autoRetry.interval = 0;
        this.formData.autoRetry.times = 1;
        if (type === 'autoRetry') {
          this.formData.autoRetry.enable = val;
          this.formData.retryable = true;
        } else {
          if (type === 'retryable') {
            this.formData.autoRetry.enable = false;
            this.formData.autoRetry.interval = 0;
            this.formData.autoRetry.times = 1;
          }
          if (type === 'ignorable' && val) {
            this.formData.skippable = true;
            this.formData.retryable = false;
            this.formData.autoRetry.enable = false;
          }
          this.formData[type] = val;
        }
        if (val && ['autoRetry', 'ignorable'].includes(type)) {
          this.formData.timeoutConfig = {
            enable: false,
            seconds: 10,
            action: 'forced_fail',
          };
        }
        this.updateData();
      },
      onTimeoutChange(val) {
        this.formData.timeoutConfig = {
          enable: val,
          seconds: 10,
          action: 'forced_fail',
        };
        if (val) {
          this.formData.ignorable = false;
          this.formData.autoRetry.enable = false;
        }
        this.updateData();
      },
      onSelectableChange(val) {
        this.formData.selectable = val;
        this.updateData();
      },
      onUserSelectChange(tags) {
        this.formData.executor_proxy = tags;
        this.updateData();
      },
      async onAlwaysUseLatestChange(val) {
        this.formData.alwaysUseLatest = val;
        if (!val) {
          await this.getSubflowDetail();
        }
        this.updateData();
      },
      updateData() {
        const {
          version, nodeName, stageName, nodeLabel, ignorable, skippable, retryable,
          selectable, alwaysUseLatest, autoRetry, timeoutConfig, schemeIdList, executor_proxy,
          loopConfig,
        } = this.formData;
        let data;
        if (this.isSubflow) {
          data = {
            nodeName,
            stageName,
            nodeLabel,
            selectable,
            alwaysUseLatest,
            schemeIdList,
            latestVersion: this.version,
            executor_proxy,
            retryable,
            autoRetry,
            timeoutConfig,
            skippable,
            loopConfig,
          };
        } else {
          data = {
            version,
            nodeName,
            stageName,
            nodeLabel,
            ignorable,
            skippable,
            retryable,
            selectable,
            autoRetry,
            timeoutConfig,
            executor_proxy,
          };
        }
        this.$emit('update', data);
      },
      /**
       * 子流程版本更新
       */
      onUpdateSubflowVersion() {
        if (this.inputLoading) {
          return;
        }

        this.$emit('updateSubflowVersion');
      },
      validate() {
        if (this.isSubflow) {
          this.$refs.subflowForm.clearError();
          if (this.$refs.loopExecutionConfigRef) {
            return this.$refs.subflowForm.validate() && this.$refs.loopExecutionConfigRef.validate();
          }
          return this.$refs.subflowForm.validate();
        }
          this.$refs.pluginForm.clearError();
          return this.$refs.pluginForm.validate();
      },
      transformPluginDesc(data) {
        const info = data.replace(/\n/g, '<br>');
        return this.filterXSS(info, {
          whiteList: {
            br: [],
          },
        });
      },
      onViewSubflow(id) {
        const pathData = {
          name: 'templatePanel',
          params: {
            templateId: id,
            type: 'view',
          },
        };
        const { href } = this.$router.resolve(pathData);
        return href;
      },
      // 执行控制类型变化处理
      onExecuteControlChange(type) {
        if (this.isViewMode) return;
        this.executeControlActive = type;
        if (type === 'loop') {
          this.formData.loopConfig.enable = true;
        } else {
          this.formData.loopConfig.enable = false;
        }
        this.updateData();
      },
      // 循环执行配置变化
      onLoopConfigChange(newConfig) {
        this.formData.loopConfig = newConfig;
        this.updateData();
      },
      onLoopControlChange() {
        this.updateData();
      },
      // 批量执行配置变化
      // onBatchVarListChange(list) {
      //   this.formData.loopConfig.batch.params = list;
      //   this.updateData();
      // },
    },
  };
</script>
<style lang="scss">
    .info-label-tips {
        max-width: 480px;
        .tippy-tooltip {
            color: #63656e;
            border: 1px solid #dcdee5;
            box-shadow: 0 0 5px 0 rgba(0,0,0,0.09);
        }
    }
</style>
<style lang="scss" scoped>
    .basic-info {
        padding-right: 30px;
    }
    .disabled-search {
        position: relative;
        cursor: not-allowed;
        ::v-deep .bk-search-select {
            border-color: #dcdee5 !important;
            background-color: #fafbfd !important;
        }
        &::after {
            content: '';
            height: 100%;
            width: 100%;
            position: absolute;
            top: 0;
            left: 0;
        }
    }
    .error-handle {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        height: 32px;
        ::v-deep .bk-form-checkbox {
            &:not(:last-of-type) {
                margin-right: 8px;
            }
            &.is-disabled .bk-checkbox-text {
                color: #c4c6cc;
            }
            &.is-checked .bk-checkbox-text {
                color: #606266;
            }
        }
        .error-handle-icon {
            display: inline-block;
            line-height: 12px;
            color: #ffffff;
            background: #979ba5;
            border-radius: 2px;
            .text {
                display: inline-block;
                font-size: 12px;
                transform: scale(0.8);
            }
        }
        .auto-retry-times {
            display: inline-flex;
            align-items: center;
            margin-left: 4px;
            height: 32px;
            font-size: 12px;
            color: #606266;
        }
    }
    .error-handle-tips {
        font-size: 12px;
        line-height: 1;
        color: #ffb400;
        margin-top: 2px;
    }
    .timeout-setting-wrap {
        display: flex;
        align-items: center;
        height: 32px;
        font-size: 12px;
        color: #63656e;
    }
    .number-input {
        position: relative;
        .unit {
            position: absolute;
            right: 8px;
            top: 1px;
            height: 30px;
            line-height: 30px;
            color: #999999;
            background: transparent;
        }
    }
    .loop-control{
      display: flex;
      align-items: center;
      font-size: 12px;
      color: #63656e;
      .control-text{
        margin-left: 5px;
      }
    }
    .auto-retry-times,
    .timeout-setting-wrap {
        ::v-deep .bk-input-number .input-number-option {
            display: none;
        }
    }
    ::v-deep .bk-form {
        .bk-label {
            font-size: 12px;
        }
        .bk-checkbox-text {
            font-size: 12px;
            color: #63656e;
        }
        .bk-form-control .group-box.group-append {
            display: flex;
            margin-left: -1px;
            background: #e1ecff;
            border: none;
            z-index: 11;
        }
        .slot-bk-label {
            position: absolute;
            top: 0;
            left: -150px;
            .form-item-tips {
                position: relative;
                line-height: 21px;
                &::after {
                    content: '';
                    position: absolute;
                    left: 0;
                    bottom: -3px;
                    border-top: 1px dashed #979ba5;
                    width: 100%
                }
            }
        }
        .view-subflow {
            display: flex;
            padding: 0 10px;
            justify-content: center;
            align-items: center;
            font-size: 12px;
            color: #63656e;
            background: #fafbfd;
            border-top: 1px solid #dcdee5;
            border-bottom: 1px solid #dcdee5;
            cursor: pointer;
            &:hover {
                color: #3a84ff;
            }
        }
        .operate-btn {
            display: inline-block;
            width: 58px;
            height: 32px;
            line-height: 32px;
            font-size: 12px;
            color: #3a84ff;
            text-align: center;
            border: 1px solid #3a84ff;
            cursor: pointer;
            &.is-disabled {
                border-color: #c4c6cc;
                color: #c4c6cc;
                cursor: not-allowed;
            }
        }
        .choose-plugin-input {
            .bk-form-input[readonly] {
                border-color: #c4c6cc !important;
            }
        }
        .plugin-info-desc {
            margin-top: 8px;
            font-size: 12px;
            color: #ff9c01;
            line-height: 1.2;
        }
        .update-tooltip {
            position: relative;
            top: 5px;
            color: #EA3636;
            font-size: 12px;
            line-height: 12px;
            .bk-button-text {
                font-size: 12px;
            }
            .icon-tip{
                font-size: 14px !important;
            }
        }
        .user-selector {
            width: 100%;
            .disabled::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                height: 100%;
                width: 100%;
                cursor: not-allowed;
            }
        }
    }

    .bk-button-group {
        display: inline-flex;

        .bk-button {
            border-radius: 0;
            margin-left: -1px;
            width: 120px;
            font-size: 12px;

            &:first-child {
                border-top-left-radius: 2px;
                border-bottom-left-radius: 2px;
                margin-left: 0;
            }

            &:last-child {
                border-top-right-radius: 2px;
                border-bottom-right-radius: 2px;
            }
        }
    }

    .execute-control-config {
        .batch-config {
          .batch-config-count {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            color: #63656E;
            .count-label{
              font-size: 12px;
              margin-right: 8px;
            }
            .count-slider{
              flex: 1;
            }
          }
        }
    }

    .bk-option-content {
        &:hover {
            .open-link-icon {
                display: inline-block;
            }
        }
        .open-link-icon {
            display: none;
            float: right;
            margin-top: 10px;
        }
    }
    .select-sub-version-popover-custom{
    .bk-options-wrapper{
        max-height: 261px !important;
    }
    .option-title{
       display: flex;
       align-items: center;
    }
    .latest-version{
        font-size: 10px;
        color: #14A568;
        line-height: 16px;
        background: #E4FAF0;
        border: 1px solid #A5E0C6;
        border-radius: 2px;
        margin-left: 15px;
        .text{
            padding: 0px 4px;
        }
    }
    .bottom-view-btn{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 5px 0;
      cursor: pointer;
      .common-icon-box-top-right-corner{
        margin-right: 8px;
        margin-top: 3px;
      }
    }
}
.sub-latest-version{
  position: absolute;
  left: 40px;
  top: 7px;
  font-size: 10px;
  color: #14A568;
  line-height: 16px;
  background: #E4FAF0;
  border: 1px solid #A5E0C6;
  border-radius: 2px;
  margin-left: 8px;
  .text{
      padding: 0px 4px;
  }
}
</style>
