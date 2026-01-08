from unittest import mock

import pytest

from bkflow.task.node_timeout import (
    ForcedFailAndSkipStrategy,
    ForcedFailStrategy,
    NodeTimeoutStrategy,
    node_timeout_handler,
)


class TestNodeTimeoutStrategies:
    def test_timeout_strategies(self):
        """Test timeout strategies"""
        mock_task = mock.Mock()

        # ForcedFailStrategy
        strategy = ForcedFailStrategy()
        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
            mock_result = {"result": True, "message": "Node forced to fail"}
            mock_operation.return_value.forced_fail.return_value = mock_result
            result = strategy.deal_with_timeout_node(mock_task, "node_123")
            assert result == mock_result

        # ForcedFailAndSkipStrategy - both succeed
        strategy = ForcedFailAndSkipStrategy()
        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
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
            result = strategy.deal_with_timeout_node(mock_task, "node_456")
            assert result == {"result": True, "message": "Skipped"}

        # ForcedFailAndSkipStrategy - fail on forced_fail
        with mock.patch("bkflow.task.node_timeout.TaskNodeOperation") as mock_operation:
            mock_fail_result = type(
                "obj",
                (object,),
                {"result": False, "__iter__": lambda s: iter([("result", False), ("message", "Failed")])},
            )()
            mock_operation.return_value.forced_fail.return_value = mock_fail_result
            result = strategy.deal_with_timeout_node(mock_task, "node_789")
            assert result == {"result": False, "message": "Failed"}

        # Registry and constants
        assert "forced_fail" in node_timeout_handler
        assert isinstance(node_timeout_handler["forced_fail"], ForcedFailStrategy)
        assert NodeTimeoutStrategy.TIMEOUT_NODE_OPERATOR == "bkflow_engine"

        # Abstract base
        with pytest.raises(TypeError):
            NodeTimeoutStrategy()
