from unittest import mock

import pytest

from bkflow.task.node_log import (
    BaseNodeLogDataSource,
    DatabaseNodeLogDataSource,
    DummyLogDataSource,
    NodeLogDataSourceFactory,
    PaaS3NodeLogDataSource,
)


class TestNodeLogDataSources:
    def test_base_node_log_data_source_abstract(self):
        """Test BaseNodeLogDataSource is abstract"""
        with pytest.raises(TypeError):
            BaseNodeLogDataSource()

    @mock.patch("bkflow.task.node_log.settings")
    def test_paas3_init(self, mock_settings):
        """Test PaaS3NodeLogDataSource initialization"""
        mock_settings.NODE_LOG_DATA_SOURCE_CONFIG = {
            "module_name": "test_module",
            "url": "http://paas3.example.com/{module_name}/{code}/logs",
        }
        mock_settings.APP_CODE = "test_app"
        mock_settings.SECRET_KEY = "test_secret"
        mock_settings.PAASV3_APIGW_API_TOKEN = "test_token"

        source = PaaS3NodeLogDataSource()

        assert source.url == "http://paas3.example.com/test_module/test_app/logs"
        assert source.private_token == "test_token"
        assert "X-Bkapi-Authorization" in source.headers

    @mock.patch("bkflow.task.node_log.requests.get")
    @mock.patch("bkflow.task.node_log.settings")
    def test_paas3_fetch_success(self, mock_settings, mock_get):
        """Test PaaS3 fetch_node_logs success"""
        mock_settings.NODE_LOG_DATA_SOURCE_CONFIG = {"url": "http://paas3.example.com/logs"}
        mock_settings.APP_CODE = "test_app"
        mock_settings.SECRET_KEY = "test_secret"
        mock_settings.PAASV3_APIGW_API_TOKEN = "token"

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "page": {"page": 1, "total": 2},
                "logs": [
                    {"ts": "2023-01-01 10:00:00", "message": "Log 1"},
                    {"ts": "2023-01-01 10:01:00", "message": "Log 2"},
                ],
            }
        }
        mock_get.return_value = mock_response

        source = PaaS3NodeLogDataSource()
        result = source.fetch_node_logs("node_123", "v1", page=1, page_size=30)

        assert result["result"] is True
        assert "2023-01-01 10:00:00: Log 1" in result["data"]["logs"]
        assert "2023-01-01 10:01:00: Log 2" in result["data"]["logs"]

    @mock.patch("bkflow.task.node_log.requests.get")
    @mock.patch("bkflow.task.node_log.settings")
    def test_paas3_fetch_failure(self, mock_settings, mock_get):
        """Test PaaS3 fetch_node_logs when request fails"""
        mock_settings.NODE_LOG_DATA_SOURCE_CONFIG = {"url": "http://paas3.example.com/logs"}
        mock_settings.APP_CODE = "test_app"
        mock_settings.SECRET_KEY = "test_secret"
        mock_settings.PAASV3_APIGW_API_TOKEN = None

        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        source = PaaS3NodeLogDataSource()
        result = source.fetch_node_logs("node_123", "v1")

        assert result["result"] is False
        assert result["data"] is None
        assert result["message"] == "Internal Server Error"

    @mock.patch("bkflow.task.node_log.BambooDjangoRuntime")
    def test_database_fetch(self, mock_runtime):
        """Test DatabaseNodeLogDataSource fetch_node_logs"""
        mock_runtime_instance = mock.Mock()
        mock_runtime_instance.get_plain_log_for_node.return_value = "Test log content"
        mock_runtime.return_value = mock_runtime_instance

        source = DatabaseNodeLogDataSource()
        result = source.fetch_node_logs("node_456", "v2")

        assert result["result"] is True
        assert result["data"]["logs"] == "Test log content"
        assert result["data"]["page_info"] == {}

    def test_dummy_fetch(self):
        """Test DummyLogDataSource fetch_node_logs"""
        source = DummyLogDataSource()
        result = source.fetch_node_logs("node_789", "v3")

        assert result["result"] is True
        assert result["data"]["logs"] == ""
        assert result["data"]["page_info"] == {}

    def test_factory_database(self):
        """Test factory with DATABASE datasource"""
        factory = NodeLogDataSourceFactory("DATABASE")
        assert isinstance(factory.data_source, DatabaseNodeLogDataSource)

    @mock.patch("bkflow.task.node_log.settings")
    def test_factory_paas3(self, mock_settings):
        """Test factory with PaaS3 datasource"""
        mock_settings.NODE_LOG_DATA_SOURCE_CONFIG = {"url": "http://test.com/logs"}
        mock_settings.APP_CODE = "test_app"
        mock_settings.SECRET_KEY = "secret"
        mock_settings.PAASV3_APIGW_API_TOKEN = "token"

        factory = NodeLogDataSourceFactory("PaaS3")
        assert isinstance(factory.data_source, PaaS3NodeLogDataSource)

    def test_factory_dummy(self):
        """Test factory with DUMMY datasource"""
        factory = NodeLogDataSourceFactory("DUMMY")
        assert isinstance(factory.data_source, DummyLogDataSource)

    def test_factory_unknown_defaults_to_database(self):
        """Test factory with unknown datasource defaults to DATABASE"""
        factory = NodeLogDataSourceFactory("UNKNOWN")
        assert isinstance(factory.data_source, DatabaseNodeLogDataSource)

    def test_factory_mappings(self):
        """Test factory DATASOURCE_MAPPINGS"""
        assert "DATABASE" in NodeLogDataSourceFactory.DATASOURCE_MAPPINGS
        assert "PaaS3" in NodeLogDataSourceFactory.DATASOURCE_MAPPINGS
        assert "DUMMY" in NodeLogDataSourceFactory.DATASOURCE_MAPPINGS
