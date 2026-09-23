from unittest import mock

from bkflow.utils.context import TaskContext


class TestTaskContext:
    @mock.patch("bkflow.utils.context.timezone")
    @mock.patch("bkflow.utils.context.datetime")
    def test_task_context(self, mock_dt, mock_tz):
        """Test TaskContext"""
        mock_tz.pytz.timezone.return_value = mock.Mock()
        mock_now = mock.Mock()
        mock_now.strftime.return_value = "2023-12-05 10:30:45"
        mock_dt.datetime.now.return_value = mock_now

        # Normal task
        mock_taskflow = mock.Mock()
        mock_taskflow.space_id = 123
        mock_taskflow.scope_type = "project"
        mock_taskflow.scope_value = "test_project"
        mock_taskflow.executor = "admin"
        mock_taskflow.id = 456
        mock_taskflow.name = "Test Task"
        mock_taskflow.create_method = "API"
        mock_taskflow.extra_info = {}
        context = TaskContext(mock_taskflow)
        assert context.task_space_id == 123
        assert context.is_mock is False

        # Mock task
        mock_taskflow.create_method = "MOCK"
        context = TaskContext(mock_taskflow)
        assert context.is_mock is True

        # Context method
        context_data = context.context()
        assert "${_system}" in context_data
        assert context_data["${_system}"]["type"] == "plain"

        # Class methods
        assert TaskContext.to_flat_key("task_id") == "${_system.task_id}"
        details = TaskContext.flat_details()
        assert "${_system.task_name}" in details
        assert TaskContext.prefix == "_system"
