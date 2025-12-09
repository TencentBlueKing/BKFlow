"""Test string utils"""
from unittest import mock

from bkflow.utils.strings import standardize_name, standardize_pipeline_node_name


class TestStringUtils:
    """Test string utility functions"""

    def test_standardize_name_normal(self):
        """Test normal name without special chars"""
        result = standardize_name("normal_name", 50)
        assert result == "normal_name"

    def test_standardize_name_with_special_chars(self):
        """Test name with special characters"""
        result = standardize_name("test<name>with$special&chars", 50)
        assert result == "testnamewithspecialchars"

    def test_standardize_name_with_quotes(self):
        """Test name with quotes"""
        result = standardize_name("name'with\"quotes", 50)
        assert result == "namewithquotes"

    def test_standardize_name_truncate(self):
        """Test name truncation"""
        long_name = "a" * 100
        result = standardize_name(long_name, 10)
        assert len(result) == 10
        assert result == "a" * 10

    def test_standardize_name_empty(self):
        """Test empty name"""
        result = standardize_name("", 50)
        assert result == ""

    def test_standardize_pipeline_simple(self):
        """Test standardizing simple pipeline"""
        pipeline = {"activities": {"node1": {"name": "test<node>"}}}
        standardize_pipeline_node_name(pipeline)
        assert pipeline["activities"]["node1"]["name"] == "testnode"

    def test_standardize_pipeline_nested(self):
        """Test standardizing nested pipeline structure"""
        pipeline = {
            "activities": {"node1": {"name": "test$name"}, "node2": {"name": "another&name"}},
            "gateways": {"gate1": {"name": "gateway'name"}},
        }
        standardize_pipeline_node_name(pipeline)
        assert pipeline["activities"]["node1"]["name"] == "testname"
        assert pipeline["activities"]["node2"]["name"] == "anothername"
        assert pipeline["gateways"]["gate1"]["name"] == "gatewayname"

    def test_standardize_pipeline_with_list(self):
        """Test standardizing pipeline with list values"""
        pipeline = {"items": [{"name": "item<1>"}, {"name": "item$2"}]}
        standardize_pipeline_node_name(pipeline)
        assert pipeline["items"][0]["name"] == "item1"
        assert pipeline["items"][1]["name"] == "item2"

    def test_standardize_pipeline_mixed(self):
        """Test standardizing pipeline with mixed structures"""
        pipeline = {
            "activities": {"node1": {"name": "test&node", "type": "ServiceActivity"}},
            "list_items": [{"name": "item'1'", "value": 1}],
        }
        standardize_pipeline_node_name(pipeline)
        assert pipeline["activities"]["node1"]["name"] == "testnode"
        assert pipeline["list_items"][0]["name"] == "item1"

    @mock.patch("bkflow.utils.strings.TEMPLATE_NODE_NAME_MAX_LENGTH", 10)
    def test_standardize_pipeline_truncate(self):
        """Test pipeline name truncation"""
        pipeline = {"activities": {"node1": {"name": "a" * 20}}}
        standardize_pipeline_node_name(pipeline)
        assert len(pipeline["activities"]["node1"]["name"]) == 10
