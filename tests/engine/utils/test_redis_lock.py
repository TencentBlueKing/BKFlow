"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from unittest import mock

import pytest
from redis.exceptions import LockError

from bkflow.utils.redis_lock import acquire_redis_lock, redis_lock, release_redis_lock


class TestAcquireRedisLock:
    """Test acquire_redis_lock function"""

    def test_acquire_lock(self):
        """Test acquiring lock with various scenarios"""
        # Success on first try
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        assert acquire_redis_lock(mock_redis, "test_key", "lock_id_123") is True
        mock_redis.set.assert_called_with("test_key", "lock_id_123", ex=5, nx=True)

        # Success after retries
        mock_redis.set.side_effect = [False, False, True]
        with mock.patch("time.sleep"):
            assert acquire_redis_lock(mock_redis, "test_key", "lock_id_123") is True

        # Failure after max retries
        mock_redis.set.side_effect = None  # Reset side_effect
        mock_redis.set.return_value = False
        with mock.patch("bkflow.utils.redis_lock.MAX_RETRY", 5), mock.patch("time.sleep"):
            assert acquire_redis_lock(mock_redis, "test_key", "lock_id_123") is False


class TestReleaseRedisLock:
    """Test release_redis_lock function"""

    def test_release_lock_success_string_value(self):
        """Test releasing lock with string lock value"""
        mock_redis = mock.Mock()
        mock_redis.get.return_value = "lock_id_123"

        release_redis_lock(mock_redis, "test_key", "lock_id_123")

        mock_redis.get.assert_called_once_with("test_key")
        mock_redis.delete.assert_called_once_with("test_key")

    def test_release_lock_success_bytes_value(self):
        """Test releasing lock with bytes lock value (different redis modes)"""
        mock_redis = mock.Mock()
        mock_redis.get.return_value = b"lock_id_123"

        release_redis_lock(mock_redis, "test_key", "lock_id_123")

        mock_redis.get.assert_called_once_with("test_key")
        mock_redis.delete.assert_called_once_with("test_key")

    def test_release_lock_mismatch_id(self):
        """Test not releasing lock when lock_id doesn't match"""
        mock_redis = mock.Mock()
        mock_redis.get.return_value = "different_lock_id"

        release_redis_lock(mock_redis, "test_key", "lock_id_123")

        mock_redis.get.assert_called_once_with("test_key")
        # Should not delete when IDs don't match
        mock_redis.delete.assert_not_called()

    def test_release_lock_none_value(self):
        """Test releasing when lock doesn't exist (None value)"""
        mock_redis = mock.Mock()
        mock_redis.get.return_value = None

        release_redis_lock(mock_redis, "test_key", "lock_id_123")

        mock_redis.get.assert_called_once_with("test_key")
        # Should not delete when lock doesn't exist
        mock_redis.delete.assert_not_called()

    def test_release_lock_bytes_mismatch(self):
        """Test not releasing lock when bytes lock_id doesn't match"""
        mock_redis = mock.Mock()
        mock_redis.get.return_value = b"different_lock_id"

        release_redis_lock(mock_redis, "test_key", "lock_id_123")

        mock_redis.delete.assert_not_called()


class TestRedisLockContextManager:
    """Test redis_lock context manager"""

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_success(self, mock_uuid):
        """Test successful lock acquisition and release"""
        mock_uuid.return_value = "test-uuid-123"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test-uuid-123"

        with redis_lock(mock_redis, "my_key") as (acquired, err):
            assert acquired is True
            assert err is None

        # Verify lock was acquired
        mock_redis.set.assert_called_once_with("lock_my_key", "test-uuid-123", ex=5, nx=True)
        # Verify lock was released
        mock_redis.delete.assert_called_once_with("lock_my_key")

    @mock.patch("bkflow.utils.redis_lock.MAX_RETRY", 5)
    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_failure(self, mock_uuid):
        """Test failed lock acquisition"""
        mock_uuid.return_value = "test-uuid-456"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = False

        with mock.patch("time.sleep"):
            with redis_lock(mock_redis, "my_key") as (acquired, err):
                assert acquired is False
                assert err is not None
                assert isinstance(err, LockError)
                assert "Unable to acquire redis lock" in str(err)
                assert "lock_my_key" in str(err)
                assert "test-uuid-456" in str(err)

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_exception_still_releases(self, mock_uuid):
        """Test that lock is released even if exception occurs in context"""
        mock_uuid.return_value = "test-uuid-789"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test-uuid-789"

        with pytest.raises(ValueError):
            with redis_lock(mock_redis, "my_key") as (acquired, err):
                assert acquired is True
                raise ValueError("Something went wrong")

        # Verify lock was still released despite exception
        mock_redis.delete.assert_called_once_with("lock_my_key")

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_with_custom_key(self, mock_uuid):
        """Test lock with different key formats"""
        mock_uuid.return_value = "test-uuid"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test-uuid"

        with redis_lock(mock_redis, "task:123:processing") as (acquired, err):
            assert acquired is True

        mock_redis.set.assert_called_with("lock_task:123:processing", "test-uuid", ex=5, nx=True)

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_edge_cases(self, mock_uuid):
        """Test redis_lock context manager edge cases"""
        mock_uuid.return_value = "test-uuid"
        mock_redis = mock.Mock()

        # Retries then succeeds
        mock_redis.set.side_effect = [False, False, True]
        mock_redis.get.return_value = "test-uuid"
        with mock.patch("time.sleep"):
            with redis_lock(mock_redis, "my_key") as (acquired, err):
                assert acquired is True

        # Bytes in release
        mock_redis.set.side_effect = None  # Reset side_effect
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test-uuid"
        with redis_lock(mock_redis, "my_key") as (acquired, err):
            assert acquired is True

        # Lock stolen
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "different-uuid"
        mock_redis.delete.reset_mock()  # Reset delete call history
        with redis_lock(mock_redis, "my_key") as (acquired, err):
            assert acquired is True
        mock_redis.delete.assert_not_called()
