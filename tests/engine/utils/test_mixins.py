from unittest import mock

import pytest

from bkflow.exceptions import UserNotFound
from bkflow.utils.mixins import (
    BKFLOWCommonMixin,
    BKFLOWDefaultPagination,
    BKFLOWNoMaxLimitPagination,
    BKFlowOrderingFilter,
    CustomViewSetMixin,
)


class TestCustomViewSetMixin:
    def test_perform_create_with_username(self):
        """Test perform_create with valid username"""
        mixin = CustomViewSetMixin()

        mock_serializer = mock.Mock()
        mock_request = mock.Mock()
        mock_request.user.username = "test_user"
        mock_serializer.context = {"request": mock_request}

        mixin.perform_create(mock_serializer)
        mock_serializer.save.assert_called_once_with(creator="test_user", updated_by="test_user")

    def test_perform_create_without_username(self):
        """Test perform_create raises UserNotFound when no username"""
        mixin = CustomViewSetMixin()

        mock_serializer = mock.Mock()
        mock_request = mock.Mock()
        mock_request.user = mock.Mock(spec=[])  # No username attribute
        mock_serializer.context = {"request": mock_request}

        with pytest.raises(UserNotFound):
            mixin.perform_create(mock_serializer)

    def test_perform_update_with_username(self):
        """Test perform_update with valid username"""
        mixin = CustomViewSetMixin()

        mock_serializer = mock.Mock()
        mock_request = mock.Mock()
        mock_request.user.username = "updater"
        mock_serializer.context = {"request": mock_request}

        mixin.perform_update(mock_serializer)
        mock_serializer.save.assert_called_once_with(updated_by="updater")

    def test_perform_update_without_username(self):
        """Test perform_update raises UserNotFound when no username"""
        mixin = CustomViewSetMixin()

        mock_serializer = mock.Mock()
        mock_request = mock.Mock()
        mock_request.user = mock.Mock(spec=[])
        mock_serializer.context = {"request": mock_request}

        with pytest.raises(UserNotFound):
            mixin.perform_update(mock_serializer)


class TestBKFLOWDefaultPagination:
    def test_default_limit(self):
        """Test default_limit is 10"""
        pagination = BKFLOWDefaultPagination()
        assert pagination.default_limit == 10

    def test_max_limit(self):
        """Test max_limit is 200"""
        pagination = BKFLOWDefaultPagination()
        assert pagination.max_limit == 200


class TestBKFLOWNoMaxLimitPagination:
    def test_default_limit(self):
        """Test default_limit is 10"""
        pagination = BKFLOWNoMaxLimitPagination()
        assert pagination.default_limit == 10

    def test_limit_query_param(self):
        """Test limit_query_param attribute exists"""
        pagination = BKFLOWNoMaxLimitPagination()
        assert hasattr(pagination, "limit_query_param")


class TestBKFlowOrderingFilter:
    def test_ordering_param(self):
        """Test ordering_param is order_by"""
        filter_instance = BKFlowOrderingFilter()
        assert filter_instance.ordering_param == "order_by"


class TestBKFLOWCommonMixin:
    def test_get_queryset(self):
        """Test get_queryset with default and action-specific queryset"""
        mixin = BKFLOWCommonMixin()
        mixin.queryset = ["default"]
        mixin.action = "list"

        with mock.patch.object(BKFLOWCommonMixin.__bases__[0], "get_queryset", return_value=["default"]):
            assert mixin.get_queryset() == ["default"]

        mixin.list_queryset = ["list_specific"]
        with mock.patch.object(BKFLOWCommonMixin.__bases__[0], "get_queryset", return_value=["list_specific"]):
            assert mixin.get_queryset() == ["list_specific"]

    def test_get_serializer_class(self):
        """Test get_serializer_class with default and action-specific serializer"""

        class MockSerializerClass:
            pass

        class CustomSerializer:
            pass

        mixin = BKFLOWCommonMixin()
        mixin.serializer_class = MockSerializerClass
        mixin.action = "list"

        with mock.patch.object(
            BKFLOWCommonMixin.__bases__[0], "get_serializer_class", return_value=MockSerializerClass
        ):
            assert mixin.get_serializer_class() == MockSerializerClass

        mixin.retrieve_serializer_class = CustomSerializer
        mixin.action = "retrieve"
        with mock.patch.object(BKFLOWCommonMixin.__bases__[0], "get_serializer_class", return_value=CustomSerializer):
            assert mixin.get_serializer_class() == CustomSerializer
