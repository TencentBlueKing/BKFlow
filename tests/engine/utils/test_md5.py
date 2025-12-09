"""Test MD5 utils"""
from bkflow.utils.md5 import compute_pipeline_md5


class TestMd5Utils:
    """Test MD5 computation"""

    def test_compute_simple_dict(self):
        """Test MD5 of simple dict"""
        data = {"key": "value"}
        result = compute_pipeline_md5(data)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_compute_same_data_same_hash(self):
        """Test same data produces same hash"""
        data = {"a": 1, "b": 2}
        hash1 = compute_pipeline_md5(data)
        hash2 = compute_pipeline_md5(data)
        assert hash1 == hash2

    def test_compute_different_data_different_hash(self):
        """Test different data produces different hash"""
        data1 = {"a": 1}
        data2 = {"a": 2}
        hash1 = compute_pipeline_md5(data1)
        hash2 = compute_pipeline_md5(data2)
        assert hash1 != hash2

    def test_compute_complex_data(self):
        """Test MD5 of complex nested data"""
        data = {
            "pipeline": {
                "activities": {"node1": {"name": "test"}},
                "gateways": {},
            }
        }
        result = compute_pipeline_md5(data)
        assert len(result) == 32

    def test_compute_list_data(self):
        """Test MD5 with list data"""
        data = {"items": [1, 2, 3, 4, 5]}
        result = compute_pipeline_md5(data)
        assert len(result) == 32
