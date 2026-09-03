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

# 子画布节点在横向占位后追加的固定间距，避免与后续节点贴合
SUBCANVAS_EXTRA_GAP = 70


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
    # 节点横坐标偏移值
    pipeline_element_shift_x = {
        DUMMY_NODE_TYPE: 0,
        PWE.ServiceActivity: activity_size[0] * 1.5,
        PWE.SubProcess: activity_size[0] * 1.5,
        PWE.SubCanvas: activity_size[0] * 4,
        PWE.EmptyStartEvent: event_size[0] * 2.5,
        PWE.EmptyEndEvent: event_size[0] * 2.5,
        PWE.ExclusiveGateway: gateway_size[0] * 6.5,
        PWE.ConditionalParallelGateway: gateway_size[0] * 6.5,
        PWE.ParallelGateway: gateway_size[0] * 2.5,
        PWE.ConvergeGateway: gateway_size[0] * 2.5,
    }

    # 节点之间的平均距离，用于换行判断
    size_x = max(activity_size[0], event_size[0], gateway_size[0])

    min_rk = min(orders.keys())
    max_rk = max(orders.keys())
    old_locations = {loc["id"]: loc for loc in pipeline.get("location", [])}
    locations = {}
    rank_x, rank_y = start
    new_line_y = 0
    for rk in range(min_rk, max_rk + MIN_LEN, MIN_LEN):
        layer_nodes = orders[rk]
        layer_nodes, dummy_nodes = upsert_orders(layer_nodes, nodes_fill_nums)
        # 当前 rank 首个节点位置
        order_x, order_y = rank_x, rank_y
        if new_line_y == 0:
            new_line_y = rank_y + shift_y

        # 当前层横向占位最大值（用于推进 rank_x）
        layer_shift_x = 0
        # 当前层最大下边界（用于层内多节点纵向不重叠）
        layer_max_y = order_y

        for node_id in layer_nodes:
            if node_id not in pipeline["all_nodes"]:
                # 虚拟占位节点，仅占用一个纵向槽位
                order_y = max(order_y, layer_max_y) + shift_y
                continue

            node = pipeline["all_nodes"][node_id]
            backend_type = PIPELINE_WEB_TO_ELEMENT.get(node[PWE.type], node[PWE.type])
            node_y = int(max(order_y, layer_max_y) + pipeline_element_shift_y[backend_type])
            node_x = int(order_x)

            # 计算该节点横向占位、下边界，并生成 location 条目
            if backend_type == PWE.SubCanvas:
                occupy_x, bottom_y = _place_subcanvas(
                    node_id=node_id,
                    node=node,
                    node_x=node_x,
                    node_y=node_y,
                    old_locations=old_locations,
                    dummy_nodes=dummy_nodes,
                    locations=locations,
                    default_width=pipeline_element_shift_x[backend_type],
                    shift_y=shift_y,
                )
            else:
                occupy_x, bottom_y = _place_normal_node(
                    node_id=node_id,
                    node=node,
                    node_x=node_x,
                    node_y=node_y,
                    old_locations=old_locations,
                    dummy_nodes=dummy_nodes,
                    locations=locations,
                    node_shift_x=pipeline_element_shift_x[backend_type],
                    shift_y=shift_y,
                )

            layer_shift_x = max(layer_shift_x, occupy_x - node_x)
            layer_max_y = max(layer_max_y, bottom_y)
            if node_y >= new_line_y:
                new_line_y = node_y + shift_y

            order_y = layer_max_y

        rank_x = rank_x + layer_shift_x
        # 1)下一个节点最右端 x 坐标超出画布宽度 2)无分支 3)下一个节点非结束节点 ——> 换行
        if rank_x + size_x > canvas_width and (len(layer_nodes) - len(dummy_nodes)) == 1 and rk < max_rk - MIN_LEN:
            rank_x = start[0]
            rank_y = new_line_y

    flows = {}
    flows.update(pipeline[PWE.flows])
    if isinstance(more_flows, dict):
        flows.update(more_flows)
    lines = position_flows(flows, locations, pipeline_element_shift_y, start[0], shift_y)
    return locations, lines


def _place_normal_node(node_id, node, node_x, node_y, old_locations, dummy_nodes, locations, node_shift_x, shift_y):
    """
    放置一个普通节点：写入 locations，返回 (occupy_x, bottom_y)
    - occupy_x: 该节点向右延伸的边界，用于推进下一节点起点
    - bottom_y: 该节点向下延伸的边界，用于同层其它节点避让
    """
    if node_id in old_locations:
        entry = copy.deepcopy(old_locations[node_id])
        entry.update({"x": node_x, "y": node_y})
        locations[node_id] = entry
    elif node_id not in dummy_nodes:
        locations[node_id] = {
            "id": node_id,
            "type": PIPELINE_ELEMENT_TO_WEB.get(node[PWE.type], node[PWE.type]),
            "name": node.get(PWE.name, ""),
            "status": "",
            "x": node_x,
            "y": node_y,
        }
    return node_x + node_shift_x, node_y + shift_y


def _place_subcanvas(node_id, node, node_x, node_y, old_locations, dummy_nodes, locations, default_width, shift_y):
    """
    放置一个子画布节点：写入 locations，同步内部子节点坐标，返回 (occupy_x, bottom_y)
    子画布宽高仅从旧 location 读取，无默认值；无实际宽度时使用 default_width 作为兜底横向占位。
    """
    old_loc = old_locations.get(node_id, {})
    sub_width = int(old_loc["width"]) if old_loc.get("width") is not None else None
    sub_height = int(old_loc["height"]) if old_loc.get("height") is not None else None

    # 计算移动偏移，用于同步内部节点坐标
    offset_x = node_x - old_loc["x"] if old_loc.get("x") is not None else 0
    offset_y = node_y - old_loc["y"] if old_loc.get("y") is not None else 0

    if node_id in old_locations:
        entry = copy.deepcopy(old_loc)
        entry.update({"x": node_x, "y": node_y})
        locations[node_id] = entry
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
        if sub_width is not None:
            entry["width"] = sub_width
        if sub_height is not None:
            entry["height"] = sub_height
        locations[node_id] = entry

    # 副作用：同步子画布内部节点坐标，使其跟随外层容器移动
    _shift_inner_locations(node, offset_x, offset_y)

    occupy_width = sub_width if sub_width is not None else default_width
    occupy_x = node_x + occupy_width + SUBCANVAS_EXTRA_GAP
    bottom_y = node_y + (sub_height if sub_height is not None else 0) + shift_y
    return occupy_x, bottom_y


def _shift_inner_locations(node, offset_x, offset_y):
    """同步移动子画布内部节点的 x/y 坐标"""
    if not offset_x and not offset_y:
        return
    sub_pipeline = node.get("pipeline") or {}
    for sub_loc in sub_pipeline.get("location", []):
        sub_loc["x"] = sub_loc.get("x", 0) + offset_x
        sub_loc["y"] = sub_loc.get("y", 0) + offset_y


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
