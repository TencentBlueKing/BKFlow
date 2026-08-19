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
import axios from 'axios';
import store from '@/store/index.js';

const task = {
  namespaced: true,
  state: {
    subActivities: {},
    nodeDetailActivityPanel: 'record',
  },
  actions: {
    /**
     * 获取任务可选节点的选择方案
     * @param {Object} data 筛选条件
     */
    loadTaskScheme({}, payload) {
      const { isCommon, project_id: projectId, template_id } = payload;
      const params = { template_id };
      if (isCommon) {
        params.template_type = 'common';
      } else {
        params.project_id = projectId;
      }
      return axios.get('api/v3/scheme/', { params }).then((response) => {
        const { data } = response.data;
        return data;
      });
    },
    /**
     * 创建任务可选节点的选择方案
     * @param {Object}} payload 方案配置数据
     */
    createTaskScheme({}, payload) {
      const { isCommon, project_id: projectId, template_id, data, name } = payload;
      const params = {
        template_id,
        data,
        name,
      };
      if (isCommon) {
        params.template_type = 'common';
      } else {
        params.project_id = projectId;
      }
      return axios.post('api/v3/scheme/', params).then(response => response.data);
    },
    /**
     * 删除任务节点选择方案
     * @param {String} payload 方案参数
     */
    deleteTaskScheme({}, payload) {
      const { isCommon, id } = payload;
      const params = {};
      if (isCommon) {
        params.template_type = 'common';
      }

      return axios.delete(`api/v3/scheme/${id}/`, { params }).then(response => response.data);
    },
    /**
     * 获取任务节点选择方案详情
     * @param {String} payload 方案参数
     */
    getSchemeDetail({}, payload) {
      const { isCommon, id } = payload;
      const params = {};
      if (isCommon) {
        params.template_type = 'common';
      }

      return axios.get(`api/v3/scheme/${id}/`, { params }).then(response => response.data.data);
    },
    /**
     * 保存所有执行方案
     * @param {String} payload 方案参数
     */
    saveTaskSchemList({}, payload) {
      const { project_id: projectId, template_id, schemes, isCommon } = payload;
      const params = {
        template_id,
        schemes,
      };
      if (isCommon) {
        params.template_type = 'common';
      } else {
        params.project_id = projectId;
      }
      return axios.post('api/v3/scheme/batch_operate/', params).then(response => response.data);
    },
    /**
     * 获取默认执行方案列表
     * @param {String} payload 方案参数
     */
    getDefaultTaskScheme({}, payload) {
      const { project_id, template_id, template_type } = payload;
      const params = {
        template_id,
        project_id,
        template_type,
      };
      return axios.get('template/api/default_scheme/', { params }).then(response => response.data);
    },
    /**
     * 保存默认执行方案列表
     * @param {String} payload 方案参数
     */
    saveDefaultScheme({}, payload) {
      const { project_id, template_id, scheme_ids, template_type } = payload;
      const params = {
        template_id,
        project_id,
        template_type,
        scheme_ids,
      };
      return axios.post('template/api/default_scheme/', params).then(response => response.data);
    },
    /**
     * 更新默认执行方案列表
     * @param {String} payload 方案参数
     */
    updateDefaultScheme({}, payload) {
      const { project_id, template_id, scheme_ids, id, template_type } = payload;
      const params = {
        template_id,
        project_id,
        template_type,
        scheme_ids,
      };
      return axios.put(`template/api/default_scheme/${id}/`, params).then(response => response.data);
    },
    /**
     * 删除默认执行方案列表
     * @param {String} payload 方案参数
     */
    deleteDefaultScheme({}, payload) {
      const { id } = payload;
      return axios.delete(`template/api/default_scheme/${id}/`).then(response => response.data);
    },
    /**
     * 加载子流程详情
     * @param {String} data.projectId 项目id
     * @param {String} data.templateId 流程id
     * @param {String} data.version 流程版本
     * @param {String} data.common 是否为公共流程
     * @param {Array} data.scheme_id_list 执行方案列表
     */
    loadSubflowConfig({}, data) {
      return axios.post(`/api/template/${data.templateId}/preview_task_tree/`, data).then(response => response.data);
    },
    /**
     * 获取任务节点预览数据
     * @param {Object} payload 筛选条件
     */
    loadPreviewNodeData({}, payload) {
      const { project_id: projectId } = store.state.project;
      const { templateId, excludeTaskNodesId, common, version } = payload;
      const dataJson = {
        version,
        template_id: templateId,
        exclude_task_nodes_id: excludeTaskNodesId,
        template_source: 'project',
      };
      if (common) {
        dataJson.template_source = 'common';
      }

      return axios.post(`taskflow/api/preview_task_tree/${projectId}/`, dataJson).then(response => response.data);
    },
    /**
     * 资源筛选配置方案全量列表
     * @param {String} payload 资源类型
     */
    configProgramList({}, payload) {
      const { project_id: projectId } = store.state.project;
      return axios.get(`api/v3/resource_config/?project_id=${projectId}&config_type=${payload}`).then(response => response.data);
    },
    /**
     * 保存筛选方案
     * @param {String} params 项目信息数据
     */
    saveResourceScheme({}, params) {
      const { url, data } = params;
      return axios.patch(url, data).then(response => response.data);
    },
    createResourceScheme({}, params) {
      const { url, data } = params;
      return axios.post(url, data).then(response => response.data);
    },
    /**
     * 创建任务
     * @param {Object} data 模板数据
     */
    createTask({}, data) {
      const { spaceId, params } = data;
      return axios.post(`/api/template/admin/create_task/${spaceId}/`, params).then(response => response.data);
    },
    /**
     * 获取任务实例详细数据
     * @param {String} instanceId 实例id
     */
    getTaskInstanceData({}, instanceId) {
      return axios.get(`task/get_task_detail/${instanceId}/`, {
        params: { space_id: store.state.spaceId },
      }).then(response => response.data.data);
    },
    /**
     * 职能化认领
     * @param {String} data 模板数据
     */
    claimFuncTask({}, data) {
      const { name, instance_id, constants, project_id: projectId } = data;
      const requestData = {
        name,
        instance_id,
        constants,
      };
      return axios.post(`taskflow/api/flow/claim/${projectId}/`, requestData).then(response => response.data);
    },
    /**
     * 获取任务执行状态
     * @param {Object} 实例数据
     * @returns Object
     */
    getTaskStatus({}, data) {
      return axios.post('task_admin/get_tasks_states/', data).then(response => response.data);
    },
    /**
     * 获取任务实例状态信息(包含子流程状态)
     * @param {String} data 实例数据
     */
    getInstanceStatus({}, data) {
      const { instance_id: instanceId, cancelToken } = data;
      return axios.get(`task/get_task_states/${instanceId}/`, {
        params: { space_id: store.state.spaceId },
      }, {
        cancelToken,
      }).then(response => response.data);
    },
    /**
     * 开始执行任务实例
     * @param {String} instanceId 实例id
     */
    instanceStart({}, instanceId) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/action/start/${projectId}/`, { instanceId }).then(response => response.data);
    },
    /**
     * 暂停执行任务实例
     * @param {String} instanceId 实例id
     */
    instancePause({}, instanceId) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/action/pause/${projectId}/`, { instanceId }).then(response => response.data);
    },
    /**
     * 继续执行任务实例
     * @param {String} instanceId 实例id
     */
    instanceResume({}, instanceId) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/action/resume/${projectId}/`, { instanceId }).then(response => response.data);
    },
    /**
     * 终止任务实例执行
     * @param {String} instanceId 任务实例id
     */
    instanceRevoke({}, instanceId) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/action/revoke/${projectId}/`, { instanceId }).then(response => response.data);
    },
    /**
     * 暂停子流程任务
     * @param {Object} data 子任务数据
     */
    subInstancePause({}, data) {
      const { instance_id, node_id } = data;
      const { project_id: projectId } = store.state.project;
      const qsData = { instance_id, node_id };
      return axios.post(`taskflow/api/nodes/action/pause_subproc/${projectId}/`, qsData).then(response => response.data);
    },
    /**
     * 继续子流程任务
     * @param {Object} data 子任务数据
     */
    subInstanceResume({}, data) {
      const { instance_id, node_id } = data;
      const { project_id: projectId } = store.state.project;
      const qsData = { instance_id, node_id };
      return axios.post(`taskflow/api/nodes/action/resume_subproc/${projectId}/`, qsData).then(response => response.data);
    },
    // 任务节点操作
    instanceOperate({}, data) {
      const { operation, instance_id: instanceId } = data;
      return axios.post(`task/operate_task/${instanceId}/${operation}/`, {
        space_id: store.state.spaceId,
      }).then(response => response.data);
    },
    /**
     * 修改实例参数
     * @param {Object} data 表单配置数据
     */
    instanceModifyParams({}, data) {
      return axios.post(`taskflow/api/update_task_constants/${data.instance_id}/`, data).then(response => response.data);
    },
    /**
     * 获取任务执行过的变量
     * @param {Object} data 表单配置数据
     */
    getTaskUsedConstants({}, data) {
      return axios.get(`taskflow/api/update_task_constants/${data.instance_id}/`).then(response => response.data);
    },
    /**
     * 获取节点执行详情
     * @param {Object} data 节点配置数据
     */
    getNodeActDetail({}, data) {
      const { username } = store.state.project;
      const { instance_id: instanceId, node_id: nodeId, component_code, subprocess_stack, loop } = data;
      return axios.get(`task/get_task_node_detail/${instanceId}/node/${nodeId}/`, {
        params: {
          component_code,
          subprocess_stack,
          loop,
          username,
          space_id: store.state.spaceId,
        },
      }).then(response => response.data);
    },
    /**
     * 获取任务所有全局变量当前渲染后的值
     * @param {Object} data 节点配置数据
     */
    getRenderCurConstants({}, data) {
      const { task_id: taskId } = data;
      return axios.get(`task/render_current_constants/${taskId}/`, {
        params: {
          space_id: store.state.spaceId,
        },
      }).then(response => response.data);
    },
    /**
     * 获取模版操作记录
     * @param {Object} data 节点配置数据
     */
    getOperationRecordTemplate({}, data) {
      return axios.get(`/api/template/${data.templateId}/get_template_operation_record/`, {
        params: {
          space_id: store.state.spaceId,
        },
      }).then(response => response.data.data);
    },
    /**
     * 获取任务操作记录
     * @param {Object} data 节点配置数据
     */
    getOperationRecordTask({}, data) {
      const { taskId, node_id } = data;
      return axios.get(`task/get_task_operation_record/${taskId}/`, {
        params: {
          node_id,
          space_id: store.state.spaceId,
        },
      }).then(response => response.data);
    },
    /**
     * 获取执行记录日志
     * @param {Object} data 节点配置数据
     */
    getNodeExecutionRecordLog({}, data) {
      const { node_id: nodeId, version, instance_id: taskId, page = 1, page_size: pageSize = 30 } = data;
      return axios.get(`task/get_task_node_log/${taskId}/${nodeId}/${version}/`, {
        params: {
          page,
          page_size: pageSize,
          space_id: store.state.spaceId,
        },
      }).then(response => response.data);
    },
    /**
     * 获取节点执行信息
     * @param {Object} data 节点配置数据
     */
    getNodeActInfo({}, data) {
      const { project_id: projectId } = store.state.project;
      const { instance_id, node_id, component_code, subprocess_stack } = data;
      return axios.get(`taskflow/api/nodes/data/${projectId}/`, {
        params: {
          instance_id,
          node_id,
          component_code,
          subprocess_stack,
        },
      }).then(response => response.data);
    },
    // 任务节点操作
    instanceNodeOperate({}, params) {
      const { node_id: nodeId, operation, instance_id: instanceId, data } = params;
      return axios.post(`task/operate_node/${instanceId}/node/${nodeId}/${operation}/`, {
        ...data,
        space_id: store.state.spaceId,
      }).then(response => response.data);
    },
    /**
     * 节点强制失败
     * @param {Object} data 任务实例数据
     */
    forceFail({}, data) {
      const { project_id: projectId } = store.state.project;
      const { node_id: nodeId, task_id: taskId } = data;
      const action = 'forced_fail';
      return axios.post(`taskflow/api/v4/node_action/${projectId}/${taskId}/${nodeId}/`, { action }, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }).then(response => response.data);
    },
    /**
     * 重试任务节点
     * @param {Object} data 任务实例数据
     */
    instanceRetry({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/retry/${projectId}/`, data).then(response => response.data);
    },
    /**
     * 设置定时间节点时间
     * @param {Object} data 节点配置数据
     */
    setSleepNode({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/spec/timer/reset/${projectId}/`, data).then(response => response.data);
    },
    /**
     * 跳过失败节点
     * @param {Object} data 节点配置数据
     */
    instanceNodeSkip({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/skip/${projectId}/`, data).then(response => response.data);
    },
    /**
     * 跳过分支网关节点
     * @param {Object} data 节点配置数据
     */
    skipExclusiveGateway({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/skip_exg/${projectId}/`, data).then(response => response.data);
    },
    /**
     * 跳过条件并行网关节点
     * @param {Object} data 节点配置数据
     */
    skipCondParallelGateWay({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/skip_cpg/${projectId}/`, data).then(response => response.data);
    },
    /**
     * 暂停节点继续
     * @param {Object} data 节点配置数据
     */
    pauseNodeResume({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/callback/${projectId}/`, data).then(response => response.data);
    },
    // 加载创建任务方式数据
    loadCreateMethod() {
      return axios.get('taskflow/api/get_task_create_method/').then(response => response.data);
    },
    /**
     * 获取作业执行详情
     * @param {Object} data 作业实例ID等信息
     */
    getJobInstanceLog({}, data) {
      const { job_instance_id, project_id: projectId } = data;
      return axios.get(`taskflow/api/nodes/get_job_instance_log/${projectId}/`, {
        params: { job_instance_id },
      }).then(response => response.data);
    },
    subflowNodeRetry({}, data) {
      const { project_id: projectId } = store.state.project;
      return axios.post(`taskflow/api/nodes/action/retry_subprocess/${projectId}/`, data).then(response => response.data);
    },
    // itsm 节点审批
    itsmTransition({}, params) {
      return axios.post('itsm_approve/', params).then(response => response.data);
    },
    getInstanceRetryParams({}, data) {
      return axios.get(`api/v3/taskflow/${data.id}/enable_fill_retry_params/`).then(response => response.data);
    },
    // 节点执行记录
    getNodeExecutionRecord({}, data) {
      return axios.get(`api/v3/taskflow/${data.taskId}/node_execution_record/`, {
        params: {
          template_node_id: data.tempNodeId,
        },
      }).then(response => response.data);
    },
    // 节点快照
    getNodeSnapshotConfig({}, params) {
      const { instance_id: instanceId, node_id: nodeId } = params;
      return axios.get(`task/get_node_snapshot_config/${instanceId}/${nodeId}/`, {
        params: {
          space_id: store.state.spaceId,
        },
      }).then(response => response.data);
    },
    // 任务mock数据
    getTaskMockData({}, data) {
      return axios.get(`task/get_task_mock_data/${data.id}/`, {
        params: {
          space_id: data.spaceId,
        },
      }).then(response => response.data);
    },
    // 创建mock任务
    createMockTask({}, data) {
      return axios.post(`api/template/${data.id}/create_mock_task/`, data.params).then(response => response.data);
    },
  },
  mutations: {
    setSubActivities(state, data) {
      state.subActivities = data;
    },
    setNodeDetailActivityPanel(state, data) {
      state.nodeDetailActivityPanel = data;
    },
  },
};

export default task;
