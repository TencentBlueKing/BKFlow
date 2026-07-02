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


import copy

from pipeline.utils.uniqid import line_uniqid

from bkflow.pipeline_web.constants import PWE
from bkflow.pipeline_web.drawing_new.constants import (
    DUMMY_NODE_TYPE,
    MIN_LEN,
    PIPELINE_ELEMENT_TO_WEB,
    PIPELINE_WEB_TO_ELEMENT,
)


def upsert_orders(orders, nodes_fill_nums):
    # 为相应的节点插入相关的虚拟节点占位排版
    new_orders = copy.deepcopy(orders)
    dummy_nodes = []
    for order in orders:
        if order in nodes_fill_nums.keys():
            dummy_nodes_list = [line_uniqid() for i in range(0, nodes_fill_nums[order])]
            dummy_nodes.extend(dummy_nodes_list)
            index = new_orders.index(order)
            new_orders = new_orders[: index + 1] + dummy_nodes_list + new_orders[index + 1 :]
    return new_orders, dummy_nodes


def position(
    pipeline,
    orders,
    activity_size,
    event_size,
    gateway_size,
    start,
    canvas_width,
    more_flows=None,
    nodes_fill_nums=None,
):
    """
    @param gateway_dummy_nums:
    @summary：将后台 pipeline tree 转换成带前端 location、line 画布信息的数据
    @param pipeline: 后台流程树
    @param orders: 层级和同一层级内节点顺序
    @param activity_size: 任务节点长宽，如 (150, 42)
    @param event_size: 事件节点长宽，如 (40, 40)
    @param gateway_size: 网关节点长宽，如 (36, 36)
    @param start: 开始节点绝对定位X、Y轴坐标
    @param canvas_width: 画布最大宽度
    @param more_flows: 额外需要获取位置信息的连线，如反向边、被替换的长边
    @return:
    """
    shift_y = int(max(activity_size[1], event_size[1], gateway_size[1]) * 2)
    # 开始/结束节点纵坐标偏差
    event_shift_y = int((activity_size[1] - event_size[1]) * 0.5)
    # 网关节点纵坐标偏差
    gateway_shift_y = int((activity_size[1] - gateway_size[1]) * 0.5)

    # 纵坐标偏移配置
    pipeline_element_shift_y = {
        DUMMY_NODE_TYPE: 0,
        PWE.ServiceActivity: 0,
        PWE.SubProcess: 0,
        PWE.SubCanvas: 0,
        PWE.EmptyStartEvent: event_shift_y,
        PWE.EmptyEndEvent: event_shift_y,
        PWE.ExclusiveGateway: gateway_shift_y,
        PWE.ConditionalParallelGateway: gateway_shift_y,
        PWE.ParallelGateway: gateway_shift_y,
        PWE.ConvergeGateway: gateway_shift_y,
    }

    # 横坐标偏移配置（子画布宽度由实际width属性决定，此处仅用于横向占位计算）
    subcanvas_placeholder_width = activity_size[0] * 4
    pipeline_element_shift_x = {
        DUMMY_NODE_TYPE: 0,
        PWE.ServiceActivity: activity_size[0] * 1.5,
        PWE.SubProcess: activity_size[0] * 1.5,
        PWE.SubCanvas: subcanvas_placeholder_width,
        PWE.EmptyStartEvent: event_size[0] * 2.5,
        PWE.EmptyEndEvent: event_size[0] * 2.5,
        PWE.ExclusiveGateway: gateway_size[0] * 6.5,
        PWE.ConditionalParallelGateway: gateway_size[0] * 6.5,
        PWE.ParallelGateway: gateway_size[0] * 2.5,
        PWE.ConvergeGateway: gateway_size[0] * 2.5,
    }

    min_rk = min(orders.keys())
    max_rk = max(orders.keys())
    old_locations = {loc["id"]: loc for loc in pipeline.get("location", [])}
    locations = {}
    rank_x, rank_y = start
    current_layer_max_x = rank_x  # 当前层最大横向位置
    new_line_y = 0  # 下一行起始y坐标

    for rk in range(min_rk, max_rk + MIN_LEN, MIN_LEN):
        layer_nodes = orders[rk]
        layer_nodes, dummy_nodes = upsert_orders(layer_nodes, nodes_fill_nums)

        order_x, order_y = rank_x, rank_y
        if new_line_y == 0:
            new_line_y = rank_y + shift_y

        current_layer_max_y = order_y  # 当前层最大下边界
        current_shift_x = 0  # 当前层横向最大占位

        for node_id in layer_nodes:
            if node_id not in pipeline["all_nodes"]:
                order_y = current_layer_max_y
                continue

            node = pipeline["all_nodes"][node_id]
            node_type = node[PWE.type]
            # 兼容前端type和后端type，统一转成后端类型查配置
            backend_type = PIPELINE_WEB_TO_ELEMENT.get(node_type, node_type)
            # 节点y坐标取当前顺序y和层最大下边界的较大值，避免重叠
            node_y = int(max(order_y, current_layer_max_y) + pipeline_element_shift_y.get(backend_type, 0))
            node_x = int(order_x)

            if backend_type == PWE.SubCanvas or node_type == "subcanvas":
                # 处理子画布节点
                sub_entry, offset_x, offset_y, sub_w, sub_h, sub_bottom = process_subcanvas_node(
                    node_id=node_id,
                    node=node,
                    node_x=node_x,
                    node_y=node_y,
                    old_locations=old_locations,
                    dummy_nodes=dummy_nodes,
                    shift_y=shift_y,
                )
                if sub_entry:
                    locations[node_id] = sub_entry

                # 优先用子画布实际宽度，没有实际宽度则用默认占位宽度
                actual_sub_width = (
                    sub_w
                    if sub_w is not None
                    else pipeline_element_shift_x.get(backend_type, subcanvas_placeholder_width)
                )
                # 子画布占位加上固定间距
                node_occupy_x = node_x + actual_sub_width + 70
                current_layer_max_x = max(current_layer_max_x, node_occupy_x)
                # 更新层内最大下边界和全局下一行y
                current_layer_max_y = max(current_layer_max_y, sub_bottom)
                new_line_y = max(new_line_y, sub_bottom)
                # 更新层内横向占位
                current_shift_x = max(current_shift_x, actual_sub_width)

            else:
                # 处理普通节点
                current_shift_x = max(current_shift_x, pipeline_element_shift_x.get(backend_type, 0))
                if node_id in old_locations:
                    loc_entry = copy.deepcopy(old_locations[node_id])
                    loc_entry.update({"x": node_x, "y": node_y})
                elif node_id not in dummy_nodes:
                    loc_entry = {
                        "id": node_id,
                        "type": PIPELINE_ELEMENT_TO_WEB.get(node_type, node_type),
                        "name": node.get(PWE.name, ""),
                        "status": "",
                        "x": node_x,
                        "y": node_y,
                    }
                else:
                    loc_entry = None

                if loc_entry:
                    locations[node_id] = loc_entry

                # 更新层内位置边界，加上固定间距
                node_occupy_x = node_x + pipeline_element_shift_x.get(backend_type, 0)
                current_layer_max_x = max(current_layer_max_x, node_occupy_x)
                current_layer_max_y = max(current_layer_max_y, node_y + shift_y)

            # 更新下一节点y坐标
            order_y = current_layer_max_y
            if node_y >= new_line_y:
                new_line_y = node_y + shift_y

        # 计算当前层最右端坐标（最后一个节点的占用位置）
        layer_right_x = current_layer_max_x

        valid_node_count = len([nid for nid in layer_nodes if nid not in dummy_nodes and nid in pipeline["all_nodes"]])
        if layer_right_x > canvas_width and rk < max_rk and valid_node_count > 0:
            current_layer_max_x = start[0]
            new_line_y = new_line_y + shift_y
        else:
            rank_x = current_layer_max_x

    flows = {}
    flows.update(pipeline[PWE.flows])
    if isinstance(more_flows, dict):
        flows.update(more_flows)
    lines = position_flows(flows, locations, pipeline_element_shift_y, start[0], shift_y)
    return locations, lines


def process_subcanvas_node(
    node_id: str, node: dict, node_x: int, node_y: int, old_locations: dict, dummy_nodes: set, shift_y: int
) -> tuple:
    """
    处理子画布节点布局，返回位置配置、偏移量、宽高、下边界
    子画布宽高仅从旧location配置读取，无默认值
    """
    old_sub_loc = old_locations.get(node_id, {})
    # 仅读取已有宽高，不设置默认值
    sub_width = int(old_sub_loc["width"]) if old_sub_loc.get("width") is not None else None
    sub_height = int(old_sub_loc["height"]) if old_sub_loc.get("height") is not None else None

    # 计算子画布移动偏移量，用于同步内部节点
    old_x = old_sub_loc.get("x")
    old_y = old_sub_loc.get("y")
    offset_x = node_x - old_x if old_x is not None else 0
    offset_y = node_y - old_y if old_y is not None else 0

    # 构建子画布位置配置
    if node_id in old_locations:
        entry = copy.deepcopy(old_sub_loc)
        entry.update({"x": node_x, "y": node_y})
        # 保留旧配置宽高，不强制覆盖
    elif node_id not in dummy_nodes:
        entry = {
            "id": node_id,
            "type": PIPELINE_ELEMENT_TO_WEB.get(node[PWE.type], node[PWE.type]),
            "name": node.get(PWE.name, ""),
            "status": "",
            "x": node_x,
            "y": node_y,
            "parent": True,
        }
        # 补充已有宽高
        if sub_width is not None:
            entry["width"] = sub_width
        if sub_height is not None:
            entry["height"] = sub_height
    else:
        entry = None

    # 同步移动子画布内部节点
    sub_pipeline = node.get("pipeline", {})
    if sub_pipeline:
        for sub_loc in sub_pipeline.get("location", []):
            sub_loc["x"] = sub_loc.get("x", 0) + offset_x
            sub_loc["y"] = sub_loc.get("y", 0) + offset_y

    # 计算子画布下边界（和普通节点间距规则一致）
    sub_bottom_y = node_y + (sub_height if sub_height is not None else 0) + shift_y

    return entry, offset_x, offset_y, sub_width, sub_height, sub_bottom_y


def position_flows(flows, locations, pipeline_element_shift_y, start_x, shift_y):
    """
    @summary: 分配连线端点
    @param flows:
    @param locations:
    @param pipeline_element_shift_y:
    @param start_x: 画布最左侧
    @param shift_y: 画布默认行距
    @return:
    """
    lines = {}
    for flow_id, flow in flows.items():
        source_arrow, target_arrow = arrow_flow(flow, locations, pipeline_element_shift_y)
        lines[flow_id] = {
            "id": flow_id,
            "source": {"arrow": source_arrow, "id": flow[PWE.source]},
            "target": {"arrow": target_arrow, "id": flow[PWE.target]},
        }
        source_location = locations[flow[PWE.source]]
        target_location = locations[flow[PWE.target]]
        # 终点是每行起始位置，说明有换行，每次换行线段需要设置线段比例保证下折线与下一行距离为单行间距
        if target_location["x"] == start_x:
            lines[flow_id]["midpoint"] = 1 - shift_y * 0.5 / (target_location["y"] - source_location["y"])
    return lines


def arrow_flow(flow, locations, pipeline_element_shift_y):
    """
    @summary: 根据 flow 起始点相对位置决定 flow 两端连线端点位置
    @param flow:
    @param locations:
    @param pipeline_element_shift_y:
    @return:
    """
    source_location = locations[flow[PWE.source]]
    target_location = locations[flow[PWE.target]]

    source_type = PIPELINE_WEB_TO_ELEMENT.get(source_location["type"], source_location["type"])
    target_type = PIPELINE_WEB_TO_ELEMENT.get(target_location["type"], target_location["type"])

    source_location_x = source_location["x"]
    source_shift_y = pipeline_element_shift_y[source_type]
    source_location_y = source_location["y"] - source_shift_y

    target_location_x = target_location["x"]
    target_shift_y = pipeline_element_shift_y[target_type]
    target_location_y = target_location["y"] - target_shift_y

    # 起点在终点左侧
    if source_location_x < target_location_x:
        # 并且起点在终点上侧，一般是发起分支
        if source_location_y < target_location_y:
            source_arrow = PWE.bottom
            target_arrow = PWE.left
        # 并且起点在终点下侧，一般是汇聚分支
        elif source_location_y > target_location_y:
            source_arrow = PWE.right
            target_arrow = PWE.bottom
        # 正常顺序流
        else:
            source_arrow = PWE.right
            target_arrow = PWE.left
    # 起点在终点右侧
    elif source_location_x > target_location_x:
        # 并且起点在终点上侧，一般是换行
        if source_location_y < target_location_y:
            source_arrow = PWE.right
            target_arrow = PWE.left
        # 并且起点在终点左侧或下侧，一般是打回流程
        else:
            source_arrow = PWE.bottom
            target_arrow = PWE.bottom
    # 起点和终点在同一横坐标上
    else:
        if source_location_y < target_location_y:
            source_arrow = PWE.bottom
            target_arrow = PWE.top
        elif source_location_y > target_location_y:
            source_arrow = PWE.top
            target_arrow = PWE.bottom
        # 自环边，目前还不会出现这种流程
        else:
            source_arrow = PWE.right
            target_arrow = PWE.bottom
    return source_arrow, target_arrow
