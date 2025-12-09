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

    def test_acquire_lock_success_first_try(self):
        """Test acquiring lock on first try"""
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True

        result = acquire_redis_lock(mock_redis, "test_key", "lock_id_123")

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", "lock_id_123", ex=5, nx=True)

    def test_acquire_lock_success_after_retries(self):
        """Test acquiring lock after a few retries"""
        mock_redis = mock.Mock()
        # Fail first 2 times, succeed on 3rd
        mock_redis.set.side_effect = [False, False, True]

        with mock.patch("time.sleep"):  # Mock sleep to speed up test
            result = acquire_redis_lock(mock_redis, "test_key", "lock_id_123")

        assert result is True
        assert mock_redis.set.call_count == 3

    @mock.patch("bkflow.utils.redis_lock.MAX_RETRY", 5)
    def test_acquire_lock_failure_max_retries(self):
        """Test lock acquisition failure after max retries"""
        mock_redis = mock.Mock()
        mock_redis.set.return_value = False

        with mock.patch("time.sleep"):  # Mock sleep to speed up test
            result = acquire_redis_lock(mock_redis, "test_key", "lock_id_123")

        assert result is False
        # Should try MAX_RETRY - 1 times (since cnt starts at 1 and condition is cnt < MAX_RETRY)
        assert mock_redis.set.call_count == 4

    @mock.patch("bkflow.utils.redis_lock.MAX_RETRY", 10)
    def test_acquire_lock_with_sleep_timing(self):
        """Test that sleep is called with correct interval"""
        mock_redis = mock.Mock()
        mock_redis.set.side_effect = [False, False, True]

        with mock.patch("time.sleep") as mock_sleep:
            result = acquire_redis_lock(mock_redis, "test_key", "lock_id_123")

        assert result is True
        # Sleep should be called twice (after first and second failed attempts)
        assert mock_sleep.call_count == 2
        # Verify sleep duration
        mock_sleep.assert_called_with(0.01)


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
    def test_redis_lock_retries_then_succeeds(self, mock_uuid):
        """Test lock acquisition after retries within context manager"""
        mock_uuid.return_value = "test-uuid"
        mock_redis = mock.Mock()
        # Fail twice, then succeed
        mock_redis.set.side_effect = [False, False, True]
        mock_redis.get.return_value = "test-uuid"

        with mock.patch("time.sleep"):
            with redis_lock(mock_redis, "my_key") as (acquired, err):
                assert acquired is True
                assert err is None

        assert mock_redis.set.call_count == 3
        mock_redis.delete.assert_called_once()

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_bytes_in_release(self, mock_uuid):
        """Test context manager with bytes value from redis"""
        mock_uuid.return_value = "test-uuid"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test-uuid"  # Redis returns bytes

        with redis_lock(mock_redis, "my_key") as (acquired, err):
            assert acquired is True

        # Should still release correctly
        mock_redis.delete.assert_called_once_with("lock_my_key")

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_no_delete_when_lock_stolen(self, mock_uuid):
        """Test that lock is not deleted if it was stolen/changed"""
        mock_uuid.return_value = "test-uuid"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        # Lock value changed (stolen by another process)
        mock_redis.get.return_value = "different-uuid"

        with redis_lock(mock_redis, "my_key") as (acquired, err):
            assert acquired is True

        # Should not delete when lock value doesn't match
        mock_redis.delete.assert_not_called()

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_redis_lock_multiple_sequential_locks(self, mock_uuid):
        """Test acquiring multiple locks sequentially"""
        mock_uuid.side_effect = ["uuid-1", "uuid-2"]
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True

        # First lock
        mock_redis.get.return_value = "uuid-1"
        with redis_lock(mock_redis, "key1") as (acquired, err):
            assert acquired is True

        # Second lock
        mock_redis.get.return_value = "uuid-2"
        with redis_lock(mock_redis, "key2") as (acquired, err):
            assert acquired is True

        assert mock_redis.set.call_count == 2
        assert mock_redis.delete.call_count == 2


class TestRedisLockIntegration:
    """Integration-style tests for redis lock"""

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_lock_prevents_concurrent_access(self, mock_uuid):
        """Test that lock properly prevents concurrent access"""
        mock_uuid.side_effect = ["uuid-first", "uuid-second"]
        mock_redis = mock.Mock()

        # First lock succeeds
        call_count = [0]

        def set_side_effect(*args, **kwargs):
            call_count[0] += 1
            # First call succeeds, second fails (lock held)
            return call_count[0] == 1

        mock_redis.set.side_effect = set_side_effect
        mock_redis.get.return_value = "uuid-first"

        # First process acquires lock
        with redis_lock(mock_redis, "shared_resource") as (acquired1, err1):
            assert acquired1 is True

            # Second process tries to acquire (should fail after retries)
            with mock.patch("time.sleep"):
                with mock.patch("bkflow.utils.redis_lock.MAX_RETRY", 3):
                    with redis_lock(mock_redis, "shared_resource") as (acquired2, err2):
                        assert acquired2 is False
                        assert err2 is not None

    @mock.patch("bkflow.utils.redis_lock.uuid4")
    def test_lock_usage_pattern(self, mock_uuid):
        """Test typical usage pattern"""
        mock_uuid.return_value = "operation-uuid"
        mock_redis = mock.Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "operation-uuid"

        operation_executed = False

        with redis_lock(mock_redis, "critical_section") as (acquired, err):
            if acquired:
                # Critical section
                operation_executed = True
            else:
                # Handle lock acquisition failure
                pytest.fail(f"Lock acquisition failed: {err}")

        assert operation_executed is True
        mock_redis.delete.assert_called_once()
