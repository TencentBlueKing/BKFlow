"""Test date utils"""
import datetime
import decimal
import uuid

import pytest
from django.utils import timezone
from django.utils.functional import lazy

from bkflow.utils.dates import format_datetime, json_encoder_default


class TestDateUtils:
    """Test date utility functions"""

    def test_format_datetime(self):
        """Test formatting datetime"""
        # Naive datetime
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45)
        result = format_datetime(dt)
        assert "2024-01-01 12:30:45" in result

        # Aware datetime
        dt = timezone.make_aware(datetime.datetime(2024, 1, 1, 12, 30, 45))
        result = format_datetime(dt)
        assert "2024-01-01" in result

        # With timezone
        tz = timezone.get_current_timezone()
        result = format_datetime(dt, tz)
        assert "2024-01-01" in result

    def test_json_encoder_promise(self):
        """Test encoding lazy translation strings"""
        lazy_func = lazy(lambda: "test", str)
        result = json_encoder_default(None, lazy_func())
        assert result == "test"

    def test_json_encoder_datetime_types(self):
        """Test encoding various datetime types"""
        # Datetime
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45)
        result = json_encoder_default(None, dt)
        assert "2024-01-01" in result

        # Datetime with microseconds
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45, 123456)
        result = json_encoder_default(None, dt)
        assert "2024-01-01" in result

        # UTC datetime
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45, tzinfo=datetime.timezone.utc)
        result = json_encoder_default(None, dt)
        assert result.endswith("Z")

        # Date
        d = datetime.date(2024, 1, 1)
        assert json_encoder_default(None, d) == "2024-01-01"

        # Time
        t = datetime.time(12, 30, 45)
        result = json_encoder_default(None, t)
        assert "12:30:45" in result

        # Time with microseconds
        t = datetime.time(12, 30, 45, 123456)
        result = json_encoder_default(None, t)
        assert "12:30:45" in result

    def test_json_encoder_aware_time_raises(self):
        """Test that aware time raises ValueError"""
        t = datetime.time(12, 30, 45, tzinfo=datetime.timezone.utc)
        with pytest.raises(ValueError, match="timezone-aware times"):
            json_encoder_default(None, t)

    def test_json_encoder_other_types(self):
        """Test encoding other types"""
        # Decimal
        assert json_encoder_default(None, decimal.Decimal("123.45")) == "123.45"

        # UUID
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert json_encoder_default(None, u) == "12345678-1234-5678-1234-567812345678"

        # Bytes
        assert json_encoder_default(None, b"hello world") == "hello world"

    def test_json_encoder_unknown_type(self):
        """Test encoding unknown type falls back to str"""
        from django.core.serializers.json import DjangoJSONEncoder

        class CustomObj:
            def __str__(self):
                return "custom_object"

        encoder = DjangoJSONEncoder()
        obj = CustomObj()
        result = json_encoder_default(encoder, obj)
        assert result == "custom_object"
