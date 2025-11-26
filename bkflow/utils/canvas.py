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


from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Type


class OperateType(Enum):
    CREATE_TEMPLATE = "create_template"
    COPY_TEMPLATE = "copy_template"
    UPDATE_TEMPLATE = "update_template"


class CanvasType(Enum):
    STAGE = "stage"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class CanvasHandler(ABC):
    """画布处理抽象基类"""

    @classmethod
    @abstractmethod
    def get_canvas_type(cls) -> CanvasType:
        """获取画布类型"""
        pass

    @classmethod
    def is_canvas_type(cls, pipeline_tree: dict) -> bool:
        """判断是否为当前画布类型"""
        return pipeline_tree.get("canvas_mode") == cls.get_canvas_type().value

    @classmethod
    def should_process_copy(cls, pipeline_tree: dict) -> bool:
        """判断复制时是否需要处理"""
        return True

    @classmethod
    def should_generate_node_map(cls, pipeline_tree: dict, node_map: Optional[dict]) -> bool:
        """判断是否需要生成节点映射"""
        return True

    @classmethod
    def handle_node_replacement(cls, pipeline_tree: dict, node_map: dict) -> None:
        """处理节点替换"""
        pass


class StageCanvasHandler(CanvasHandler):
    """Stage画布处理类"""

    @classmethod
    def get_canvas_type(cls) -> CanvasType:
        return CanvasType.STAGE

    @classmethod
    def should_process_copy(cls, pipeline_tree: dict) -> bool:
        """Stage画布在复制时需要特殊处理"""
        return cls.is_canvas_type(pipeline_tree)

    @classmethod
    def should_generate_node_map(cls, pipeline_tree: dict, node_map: Optional[dict]) -> bool:
        """Stage画布在没有node_map时需要生成映射"""
        return not (cls.is_canvas_type(pipeline_tree) and node_map)

    @classmethod
    def handle_node_replacement(cls, pipeline_tree: dict, node_map: dict) -> None:
        """处理Stage画布节点替换"""
        cls.sync_stage_canvas_data_node_ids(node_map, pipeline_tree)

    @staticmethod
    def sync_stage_canvas_data_node_ids(node_map: dict, pipeline_tree: dict) -> dict:
        """同步Stage画布数据中的节点ID"""
        stage_canvas_data = pipeline_tree.get("stage_canvas_data", [])

        # 收集所有需要处理的节点
        all_nodes = []
        for stage in stage_canvas_data:
            for job in stage.get("jobs", []):
                all_nodes.extend(job.get("nodes", []))

        # 直接更新节点 ID
        for node in all_nodes:
            node_id = node.get("id")
            if node_id in node_map:
                node["id"] = node_map[node_id]
                # 同步更新 option 中的 id
                option = node.get("option")
                if option and isinstance(option, dict) and "id" in option:
                    option["id"] = node_map[node_id]

        return pipeline_tree


class VerticalCanvasHandler(CanvasHandler):
    """垂直画布处理类"""

    @classmethod
    def get_canvas_type(cls) -> CanvasType:
        return CanvasType.VERTICAL

    @classmethod
    def should_process_copy(cls, pipeline_tree: dict) -> bool:
        """垂直画布复制时不需要特殊处理"""
        return False


class HorizontalCanvasHandler(CanvasHandler):
    """水平画布处理类"""

    @classmethod
    def get_canvas_type(cls) -> CanvasType:
        return CanvasType.HORIZONTAL

    @classmethod
    def should_process_copy(cls, pipeline_tree: dict) -> bool:
        """水平画布复制时不需要特殊处理"""
        return False


def get_canvas_handler(pipeline_tree: dict) -> Type[CanvasHandler]:
    """获取对应的画布处理器"""
    canvas_mode = pipeline_tree.get("canvas_mode")
    handlers = {
        CanvasType.STAGE.value: StageCanvasHandler,
        CanvasType.VERTICAL.value: VerticalCanvasHandler,
        CanvasType.HORIZONTAL.value: HorizontalCanvasHandler,
    }
    return handlers.get(canvas_mode, HorizontalCanvasHandler)  # 默认使用水平画布处理器


def get_variable_mapping(constants: dict, target_node_ids: set) -> dict:
    """获取节点输出变量到目标变量的映射关系

    Returns:
        dict: 格式为 {node_id: {original_key: target_key}}
    """
    mapping = {}

    # 预先初始化所有目标节点的映射字典
    for node_id in target_node_ids:
        mapping[node_id] = {}

    # 过滤出有效的变量配置
    valid_vars = (
        (var_info["key"], var_info.get("source_info", {}))
        for var_info in constants.values()
        if var_info.get("source_info")
    )

    # 构建映射关系
    for target_key, source_info in valid_vars:
        for node_id, original_vars in source_info.items():
            if node_id in target_node_ids and original_vars:
                mapping[node_id][original_vars[0]] = target_key

    return mapping
