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

    def test_format_naive_datetime(self):
        """Test formatting naive datetime"""
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45)
        result = format_datetime(dt)
        assert "2024-01-01 12:30:45" in result

    def test_format_aware_datetime(self):
        """Test formatting timezone-aware datetime"""
        dt = timezone.make_aware(datetime.datetime(2024, 1, 1, 12, 30, 45))
        result = format_datetime(dt)
        assert "2024-01-01" in result
        assert ":" in result

    def test_format_datetime_with_tz(self):
        """Test formatting datetime with specific timezone"""
        dt = timezone.make_aware(datetime.datetime(2024, 1, 1, 12, 30, 45))
        tz = timezone.get_current_timezone()
        result = format_datetime(dt, tz)
        assert "2024-01-01" in result

    def test_json_encoder_promise(self):
        """Test encoding lazy translation strings"""
        lazy_func = lazy(lambda: "test", str)
        result = json_encoder_default(None, lazy_func())
        assert result == "test"

    def test_json_encoder_datetime(self):
        """Test encoding datetime"""
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45)
        result = json_encoder_default(None, dt)
        assert "2024-01-01" in result
        assert "12:30:45" in result

    def test_json_encoder_datetime_with_microseconds(self):
        """Test encoding datetime with microseconds"""
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45, 123456)
        result = json_encoder_default(None, dt)
        assert "2024-01-01" in result

    def test_json_encoder_datetime_utc(self):
        """Test encoding UTC datetime"""
        dt = datetime.datetime(2024, 1, 1, 12, 30, 45, tzinfo=datetime.timezone.utc)
        result = json_encoder_default(None, dt)
        assert result.endswith("Z")

    def test_json_encoder_date(self):
        """Test encoding date"""
        d = datetime.date(2024, 1, 1)
        result = json_encoder_default(None, d)
        assert result == "2024-01-01"

    def test_json_encoder_time(self):
        """Test encoding time"""
        t = datetime.time(12, 30, 45)
        result = json_encoder_default(None, t)
        assert "12:30:45" in result

    def test_json_encoder_time_with_microseconds(self):
        """Test encoding time with microseconds"""
        t = datetime.time(12, 30, 45, 123456)
        result = json_encoder_default(None, t)
        assert "12:30:45" in result

    def test_json_encoder_aware_time_raises(self):
        """Test that aware time raises ValueError"""
        t = datetime.time(12, 30, 45, tzinfo=datetime.timezone.utc)
        with pytest.raises(ValueError, match="timezone-aware times"):
            json_encoder_default(None, t)

    def test_json_encoder_decimal(self):
        """Test encoding Decimal"""
        d = decimal.Decimal("123.45")
        result = json_encoder_default(None, d)
        assert result == "123.45"

    def test_json_encoder_uuid(self):
        """Test encoding UUID"""
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = json_encoder_default(None, u)
        assert result == "12345678-1234-5678-1234-567812345678"

    def test_json_encoder_bytes(self):
        """Test encoding bytes"""
        b = b"hello world"
        result = json_encoder_default(None, b)
        assert result == "hello world"

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
