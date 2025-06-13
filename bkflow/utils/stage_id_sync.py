import uuid


class StageCanvasHandler:
    @staticmethod
    def prepare_for_id_replacement(pipeline_tree):
        """
        在 recursive_replace_id 执行前调用，为每个节点添加临时标记

        参数:
            pipeline_tree: 包含 activities 和 stage_canvas_data 的流水线树结构
        """
        # 获取 activities 和 stage_canvas_data
        activities = pipeline_tree.get("activities", {})
        stage_canvas_data = pipeline_tree.get("stage_canvas_data", [])

        # 为每个 activity 添加临时标记
        for activity_id, activity in activities.items():
            # 生成一个唯一标记
            marker = str(uuid.uuid4())
            activity["_temp_marker"] = marker

        # 收集所有需要处理的节点
        all_nodes = []
        for stage in stage_canvas_data:
            for job in stage.get("jobs", []):
                all_nodes.extend(job.get("nodes", []))

        # 为每个节点添加与对应 activity 相同的临时标记
        for node in all_nodes:
            node_id = node.get("id")
            if node_id in activities:
                node["_temp_marker"] = activities[node_id].get("_temp_marker")

    @staticmethod
    def sync_stage_canvas_data_node_ids(pipeline_tree):
        """
        在 recursive_replace_id 执行后调用，同步 stage_canvas_data 中的节点 ID

        参数:
            pipeline_tree: 包含 stage_canvas_data 和 activities 的流水线树结构
        """
        # 获取 activities 和 stage_canvas_data
        activities = pipeline_tree.get("activities", {})
        stage_canvas_data = pipeline_tree.get("stage_canvas_data", [])

        # 构建标记到新 ID 的映射
        marker_to_id = {}
        for activity_id, activity in activities.items():
            marker = activity.pop("_temp_marker", None)
            if marker:
                marker_to_id[marker] = activity_id

        # 收集所有需要处理的节点
        all_nodes = []
        for stage in stage_canvas_data:
            for job in stage.get("jobs", []):
                all_nodes.extend(job.get("nodes", []))

        # 更新节点 ID 并移除临时标记
        for node in all_nodes:
            marker = node.pop("_temp_marker", None)
            if marker and marker in marker_to_id:
                node["id"] = marker_to_id[marker]
