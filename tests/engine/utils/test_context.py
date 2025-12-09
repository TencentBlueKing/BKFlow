from unittest import mock

from bkflow.utils.context import TaskContext


class TestTaskContext:
    @mock.patch("bkflow.utils.context.timezone")
    @mock.patch("bkflow.utils.context.datetime")
    def test_initialization(self, mock_dt, mock_tz):
        """Test TaskContext initialization"""
        mock_tz_obj = mock.Mock()
        mock_tz.pytz.timezone.return_value = mock_tz_obj

        mock_now = mock.Mock()
        mock_now.strftime.return_value = "2023-12-05 10:30:45"
        mock_dt.datetime.now.return_value = mock_now

        mock_taskflow = mock.Mock()
        mock_taskflow.space_id = 123
        mock_taskflow.scope_type = "project"
        mock_taskflow.scope_value = "test_project"
        mock_taskflow.executor = "admin"
        mock_taskflow.id = 456
        mock_taskflow.name = "Test Task"
        mock_taskflow.create_method = "API"

        context = TaskContext(mock_taskflow)

        assert context.task_space_id == 123
        assert context.task_scope_type == "project"
        assert context.task_scope_value == "test_project"
        assert context.operator == "admin"
        assert context.executor == "admin"
        assert context.task_id == 456
        assert context.task_name == "Test Task"
        assert context.is_mock is False
        assert context.task_start_time == "2023-12-05 10:30:45"

    @mock.patch("bkflow.utils.context.timezone")
    @mock.patch("bkflow.utils.context.datetime")
    def test_initialization_mock_task(self, mock_dt, mock_tz):
        """Test TaskContext with mock task"""
        mock_tz_obj = mock.Mock()
        mock_tz.pytz.timezone.return_value = mock_tz_obj

        mock_now = mock.Mock()
        mock_now.strftime.return_value = "2023-12-05 10:30:45"
        mock_dt.datetime.now.return_value = mock_now

        mock_taskflow = mock.Mock()
        mock_taskflow.space_id = 1
        mock_taskflow.scope_type = "test"
        mock_taskflow.scope_value = "value"
        mock_taskflow.executor = "user"
        mock_taskflow.id = 1
        mock_taskflow.name = "Mock Task"
        mock_taskflow.create_method = "MOCK"

        context = TaskContext(mock_taskflow)
        assert context.is_mock is True

    @mock.patch("bkflow.utils.context.timezone")
    @mock.patch("bkflow.utils.context.datetime")
    def test_context_method(self, mock_dt, mock_tz):
        """Test context method returns proper format"""
        mock_tz_obj = mock.Mock()
        mock_tz.pytz.timezone.return_value = mock_tz_obj

        mock_now = mock.Mock()
        mock_now.strftime.return_value = "2023-12-05 10:30:45"
        mock_dt.datetime.now.return_value = mock_now

        mock_taskflow = mock.Mock()
        mock_taskflow.space_id = 1
        mock_taskflow.scope_type = "test"
        mock_taskflow.scope_value = "value"
        mock_taskflow.executor = "user"
        mock_taskflow.id = 1
        mock_taskflow.name = "Test"
        mock_taskflow.create_method = "API"

        task_context = TaskContext(mock_taskflow)
        context_data = task_context.context()

        assert "${_system}" in context_data
        assert context_data["${_system}"]["type"] == "plain"
        assert context_data["${_system}"]["is_param"] is True
        assert context_data["${_system}"]["value"] == task_context

    def test_to_flat_key(self):
        """Test to_flat_key class method"""
        result = TaskContext.to_flat_key("task_id")
        assert result == "${_system.task_id}"

        result = TaskContext.to_flat_key("task_name")
        assert result == "${_system.task_name}"

    def test_flat_details(self):
        """Test flat_details class method"""
        details = TaskContext.flat_details()

        assert "${_system.task_name}" in details
        assert "${_system.task_id}" in details
        assert "${_system.task_start_time}" in details
        assert "${_system.operator}" in details

        task_name_detail = details["${_system.task_name}"]
        assert task_name_detail["key"] == "${_system.task_name}"
        assert task_name_detail["index"] == -1
        assert task_name_detail["show_type"] == "hide"
        assert task_name_detail["source_type"] == "system"
        assert task_name_detail["value"] == ""
        assert task_name_detail["hook"] is False

    def test_prefix_constant(self):
        """Test prefix constant"""
        assert TaskContext.prefix == "_system"
