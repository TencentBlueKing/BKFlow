# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import logging
from copy import deepcopy

from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer

from .utils import post_handle_pipeline_tree, pre_handle_pipeline_tree

logger = logging.getLogger("root")


def preview_template_tree(
    pipeline_tree,
    exclude_task_nodes_id,
    pre_handle_pipeline_tree=pre_handle_pipeline_tree,
    post_handle_pipeline_tree=post_handle_pipeline_tree,
):
    template_constants = deepcopy(pipeline_tree["constants"])
    pre_handle_pipeline_tree(pipeline_tree)
    PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes(pipeline_tree, exclude_task_nodes_id)

    constants_not_referred = {
        key: value for key, value in list(template_constants.items()) if key not in pipeline_tree["constants"]
    }
    post_handle_pipeline_tree(pipeline_tree)
    return {"pipeline_tree": pipeline_tree, "constants_not_referred": constants_not_referred}
