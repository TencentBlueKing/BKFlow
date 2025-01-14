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

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ArrayItemSchema, ObjectItemSchema, StringItemSchema
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")


class ValueAssignService(BKFlowBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name=_("赋值变量或常量与被赋值变量列表"),
                key="bk_assignment_list",
                type="array",
                schema=ArrayItemSchema(
                    description=_("赋值变量或常量与被赋值变量的映射列表"),
                    item_schema=ObjectItemSchema(
                        description=_("单个赋值关系"),
                        property_schemas={
                            "bk_assign_source_var": StringItemSchema(description=_("赋值变量或常量")),
                            "bk_assgin_target_var": StringItemSchema(description=_("被赋值变量")),
                        },
                    ),
                ),
            )
        ]

    def outputs_format(self):
        # 插件返回内容
        return []

    def plugin_execute(self, data, parent_data):
        runtime = BambooDjangoRuntime()
        upsert_dict = {}
        pipeline_id = self._runtime_attrs["root_pipeline_id"]
        assign_list = data.get_one_of_inputs("bk_assignment_list")
        for assign in assign_list:
            # 循环处理表格中的内容 检查是否存在/类型问题后再统一事务批量执行
            input_var = assign["bk_assign_source_var"]
            target_var = assign["bk_assgin_target_var"]
            target_var_str = "${{{}}}".format(target_var)
            context = runtime.get_context_values(pipeline_id=pipeline_id, keys={target_var_str})
            if not context:
                # 如果没有找到对应的全局变量则直接返回错误
                err_msg = "target variable {} is not exist".format(target_var)
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False
            context = context[0]

            # 处理输入变量与目标变量的类型转换(输入常量时) 如果是相同类型则必然成功
            try:
                # 尝试将输入转换为目标变量类型
                input_var = type(context.value)(input_var)
            except (ValueError, TypeError):
                err_msg = "input variable '{}' cannot be converted to the type of target variable '{}': {}".format(
                    input_var, target_var, type(context.value).__name__
                )
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False

            # 更新上下文并放入字典
            context.value = input_var
            upsert_dict[target_var_str] = context
        runtime.upsert_plain_context_values(pipeline_id=pipeline_id, update=upsert_dict)
        # 批量更新内容 事务原子操作
        return True


class ValueAssignComponent(Component):
    name = _("赋值节点")
    code = "value_assign"
    bound_service = ValueAssignService
    form = settings.STATIC_URL + "components/value_assign/v1_0_0.js"
    version = "v1.0.0"
    desc = "提供内置赋值功能"
