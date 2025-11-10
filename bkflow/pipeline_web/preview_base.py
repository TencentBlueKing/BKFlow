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


import json
import logging
import traceback
from copy import deepcopy

from django.core.exceptions import ValidationError
from pipeline.component_framework.constant import ConstantPool
from pipeline.core.constants import PE
from pipeline.models import TemplateScheme
from pipeline.validators.gateway import validate_gateways
from pipeline.validators.utils import format_node_io_to_list

from bkflow.pipeline_web.constants import PWE
from bkflow.template.models import Template, TemplateReference

logger = logging.getLogger("root")


class PipelineTemplateWebPreviewer:
    @staticmethod
    def get_template_exclude_task_nodes_with_schemes(pipeline_tree, scheme_id_list, check_schemes_exist=False):
        """
        根据执行方案获取要剔除的模版节点
        @param pipeline_tree:
        @param scheme_id_list:
        @param check_schemes_exist:
        @return:
        """
        template_nodes_set = set(pipeline_tree[PE.activities].keys())
        exclude_task_nodes_id_set = set()
        if scheme_id_list:
            scheme_dict = TemplateScheme.objects.in_bulk(scheme_id_list)
            if check_schemes_exist and len(scheme_dict) != len(scheme_id_list):
                raise ValidationError(f"not all input scheme id exit: {set(scheme_id_list)-set(scheme_dict.keys())}")
            scheme_data_set = set()
            for scheme in scheme_dict.values():
                scheme_data = json.loads(scheme.data)
                scheme_data_set.update(scheme_data)
            exclude_task_nodes_id_set = template_nodes_set - scheme_data_set

        # 不可选节点一定执行
        for node_id, node in pipeline_tree[PE.activities].items():
            if not node["optional"]:
                exclude_task_nodes_id_set.discard(node_id)

        return list(exclude_task_nodes_id_set)

    @staticmethod
    def get_template_exclude_task_nodes_with_appoint_nodes(pipeline_tree, appoint_nodes_id):
        """
        根据执行方案获取要剔除的模版节点
        @param pipeline_tree:
        @param appoint_nodes_id:
        @return:
        """
        template_nodes_set = set(pipeline_tree[PE.activities].keys())
        not_optional_nodes_set = {
            node_id for node_id, node in pipeline_tree[PE.activities].items() if not node["optional"]
        }
        appoint_nodes_id_set = set(appoint_nodes_id)
        exclude_task_nodes_id_set = template_nodes_set - appoint_nodes_id_set - not_optional_nodes_set
        return list(exclude_task_nodes_id_set)

    @staticmethod
    def preview_pipeline_tree_exclude_task_nodes(
        pipeline_tree, exclude_task_nodes_id=None, remove_outputs_without_refs=True
    ):
        """
        @param pipeline_tree:
        @param exclude_task_nodes_id:
        @param remove_outputs_without_refs: 是否移除在当前流程设置为输出但未被引用的自定义变量
        @return:
        """
        if exclude_task_nodes_id is None:
            exclude_task_nodes_id = []

        locations = {item["id"]: item for item in pipeline_tree.get("location", [])}
        lines = {item["id"]: item for item in pipeline_tree.get("line", [])}

        for act_id in exclude_task_nodes_id:
            if act_id not in pipeline_tree[PE.activities]:
                error = "task node[id=%s] is not in template pipeline tree" % act_id
                raise Exception(error)

            act = pipeline_tree[PE.activities].pop(act_id)

            if not act["optional"]:
                error = "task node[id=%s] is not optional" % act_id
                raise Exception(error)

            PipelineTemplateWebPreviewer._ignore_act(
                act=act, locations=locations, lines=lines, pipeline_tree=pipeline_tree
            )

        PipelineTemplateWebPreviewer._remove_useless_parallel(pipeline_tree, lines, locations)

        pipeline_tree["line"] = list(lines.values())
        pipeline_tree["location"] = list(locations.values())

        PipelineTemplateWebPreviewer._remove_useless_constants(
            exclude_task_nodes_id=exclude_task_nodes_id,
            pipeline_tree=pipeline_tree,
            remove_outputs_without_refs=remove_outputs_without_refs,
        )

        return True

    @staticmethod
    def _try_to_ignore_parallel(parallel, converge_id, lines, locations, pipeline_tree):

        ignore_whole_parallel = True
        converge = pipeline_tree[PE.gateways][converge_id]
        parallel_outgoing = deepcopy(parallel[PE.outgoing])

        for outgoing_id in parallel_outgoing:
            # meet not converge node
            if pipeline_tree[PE.flows][outgoing_id][PE.target] != converge_id:
                ignore_whole_parallel = False
                continue

            # remove boring sequence
            converge[PE.incoming].remove(outgoing_id)
            parallel[PE.outgoing].remove(outgoing_id)
            pipeline_tree[PE.flows].pop(outgoing_id)
            lines.pop(outgoing_id)

        if not ignore_whole_parallel:
            return

        target_of_converge = pipeline_tree[PE.flows][converge[PE.outgoing]][PE.target]
        next_node_of_converge = (
            pipeline_tree[PE.activities].get(target_of_converge)
            or pipeline_tree[PE.gateways].get(target_of_converge)
            or pipeline_tree[PE.end_event]
        )

        # remove converge outgoing
        lines.pop(converge[PE.outgoing])
        pipeline_tree[PE.flows].pop(converge[PE.outgoing])

        # sequences not come from parallel to be removed
        new_incoming_list = []
        # redirect converge rerun incoming
        for incoming in converge[PE.incoming]:
            pipeline_tree[PE.flows][incoming][PE.target] = target_of_converge
            lines[incoming][PE.target]["id"] = target_of_converge
            new_incoming_list.append(incoming)

        # redirect parallel rerun incoming
        gateway_incoming = parallel[PE.incoming]
        gateway_incoming = gateway_incoming if isinstance(gateway_incoming, list) else [gateway_incoming]
        for incoming in gateway_incoming:
            pipeline_tree[PE.flows][incoming][PE.target] = target_of_converge
            lines[incoming][PE.target]["id"] = target_of_converge
            new_incoming_list.append(incoming)

        # process next node's incoming
        PipelineTemplateWebPreviewer._replace_node_incoming(
            next_node=next_node_of_converge, replaced_incoming=converge[PE.outgoing], new_incoming=new_incoming_list
        )

        # remove parallel and converge
        pipeline_tree[PE.gateways].pop(parallel["id"])
        pipeline_tree[PE.gateways].pop(converge["id"])
        locations.pop(parallel["id"])
        locations.pop(converge["id"])

    @staticmethod
    def _replace_node_incoming(next_node, replaced_incoming, new_incoming):
        if isinstance(next_node[PE.incoming], list):
            next_node[PE.incoming].pop(next_node[PE.incoming].index(replaced_incoming))
            next_node[PE.incoming].extend(new_incoming)
        else:
            is_boring_list = isinstance(new_incoming, list) and len(new_incoming) == 1
            next_node[PE.incoming] = new_incoming[0] if is_boring_list else new_incoming

    @staticmethod
    def _ignore_act(act, locations, lines, pipeline_tree):

        # change next_node's incoming: task node、control node is different
        # change incoming_flow's target to next node
        # delete outgoing_flow
        incoming_id_list, outgoing_id = act[PE.incoming], act[PE.outgoing]
        incoming_id_list = incoming_id_list if isinstance(incoming_id_list, list) else [incoming_id_list]

        outgoing_flow = pipeline_tree[PE.flows][outgoing_id]
        target_id = outgoing_flow[PE.target]

        next_node = (
            pipeline_tree[PE.activities].get(target_id)
            or pipeline_tree[PE.gateways].get(target_id)
            or pipeline_tree[PE.end_event]
        )

        PipelineTemplateWebPreviewer._replace_node_incoming(
            next_node=next_node, replaced_incoming=outgoing_id, new_incoming=incoming_id_list
        )

        for incoming_id in incoming_id_list:
            incoming_flow = pipeline_tree[PE.flows][incoming_id]
            incoming_flow[PE.target] = next_node["id"]

        pipeline_tree[PE.flows].pop(outgoing_id)

        # web location data
        try:
            locations.pop(act["id"])
            lines.pop(outgoing_id)

            for incoming_id in incoming_id_list:
                lines[incoming_id][PE.target]["id"] = next_node["id"]
        except Exception:
            logger.exception(
                "create_pipeline_instance_exclude_task_nodes adjust web data error: %s" % traceback.format_exc()
            )

    @staticmethod
    def _remove_useless_constants(exclude_task_nodes_id, pipeline_tree, remove_outputs_without_refs=True):
        """
        @param exclude_task_nodes_id:
        @param pipeline_tree:
        @param remove_outputs_without_refs: 是否移除在当前流程设置为输出但未被引用的自定义变量
        @return:
        """
        # pop unreferenced constant
        data = {}
        for act_id, act in list(pipeline_tree[PE.activities].items()):
            if act["type"] == PE.ServiceActivity:
                node_data = {
                    ("{}_{}".format(act_id, key)): value for key, value in list(act["component"]["data"].items())
                }
            # PE.SubProcess
            else:
                node_data = {
                    ("{}_{}".format(act_id, key)): value
                    for key, value in list(act.get("constants", {}).items())
                    if value["show_type"] == "show"
                }
            data.update(node_data)

        for gw_id, gw in list(pipeline_tree[PE.gateways].items()):
            if gw["type"] in [PE.ExclusiveGateway, PE.ConditionalParallelGateway]:
                gw_data = {
                    ("{}_{}".format(gw_id, key)): {"value": value["evaluate"]}
                    for key, value in list(gw["conditions"].items())
                }
                data.update(gw_data)

        # get all referenced constants in flow
        constants = pipeline_tree[PE.constants]

        referenced_keys = []
        while True:
            last_count = len(referenced_keys)
            cons_pool = ConstantPool(data, lazy=True)
            refs = cons_pool.get_reference_info(strict=False)
            for keys in list(refs.values()):
                for key in keys:
                    # add outputs keys later
                    if key in constants and key not in referenced_keys:
                        referenced_keys.append(key)
                        data.update({key: constants[key]})
            if len(referenced_keys) == last_count:
                break

        # keep outputs constants
        outputs_keys = [key for key, value in list(constants.items()) if value["source_type"] == "component_outputs"]
        referenced_keys = list(set(referenced_keys + outputs_keys))
        init_outputs = pipeline_tree[PE.outputs]
        pipeline_tree[PE.outputs] = [key for key in init_outputs if key in referenced_keys]
        # rebuild constants index
        referenced_keys.sort(key=lambda x: constants[x]["index"])
        new_constants = {}
        for index, key in enumerate(referenced_keys):
            value = constants[key]
            value["index"] = index
            # delete constant reference info to task node
            for act_id in exclude_task_nodes_id:
                if act_id in value["source_info"]:
                    value["source_info"].pop(act_id)
            new_constants[key] = value

        if not remove_outputs_without_refs:
            for key, value in constants.items():
                if value["source_type"] == "custom" and key in init_outputs and key not in pipeline_tree[PE.outputs]:
                    new_constants[key] = value
                    pipeline_tree[PE.outputs].append(key)

        pipeline_tree[PE.constants] = new_constants

    @staticmethod
    def _remove_useless_parallel(pipeline_tree, lines, locations):
        copy_tree = deepcopy(pipeline_tree)

        for act in list(copy_tree["activities"].values()):
            format_node_io_to_list(act, o=False)

        for gateway in list(copy_tree["gateways"].values()):
            format_node_io_to_list(gateway, o=False)

        format_node_io_to_list(copy_tree["end_event"], o=False)

        converges = validate_gateways(copy_tree)

        while True:

            gateway_count = len(pipeline_tree[PE.gateways])

            for converge_id, converged_list in list(converges.items()):

                for converged in converged_list:

                    gateway = pipeline_tree[PE.gateways].get(converged)

                    if not gateway:  # had been removed
                        continue

                    # conditional parallel gateway do not need to trim
                    is_parallel = gateway[PE.type] == PE.ParallelGateway

                    # only process parallel gateway
                    if not is_parallel:
                        continue

                    PipelineTemplateWebPreviewer._try_to_ignore_parallel(
                        parallel=gateway,
                        converge_id=converge_id,
                        lines=lines,
                        locations=locations,
                        pipeline_tree=pipeline_tree,
                    )

            if gateway_count == len(pipeline_tree[PE.gateways]):
                break

    @staticmethod
    def is_circular_reference(pipeline_tree, current_template_id, space_id, scope_type, scope_value):
        """
        检查子流程模板是否存在循环依赖
        """

        templates = Template.objects.filter(space_id=space_id, is_deleted=False)

        if scope_type is not None:
            templates = templates.filter(scope_type=scope_type)
        if scope_value is not None:
            templates = templates.filter(scope_value=scope_value)
        if scope_type is None and scope_value is None:
            templates = templates.filter(scope_type__isnull=True, scope_value__isnull=True)

        template_ids = list(templates.values_list("id", flat=True))
        template_refs = TemplateReference.objects.filter(root_template_id__in=template_ids).values(
            "root_template_id", "subprocess_template_id"
        )

        sub_template_map = {}
        for ref in template_refs:
            root_id = ref["root_template_id"]
            sub_id = int(ref["subprocess_template_id"])
            if root_id not in sub_template_map:
                sub_template_map[root_id] = []
            sub_template_map[root_id].append(sub_id)

        def has_cycle_from_template(disclose_template_id, visited):
            if disclose_template_id in visited:
                return True
            visited.add(disclose_template_id)

            sub_refs = sub_template_map.get(str(disclose_template_id), [])

            for sub_id in sub_refs:
                if has_cycle_from_template(sub_id, visited):
                    return True
            visited.remove(disclose_template_id)

            return False

        activities = pipeline_tree.get("activities", {})
        visited_templates = set()
        if current_template_id:
            visited_templates.add(current_template_id)

        for act_key, act_value in activities.items():
            if act_value.get(PWE.type) == PWE.SubProcess:
                template_id = act_value["template_id"]
                if has_cycle_from_template(template_id, visited_templates):
                    return {
                        "has_cycle": True,
                        "node_key": act_key,
                        "node_name": act_value.get("name"),
                        "template_id": template_id,
                    }

        return {"has_cycle": False}
