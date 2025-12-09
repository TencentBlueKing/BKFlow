"""Test APIGW utils"""
from unittest import mock

import pytest

from bkflow.apigw.utils import get_space_config_presentation, paginate_list_data


class TestApigwUtils:
    """Test APIGW utility functions"""

    @mock.patch("bkflow.apigw.utils.SpaceConfig.objects.get_space_config_info")
    def test_get_space_config_presentation(self, mock_get_config):
        """Test getting space config presentation"""
        mock_get_config.return_value = [{"key": "key1", "value": "value1"}, {"key": "key2", "value": "value2"}]

        result = get_space_config_presentation(1)

        assert result["space_id"] == 1
        assert len(result["config"]) == 2
        mock_get_config.assert_called_once_with(space_id=1)

    def test_paginate_list_data_default(self):
        """Test pagination with default params"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: default

        mock_queryset = list(range(150))
        mock_qs = mock.Mock()
        mock_qs.count.return_value = 150
        mock_qs.__getitem__ = lambda self, key: mock_queryset[key]

        results, count = paginate_list_data(mock_request, mock_qs)

        assert count == 150
        assert len(results) == 100

    def test_paginate_list_data_custom_params(self):
        """Test pagination with custom offset and limit"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: {"offset": "10", "limit": "20"}.get(key, default)

        mock_queryset = list(range(100))
        mock_qs = mock.Mock()
        mock_qs.count.return_value = 100
        mock_qs.__getitem__ = lambda self, key: mock_queryset[key]

        results, count = paginate_list_data(mock_request, mock_qs)

        assert count == 100
        assert len(results) == 20
        assert results[0] == 10

    def test_paginate_list_data_max_limit(self):
        """Test pagination with limit exceeding max"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: {
            "offset": "0",
            "limit": "300",  # Exceeds max of 200
        }.get(key, default)

        mock_queryset = list(range(300))
        mock_qs = mock.Mock()
        mock_qs.count.return_value = 300
        mock_qs.__getitem__ = lambda self, key: mock_queryset[key]

        results, count = paginate_list_data(mock_request, mock_qs)

        assert count == 300
        assert len(results) == 200

    def test_paginate_list_data_negative_offset(self):
        """Test pagination with negative offset"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: {"offset": "-1", "limit": "10"}.get(key, default)

        mock_qs = mock.Mock()
        mock_qs.count.return_value = 100

        with pytest.raises(Exception, match="pagination error"):
            paginate_list_data(mock_request, mock_qs)

    def test_paginate_list_data_negative_limit(self):
        """Test pagination with negative limit"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: {"offset": "0", "limit": "-10"}.get(key, default)

        mock_qs = mock.Mock()
        mock_qs.count.return_value = 100

        with pytest.raises(Exception, match="pagination error"):
            paginate_list_data(mock_request, mock_qs)

    def test_paginate_list_data_invalid_params(self):
        """Test pagination with invalid params"""
        mock_request = mock.Mock()
        mock_request.GET.get.side_effect = lambda key, default: {"offset": "invalid", "limit": "10"}.get(key, default)

        mock_qs = mock.Mock()

        with pytest.raises(Exception, match="pagination error"):
            paginate_list_data(mock_request, mock_qs)
