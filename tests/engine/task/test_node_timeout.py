from unittest import mock

import pytest

from bkflow.task.node_timeout import (
    ForcedFailAndSkipStrategy,
    ForcedFailStrategy,
    NodeTimeoutStrategy,
    node_timeout_handler,
)


class TestNodeTimeoutStrategies:
    def test_forced_fail_strategy_success(self):
        """Test ForcedFailStrategy forces node to fail"""
        mock_task = mock.Mock()
        node_id = "node_123"

        strategy = ForcedFailStrategy()

        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
            mock_result = {"result": True, "message": "Node forced to fail"}
            mock_operation.return_value.forced_fail.return_value = mock_result

            result = strategy.deal_with_timeout_node(mock_task, node_id)

            mock_operation.assert_called_once_with(mock_task, node_id)
            mock_operation.return_value.forced_fail.assert_called_once_with(operator="bkflow_engine")
            assert result == mock_result

    def test_forced_fail_and_skip_strategy_both_succeed(self):
        """Test ForcedFailAndSkipStrategy when both operations succeed"""
        mock_task = mock.Mock()
        node_id = "node_456"

        strategy = ForcedFailAndSkipStrategy()

        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
            # Create mock result objects with .result attribute
            mock_fail_result = type(
                "obj", (object,), {"result": True, "__iter__": lambda s: iter([("result", True)])}
            )()

            mock_skip_result = type(
                "obj",
                (object,),
                {"result": True, "__iter__": lambda s: iter([("result", True), ("message", "Skipped")])},
            )()

            mock_operation.return_value.forced_fail.return_value = mock_fail_result
            mock_operation.return_value.skip.return_value = mock_skip_result

            result = strategy.deal_with_timeout_node(mock_task, node_id)

            assert mock_operation.call_count == 2
            mock_operation.return_value.forced_fail.assert_called_once_with(operator="bkflow_engine")
            mock_operation.return_value.skip.assert_called_once_with(operator="bkflow_engine")
            assert result == {"result": True, "message": "Skipped"}

    def test_forced_fail_and_skip_strategy_fail_on_forced_fail(self):
        """Test ForcedFailAndSkipStrategy when forced_fail fails"""
        mock_task = mock.Mock()
        node_id = "node_789"

        strategy = ForcedFailAndSkipStrategy()

        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
            mock_fail_result = type(
                "obj",
                (object,),
                {"result": False, "__iter__": lambda s: iter([("result", False), ("message", "Failed")])},
            )()

            mock_operation.return_value.forced_fail.return_value = mock_fail_result

            result = strategy.deal_with_timeout_node(mock_task, node_id)

            mock_operation.return_value.forced_fail.assert_called_once_with(operator="bkflow_engine")
            assert mock_operation.return_value.skip.call_count == 0
            assert result == {"result": False, "message": "Failed"}

    def test_node_timeout_handler_registry(self):
        """Test node_timeout_handler contains expected strategies"""
        assert "forced_fail" in node_timeout_handler
        assert "forced_fail_and_skip" in node_timeout_handler

        assert isinstance(node_timeout_handler["forced_fail"], ForcedFailStrategy)
        assert isinstance(node_timeout_handler["forced_fail_and_skip"], ForcedFailAndSkipStrategy)

    def test_timeout_node_operator_constant(self):
        """Test TIMEOUT_NODE_OPERATOR constant"""
        assert NodeTimeoutStrategy.TIMEOUT_NODE_OPERATOR == "bkflow_engine"
        assert ForcedFailStrategy.TIMEOUT_NODE_OPERATOR == "bkflow_engine"
        assert ForcedFailAndSkipStrategy.TIMEOUT_NODE_OPERATOR == "bkflow_engine"

    def test_base_strategy_is_abstract(self):
        """Test NodeTimeoutStrategy is abstract"""
        with pytest.raises(TypeError):
            NodeTimeoutStrategy()
