"""Tests for event dedup fingerprint logic."""
import pytest
from datetime import date

from atlas.models.event import EventFingerprint, compute_time_bucket


class TestEventFingerprint:
    """Test fingerprint generation determinism and correctness."""

    def test_same_input_same_fingerprint(self):
        fp1 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W19")
        fp2 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W19")
        assert fp1.fingerprint == fp2.fingerprint

    def test_different_entity_different_fingerprint(self):
        fp1 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W19")
        fp2 = EventFingerprint(entity="铜", event_type="price_change", direction="up", time_bucket="2026-W19")
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_direction_different_fingerprint(self):
        fp1 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W19")
        fp2 = EventFingerprint(entity="锂", event_type="price_change", direction="down", time_bucket="2026-W19")
        assert fp1.fingerprint != fp2.fingerprint

    def test_different_time_bucket_different_fingerprint(self):
        fp1 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W19")
        fp2 = EventFingerprint(entity="锂", event_type="price_change", direction="up", time_bucket="2026-W20")
        assert fp1.fingerprint != fp2.fingerprint

    def test_fingerprint_length(self):
        fp = EventFingerprint(entity="test", event_type="price_change", direction="up", time_bucket="2026-W19")
        assert len(fp.fingerprint) == 32

    def test_fingerprint_is_hex(self):
        fp = EventFingerprint(entity="test", event_type="price_change", direction="up", time_bucket="2026-W19")
        int(fp.fingerprint, 16)  # Should not raise


class TestComputeTimeBucket:
    """Test time bucket computation per event type."""

    def test_daily_bucket(self):
        result = compute_time_bucket("accident_disaster", date(2026, 5, 8))
        assert result == "2026-05-08"

    def test_weekly_bucket(self):
        result = compute_time_bucket("price_change", date(2026, 5, 8))
        assert result.startswith("2026-W")

    def test_monthly_bucket(self):
        result = compute_time_bucket("policy_new", date(2026, 5, 8))
        assert result == "2026-05"

    def test_quarterly_bucket(self):
        result = compute_time_bucket("earnings_beat", date(2026, 5, 8))
        assert result == "2026-Q2"

    def test_quarterly_q1(self):
        result = compute_time_bucket("earnings_miss", date(2026, 2, 15))
        assert result == "2026-Q1"

    def test_quarterly_q3(self):
        result = compute_time_bucket("earnings_beat", date(2026, 8, 1))
        assert result == "2026-Q3"

    def test_unknown_type_defaults_to_week(self):
        result = compute_time_bucket("some_unknown_type", date(2026, 5, 8))
        assert result.startswith("2026-W")

    def test_other_type_uses_week(self):
        result = compute_time_bucket("other", date(2026, 5, 8))
        assert result.startswith("2026-W")

    def test_none_date_uses_today(self):
        result = compute_time_bucket("price_change")
        assert result  # Just verify it returns something

