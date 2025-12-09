import logging
from unittest import mock

from bkflow.utils.logging import BambooEngineNodeInfoFilter, TraceIDInjectFilter


class TestLoggingFilters:
    def setup_method(self):
        """Setup test record"""
        self.record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=10, msg="Test message", args=(), exc_info=None
        )

    @mock.patch("bkflow.utils.logging.local")
    def test_trace_id_inject_with_trace_id(self, mock_local):
        """Test TraceIDInjectFilter when trace_id exists"""
        mock_local.trace_id = "test_trace_123"

        filter_instance = TraceIDInjectFilter()
        result = filter_instance.filter(self.record)

        assert result is True
        assert self.record.trace_id == "test_trace_123"

    @mock.patch("bkflow.utils.logging.local")
    def test_trace_id_inject_without_trace_id(self, mock_local):
        """Test TraceIDInjectFilter when trace_id does not exist"""
        # Remove trace_id attribute if exists
        if hasattr(mock_local, "trace_id"):
            del mock_local.trace_id

        filter_instance = TraceIDInjectFilter()
        result = filter_instance.filter(self.record)

        assert result is True
        assert self.record.trace_id is None

    @mock.patch("bkflow.utils.logging.engine_local")
    def test_bamboo_engine_filter_with_node_info(self, mock_engine_local):
        """Test BambooEngineNodeInfoFilter when node info exists"""
        mock_node_info = mock.Mock()
        mock_node_info.node_id = "node_123"
        mock_node_info.version = "v1.0"
        mock_engine_local.get_node_info.return_value = mock_node_info

        filter_instance = BambooEngineNodeInfoFilter()
        result = filter_instance.filter(self.record)

        assert result is True
        assert self.record.node_id == "node_123"
        assert self.record.version == "v1.0"

    @mock.patch("bkflow.utils.logging.engine_local")
    def test_bamboo_engine_filter_without_node_info(self, mock_engine_local):
        """Test BambooEngineNodeInfoFilter when node info is None"""
        mock_engine_local.get_node_info.return_value = None

        filter_instance = BambooEngineNodeInfoFilter()
        result = filter_instance.filter(self.record)

        assert result is True
        assert not hasattr(self.record, "node_id")
        assert not hasattr(self.record, "version")
