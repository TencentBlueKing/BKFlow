"""Test string utils"""
from unittest import mock

from bkflow.utils.strings import standardize_name, standardize_pipeline_node_name


class TestStringUtils:
    """Test string utility functions"""

    def test_standardize_name(self):
        """Test standardize_name with various inputs"""
        assert standardize_name("normal_name", 50) == "normal_name"
        assert standardize_name("test<name>with$special&chars", 50) == "testnamewithspecialchars"
        assert standardize_name("name'with\"quotes", 50) == "namewithquotes"
        assert standardize_name("", 50) == ""

        # Truncation
        long_name = "a" * 100
        result = standardize_name(long_name, 10)
        assert len(result) == 10
        assert result == "a" * 10

    def test_standardize_pipeline_node_name(self):
        """Test standardizing pipeline node names"""
        # Simple pipeline
        pipeline = {"activities": {"node1": {"name": "test<node>"}}}
        standardize_pipeline_node_name(pipeline)
        assert pipeline["activities"]["node1"]["name"] == "testnode"

        # Nested structure
        pipeline = {
            "activities": {"node1": {"name": "test$name"}, "node2": {"name": "another&name"}},
            "gateways": {"gate1": {"name": "gateway'name"}},
        }
        standardize_pipeline_node_name(pipeline)
        assert pipeline["activities"]["node1"]["name"] == "testname"
        assert pipeline["gateways"]["gate1"]["name"] == "gatewayname"

        # List values
        pipeline = {"items": [{"name": "item<1>"}, {"name": "item$2"}]}
        standardize_pipeline_node_name(pipeline)
        assert pipeline["items"][0]["name"] == "item1"

        # Truncation
        with mock.patch("bkflow.utils.strings.TEMPLATE_NODE_NAME_MAX_LENGTH", 10):
            pipeline = {"activities": {"node1": {"name": "a" * 20}}}
            standardize_pipeline_node_name(pipeline)
            assert len(pipeline["activities"]["node1"]["name"]) == 10
