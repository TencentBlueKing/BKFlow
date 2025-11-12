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
    v-bkloading="{ isLoading: taskDataLoading, opacity: 1, zIndex: 100 }"
    class="task-execute-container">
    <template v-if="!taskDataLoading">
      <TaskOperation
        :space-id="spaceId"
        :instance-id="instanceId"
        :router-type="routerType"
        :instance-name="instanceName"
        :instance-flow="instanceFlow"
        :template-id="templateId"
        :primitive-tpl-id="primitiveTplId"
        :primitive-tpl-source="primitiveTplSource"
        :template-source="templateSource"
        :scope-info="scopeInfo"
        :create-method="createMethod"
        :canvas-mode="canvasMode"
        :instance-actions="instanceActions"
        :trigger-method="triggerMethod"
        :parent-task-info="parentTaskInfo" />
    </template>
  </div>
</template>
<script>
  import { mapMutations, mapActions } from 'vuex';
  import TaskOperation from './TaskOperation.vue';

  export default {
    name: 'TaskExecute',
    components: {
      TaskOperation,
    },
    props: {
      instanceId: {
        type: [Number, String],
        default: '',
      },
      common: {
        type: [Number, String],
        default: '',
      },
      routerType: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        taskDataLoading: true,
        isFunctional: this.routerType === 'function', // 是否为职能化任务
        showParamsFill: false, // 显示参数填写页面
        primaryTitle: '', // 浏览器tab页初始title
        instanceName: '',
        instanceFlow: '',
        templateSource: '',
        instanceActions: [],
        templateId: '',
        primitiveTplId: '', // 任务原始模板id
        primitiveTplSource: '', // 任务原始模板来源
        spaceId: 0,
        scopeInfo: {},
        createMethod: '',
        canvasMode: '',
        triggerMethod: '',
        parentTaskInfo: {},
      };
    },
    created() {
      const { spaceId } = this.$route.params;
      this.setSpaceId(Number(spaceId));
      this.getTaskData();
    },
    methods: {
      ...mapMutations([
        'setSpaceId',
      ]),
      ...mapMutations('template/', [
        'setPipelineTree',
      ]),
      ...mapActions('task/', [
        'getTaskInstanceData',
        'loadSubflowConfig',
      ]),
      async getTaskData() {
        try {
          this.taskDataLoading = true;
          const instanceData = await this.getTaskInstanceData(this.instanceId);
          const {
            current_flow: currentFlow,
            pipeline_tree: pipelineTree,
            name,
            template_id: templateId,
            template_source: templateSource,
            auth: authActions,
            primitive_template_id: primitiveTemplateId,
            primitive_template_source: primitiveTemplateSource,
            space_id: spaceId,
            scope_type: scopeType,
            scope_value: scopeValue,
            create_method: createMethod,
            trigger_method: triggerMethod,
            parent_task_info: parentTaskInfo,
          } = instanceData;
          if (this.isFunctional && currentFlow === 'func_claim') {
            this.showParamsFill = true;
          } else {
            this.primaryTitle = document.title;
            document.title = name;
          }
          // 判断是否存在子流程节点-如果存在需获取子流程的节点树
          for (const key of Object.keys(pipelineTree.activities)) {
            const currentItem = pipelineTree.activities[key];
            if (currentItem.component.code === 'subprocess_plugin') {
              const { template_id } = currentItem.component.data.subprocess.value;
              const params = {
                templateId: template_id,
                is_all_nodes: true,
              };
              const res = await this.loadSubflowConfig(params);
              currentItem.pipeline = res.data.pipeline_tree;
            }
          }
          this.instanceFlow = pipelineTree;
          this.instanceName = name;
          this.templateId = templateId;
          this.primitiveTplId = primitiveTemplateId;
          this.primitiveTplSource = primitiveTemplateSource;
          this.templateSource = templateSource;
          this.instanceActions = authActions;
          this.spaceId = spaceId;
          this.scopeInfo = { scope_type: scopeType, scope_value: scopeValue };
          this.canvasMode = pipelineTree.canvas_mode;
          this.createMethod = createMethod;
          this.triggerMethod = triggerMethod;
          this.parentTaskInfo = parentTaskInfo || {};
          // 将节点树存起来
          this.setPipelineTree(pipelineTree);
        } catch (e) {
          console.log(e);
        } finally {
          this.taskDataLoading = false;
        }
      },
    },
    // 离开任务执行页面时，还原页面的title、icon
    beforeRouteLeave(to, from, next) {
      document.title = this.primaryTitle;
      next();
    },
  };
</script>
<style lang="scss" scoped>
    .task-execute-container {
        height: 100%;
        background: #f4f7fa;
    }
    ::v-deep .canvas-comp-wrapper {
        .canvas-material-container {
          background: #f5f7fa;
        }
        .canvas-tools {
            left: 20px !important;
        }
    }
</style>
