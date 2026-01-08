from unittest import mock

from pipeline.core.constants import PE

from bkflow.task.auto_retry import AutoRetryNodeStrategyCreator


class TestAutoRetryNodeStrategyCreator:
    def test_initialization_and_constants(self):
        """Test initialization and constants"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=123, root_pipeline_id="pipe_456")
        assert creator.taskflow_id == 123
        assert creator.root_pipeline_id == "pipe_456"
        assert AutoRetryNodeStrategyCreator.TASKFLOW_NODE_AUTO_RETRY_MAX_TIMES == 10
        assert AutoRetryNodeStrategyCreator.TASKFLOW_NODE_AUTO_RETRY_MAX_INTERVAL == 10
        assert AutoRetryNodeStrategyCreator.TASKFLOW_NODE_AUTO_RETRY_BATCH_CREATE_COUNT == 1000

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_single_activity_enabled(self, mock_apps):
        """Test batch_create_strategy with single enabled activity"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 5, "interval": 3}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        assert mock_strategy_model.call_count == 1
        call_args = mock_strategy_model.call_args[1]
        assert call_args["taskflow_id"] == 1
        assert call_args["root_pipeline_id"] == "root_1"
        assert call_args["node_id"] == "act1"
        assert call_args["max_retry_times"] == 5
        assert call_args["interval"] == 3

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_disabled(self, mock_apps):
        """Test batch_create_strategy with disabled auto_retry"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": False, "times": 5}},
                "act2": {"type": "ServiceActivity"},
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        assert mock_strategy_model.call_count == 0

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_max_times_limit(self, mock_apps):
        """Test max_retry_times is limited to MAX_TIMES"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 100, "interval": 2}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["max_retry_times"] == 10  # Limited to MAX

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_max_interval_limit(self, mock_apps):
        """Test interval is limited to MAX_INTERVAL"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 3, "interval": 50}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["interval"] == 10  # Limited to MAX

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_negative_values(self, mock_apps):
        """Test negative values are converted with abs()"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": -5, "interval": -3}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["max_retry_times"] == 5
        assert call_args["interval"] == 3

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_invalid_times(self, mock_apps):
        """Test invalid times falls back to default"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": "invalid", "interval": 3}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["max_retry_times"] == 10  # Default MAX_TIMES

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_invalid_interval(self, mock_apps):
        """Test invalid interval falls back to default"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 3, "interval": "invalid"}}
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["interval"] == 10  # Default MAX_INTERVAL

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_subprocess(self, mock_apps):
        """Test batch_create_strategy with SubProcess"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "subproc": {
                    "type": PE.SubProcess,
                    PE.pipeline: {
                        PE.activities: {
                            "sub_act1": {
                                "type": "ServiceActivity",
                                "auto_retry": {"enable": True, "times": 3, "interval": 2},
                            }
                        }
                    },
                }
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        assert mock_strategy_model.call_count == 1
        call_args = mock_strategy_model.call_args[1]
        assert call_args["node_id"] == "sub_act1"

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_multiple_activities(self, mock_apps):
        """Test with multiple activities"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {
            PE.activities: {
                "act1": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 3, "interval": 2}},
                "act2": {"type": "ServiceActivity", "auto_retry": {"enable": True, "times": 5, "interval": 4}},
                "act3": {"type": "ServiceActivity", "auto_retry": {"enable": False}},
            }
        }

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        assert mock_strategy_model.call_count == 2
        mock_strategy_model.objects.bulk_create.assert_called_once()
        assert len(mock_strategy_model.objects.bulk_create.call_args[0][0]) == 2

    @mock.patch("bkflow.task.auto_retry.apps")
    def test_batch_create_strategy_default_values(self, mock_apps):
        """Test default values when times/interval not provided"""
        creator = AutoRetryNodeStrategyCreator(taskflow_id=1, root_pipeline_id="root_1")

        pipeline_tree = {PE.activities: {"act1": {"type": "ServiceActivity", "auto_retry": {"enable": True}}}}

        mock_strategy_model = mock.Mock()
        mock_apps.get_model.return_value = mock_strategy_model

        creator.batch_create_strategy(pipeline_tree)

        call_args = mock_strategy_model.call_args[1]
        assert call_args["max_retry_times"] == 10  # Default MAX_TIMES
        assert call_args["interval"] == 0  # Default interval is 0
