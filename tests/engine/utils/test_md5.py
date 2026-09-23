"""Test MD5 utils"""
from bkflow.utils.md5 import compute_pipeline_md5


class TestMd5Utils:
    """Test MD5 computation"""

    def test_compute_pipeline_md5(self):
        """Test MD5 computation"""
        # Simple dict
        result = compute_pipeline_md5({"key": "value"})
        assert isinstance(result, str)
        assert len(result) == 32

        # Same data same hash
        data = {"a": 1, "b": 2}
        assert compute_pipeline_md5(data) == compute_pipeline_md5(data)

        # Different data different hash
        assert compute_pipeline_md5({"a": 1}) != compute_pipeline_md5({"a": 2})

        # Complex nested data
        result = compute_pipeline_md5({"pipeline": {"activities": {"node1": {"name": "test"}}, "gateways": {}}})
        assert len(result) == 32

        # List data
        result = compute_pipeline_md5({"items": [1, 2, 3, 4, 5]})
        assert len(result) == 32
