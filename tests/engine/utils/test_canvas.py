from bkflow.utils.canvas import (
    CanvasType,
    HorizontalCanvasHandler,
    OperateType,
    StageCanvasHandler,
    VerticalCanvasHandler,
    get_canvas_handler,
    get_variable_mapping,
)


class TestEnums:
    def test_enums(self):
        """Test enum values"""
        assert OperateType.CREATE_TEMPLATE.value == "create_template"
        assert OperateType.COPY_TEMPLATE.value == "copy_template"
        assert OperateType.UPDATE_TEMPLATE.value == "update_template"
        assert CanvasType.STAGE.value == "stage"
        assert CanvasType.VERTICAL.value == "vertical"
        assert CanvasType.HORIZONTAL.value == "horizontal"


class TestStageCanvasHandler:
    def test_get_canvas_type(self):
        """Test get_canvas_type returns STAGE"""
        assert StageCanvasHandler.get_canvas_type() == CanvasType.STAGE

    def test_is_canvas_type(self):
        """Test is_canvas_type with various canvas modes"""
        assert StageCanvasHandler.is_canvas_type({"canvas_mode": "stage"}) is True
        assert StageCanvasHandler.is_canvas_type({"canvas_mode": "vertical"}) is False

    def test_should_process_copy(self):
        """Test should_process_copy for stage and non-stage"""
        assert StageCanvasHandler.should_process_copy({"canvas_mode": "stage"}) is True
        assert StageCanvasHandler.should_process_copy({"canvas_mode": "vertical"}) is False

    def test_should_generate_node_map(self):
        """Test should_generate_node_map with and without node_map"""
        assert StageCanvasHandler.should_generate_node_map({"canvas_mode": "stage"}, None) is True
        assert StageCanvasHandler.should_generate_node_map({"canvas_mode": "stage"}, {"node1": "new_node1"}) is False

    def test_sync_stage_canvas_data_node_ids(self):
        """Test sync_stage_canvas_data_node_ids updates node IDs"""
        node_map = {"node1": "new_node1", "node2": "new_node2"}
        pipeline_tree = {
            "stage_canvas_data": [
                {
                    "id": "stage1",
                    "jobs": [
                        {
                            "id": "job1",
                            "nodes": [
                                {"id": "node1", "option": {"id": "node1"}},
                                {"id": "node2"},
                            ],
                        }
                    ],
                }
            ]
        }

        result = StageCanvasHandler.sync_stage_canvas_data_node_ids(node_map, pipeline_tree)

        assert result["stage_canvas_data"][0]["jobs"][0]["nodes"][0]["id"] == "new_node1"
        assert result["stage_canvas_data"][0]["jobs"][0]["nodes"][0]["option"]["id"] == "new_node1"
        assert result["stage_canvas_data"][0]["jobs"][0]["nodes"][1]["id"] == "new_node2"

    def test_handle_node_replacement(self):
        """Test handle_node_replacement calls sync method"""
        node_map = {"node1": "new_node1"}
        pipeline_tree = {"stage_canvas_data": [{"id": "stage1", "jobs": [{"id": "job1", "nodes": [{"id": "node1"}]}]}]}

        StageCanvasHandler.handle_node_replacement(pipeline_tree, node_map)
        assert pipeline_tree["stage_canvas_data"][0]["jobs"][0]["nodes"][0]["id"] == "new_node1"


class TestVerticalCanvasHandler:
    def test_vertical_handler(self):
        """Test VerticalCanvasHandler methods"""
        assert VerticalCanvasHandler.get_canvas_type() == CanvasType.VERTICAL
        assert VerticalCanvasHandler.should_process_copy({"canvas_mode": "vertical"}) is False


class TestHorizontalCanvasHandler:
    def test_horizontal_handler(self):
        """Test HorizontalCanvasHandler methods"""
        assert HorizontalCanvasHandler.get_canvas_type() == CanvasType.HORIZONTAL
        assert HorizontalCanvasHandler.should_process_copy({"canvas_mode": "horizontal"}) is False


class TestGetCanvasHandler:
    def test_get_handler(self):
        """Test get_canvas_handler for various modes"""
        assert get_canvas_handler({"canvas_mode": "stage"}) == StageCanvasHandler
        assert get_canvas_handler({"canvas_mode": "vertical"}) == VerticalCanvasHandler
        assert get_canvas_handler({"canvas_mode": "horizontal"}) == HorizontalCanvasHandler
        assert get_canvas_handler({"canvas_mode": "unknown"}) == HorizontalCanvasHandler


class TestGetVariableMapping:
    def test_basic_mapping(self):
        """Test get_variable_mapping with basic source_info"""
        constants = {
            "var1": {"key": "target_key1", "source_info": {"node1": ["original_key1"], "node2": ["original_key2"]}}
        }
        target_node_ids = {"node1", "node2"}

        result = get_variable_mapping(constants, target_node_ids)

        assert result == {"node1": {"original_key1": "target_key1"}, "node2": {"original_key2": "target_key1"}}

    def test_variable_mapping_edge_cases(self):
        """Test get_variable_mapping edge cases"""
        # No source_info
        assert get_variable_mapping({"var1": {"key": "target_key1"}}, {"node1"}) == {"node1": {}}

        # Filtered nodes
        constants = {
            "var1": {
                "key": "target_key1",
                "source_info": {"node1": ["original_key1"], "node_not_target": ["original_key2"]},
            }
        }
        assert get_variable_mapping(constants, {"node1"}) == {"node1": {"original_key1": "target_key1"}}

        # Empty original_vars
        constants = {"var1": {"key": "target_key1", "source_info": {"node1": [], "node2": ["original_key1"]}}}
        assert get_variable_mapping(constants, {"node1", "node2"}) == {
            "node1": {},
            "node2": {"original_key1": "target_key1"},
        }

        # Multiple original keys uses first
        constants = {"var1": {"key": "target_key1", "source_info": {"node1": ["key1", "key2", "key3"]}}}
        assert get_variable_mapping(constants, {"node1"}) == {"node1": {"key1": "target_key1"}}
