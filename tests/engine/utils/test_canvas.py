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
    def test_operate_type_enum(self):
        """Test OperateType enum values"""
        assert OperateType.CREATE_TEMPLATE.value == "create_template"
        assert OperateType.COPY_TEMPLATE.value == "copy_template"
        assert OperateType.UPDATE_TEMPLATE.value == "update_template"

    def test_canvas_type_enum(self):
        """Test CanvasType enum values"""
        assert CanvasType.STAGE.value == "stage"
        assert CanvasType.VERTICAL.value == "vertical"
        assert CanvasType.HORIZONTAL.value == "horizontal"


class TestStageCanvasHandler:
    def test_get_canvas_type(self):
        """Test get_canvas_type returns STAGE"""
        assert StageCanvasHandler.get_canvas_type() == CanvasType.STAGE

    def test_is_canvas_type_match(self):
        """Test is_canvas_type with matching canvas_mode"""
        pipeline_tree = {"canvas_mode": "stage"}
        assert StageCanvasHandler.is_canvas_type(pipeline_tree) is True

    def test_is_canvas_type_no_match(self):
        """Test is_canvas_type with non-matching canvas_mode"""
        pipeline_tree = {"canvas_mode": "vertical"}
        assert StageCanvasHandler.is_canvas_type(pipeline_tree) is False

    def test_should_process_copy_for_stage(self):
        """Test should_process_copy returns True for stage canvas"""
        pipeline_tree = {"canvas_mode": "stage"}
        assert StageCanvasHandler.should_process_copy(pipeline_tree) is True

    def test_should_process_copy_for_non_stage(self):
        """Test should_process_copy returns False for non-stage"""
        pipeline_tree = {"canvas_mode": "vertical"}
        assert StageCanvasHandler.should_process_copy(pipeline_tree) is False

    def test_should_generate_node_map_without_map(self):
        """Test should_generate_node_map when node_map is None"""
        pipeline_tree = {"canvas_mode": "stage"}
        assert StageCanvasHandler.should_generate_node_map(pipeline_tree, None) is True

    def test_should_generate_node_map_with_map(self):
        """Test should_generate_node_map when node_map exists"""
        pipeline_tree = {"canvas_mode": "stage"}
        node_map = {"node1": "new_node1"}
        assert StageCanvasHandler.should_generate_node_map(pipeline_tree, node_map) is False

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
    def test_get_canvas_type(self):
        """Test get_canvas_type returns VERTICAL"""
        assert VerticalCanvasHandler.get_canvas_type() == CanvasType.VERTICAL

    def test_should_process_copy(self):
        """Test should_process_copy returns False"""
        pipeline_tree = {"canvas_mode": "vertical"}
        assert VerticalCanvasHandler.should_process_copy(pipeline_tree) is False


class TestHorizontalCanvasHandler:
    def test_get_canvas_type(self):
        """Test get_canvas_type returns HORIZONTAL"""
        assert HorizontalCanvasHandler.get_canvas_type() == CanvasType.HORIZONTAL

    def test_should_process_copy(self):
        """Test should_process_copy returns False"""
        pipeline_tree = {"canvas_mode": "horizontal"}
        assert HorizontalCanvasHandler.should_process_copy(pipeline_tree) is False


class TestGetCanvasHandler:
    def test_get_handler_stage(self):
        """Test get_canvas_handler for stage mode"""
        pipeline_tree = {"canvas_mode": "stage"}
        handler = get_canvas_handler(pipeline_tree)
        assert handler == StageCanvasHandler

    def test_get_handler_vertical(self):
        """Test get_canvas_handler for vertical mode"""
        pipeline_tree = {"canvas_mode": "vertical"}
        handler = get_canvas_handler(pipeline_tree)
        assert handler == VerticalCanvasHandler

    def test_get_handler_horizontal(self):
        """Test get_canvas_handler for horizontal mode"""
        pipeline_tree = {"canvas_mode": "horizontal"}
        handler = get_canvas_handler(pipeline_tree)
        assert handler == HorizontalCanvasHandler

    def test_get_handler_unknown_defaults_to_horizontal(self):
        """Test get_canvas_handler defaults to HorizontalCanvasHandler"""
        pipeline_tree = {"canvas_mode": "unknown"}
        handler = get_canvas_handler(pipeline_tree)
        assert handler == HorizontalCanvasHandler


class TestGetVariableMapping:
    def test_basic_mapping(self):
        """Test get_variable_mapping with basic source_info"""
        constants = {
            "var1": {"key": "target_key1", "source_info": {"node1": ["original_key1"], "node2": ["original_key2"]}}
        }
        target_node_ids = {"node1", "node2"}

        result = get_variable_mapping(constants, target_node_ids)

        assert result == {"node1": {"original_key1": "target_key1"}, "node2": {"original_key2": "target_key1"}}

    def test_no_source_info(self):
        """Test with constants without source_info"""
        constants = {"var1": {"key": "target_key1"}, "var2": {"key": "target_key2", "source_info": {}}}
        target_node_ids = {"node1"}

        result = get_variable_mapping(constants, target_node_ids)
        assert result == {"node1": {}}

    def test_filtered_nodes(self):
        """Test nodes not in target_node_ids are filtered"""
        constants = {
            "var1": {
                "key": "target_key1",
                "source_info": {"node1": ["original_key1"], "node_not_target": ["original_key2"]},
            }
        }
        target_node_ids = {"node1"}

        result = get_variable_mapping(constants, target_node_ids)
        assert result == {"node1": {"original_key1": "target_key1"}}

    def test_empty_original_vars(self):
        """Test with empty original_vars list"""
        constants = {"var1": {"key": "target_key1", "source_info": {"node1": [], "node2": ["original_key1"]}}}
        target_node_ids = {"node1", "node2"}

        result = get_variable_mapping(constants, target_node_ids)
        assert result == {"node1": {}, "node2": {"original_key1": "target_key1"}}

    def test_multiple_original_keys_uses_first(self):
        """Test only first original key is used"""
        constants = {"var1": {"key": "target_key1", "source_info": {"node1": ["key1", "key2", "key3"]}}}
        target_node_ids = {"node1"}

        result = get_variable_mapping(constants, target_node_ids)
        assert result == {"node1": {"key1": "target_key1"}}
