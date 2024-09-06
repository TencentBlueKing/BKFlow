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

const taskList = {
  namespaced: true,
  state: {

  },
  mutations: {

  },
  actions: {
    loadTaskList({}, data) {
      const config = {};
      if (data.cancelToken) {
        config.cancelToken = data.cancelToken;
        delete data.cancelToken;
      }
      return axios.get(`/task_admin/get_task_list/${data.space_id}/`, {
        params: data,
        ...config,
      }).then(response => response.data);
    },
    deleteTask({}, data) {
      return axios.post('/task_admin/batch_delete_tasks/', data).then(response => response.data);
    },
  },
};

export default taskList;
