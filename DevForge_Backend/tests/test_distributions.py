"""Tests for simple distribution functions.

Tests cover:
- Numeric distributions (normal, lognormal, pareto, categorical)
- Temporal patterns (random, business_hours, seasonal, weekday)
- Statistical properties and shape validation
- Edge cases and parameter validation
"""

import pytest
from datetime import datetime, timedelta
from src.tools.datagen.simple_distributions import (
    normal,
    lognormal,
    pareto,
    uniform,
    categorical,
    random_timestamps,
    business_hours_timestamps,
    seasonal_timestamps,
    weekday_timestamps,
)


class TestNumericDistributions:
    """Tests for numeric distribution functions."""

    def test_normal_basic(self):
        """Test basic normal distribution."""
        values = normal(mean=100, std=15, n=1000)
        
        assert len(values) == 1000
        assert all(isinstance(v, float) for v in values)
        
        # Check approximate mean and std (allow some variance)
        mean_val = sum(values) / len(values)
        assert 95 < mean_val < 105  # Within ~0.5 std of mean
        
        # Check variance
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = variance ** 0.5
        assert 12 < std_val < 18

    def test_normal_with_bounds(self):
        """Test normal distribution with min/max bounds."""
        values = normal(mean=100, std=15, n=1000, min_val=80, max_val=120)
        
        assert all(80 <= v <= 120 for v in values)

    def test_lognormal_basic(self):
        """Test lognormal distribution."""
        values = lognormal(mean=3, std=1, n=1000)
        
        assert len(values) == 1000
        assert all(v > 0 for v in values)  # Always positive
        assert all(isinstance(v, float) for v in values)

    def test_lognormal_min_value(self):
        """Test lognormal respects minimum value."""
        values = lognormal(mean=0, std=0.5, n=100, min_val=1.0)
        
        assert all(v >= 1.0 for v in values)

    def test_pareto_basic(self):
        """Test Pareto distribution."""
        values = pareto(alpha=1.16, n=1000, scale=1.0)
        
        assert len(values) == 1000
        assert all(v >= 1.0 for v in values)  # All above scale
        assert all(isinstance(v, float) for v in values)

    def test_pareto_scale(self):
        """Test Pareto with custom scale."""
        values = pareto(alpha=2.0, n=100, scale=100.0)
        
        assert all(v >= 100.0 for v in values)

    def test_uniform_basic(self):
        """Test uniform distribution."""
        values = uniform(min_val=0, max_val=100, n=1000)
        
        assert len(values) == 1000
        assert all(0 <= v < 100 for v in values)
        
        # Check approximate uniform distribution
        mean_val = sum(values) / len(values)
        assert 45 < mean_val < 55  # Should be around 50

    def test_categorical_equal_probability(self):
        """Test categorical with equal probabilities."""
        choices = ["red", "blue", "green"]
        values = categorical(choices, n=300)
        
        assert len(values) == 300
        assert all(v in choices for v in values)
        
        # Check roughly equal distribution
        counts = {choice: values.count(choice) for choice in choices}
        for count in counts.values():
            assert 80 < count < 120  # Roughly 100 each with some variance

    def test_categorical_weighted(self):
        """Test categorical with weighted probabilities."""
        choices = ["common", "uncommon", "rare"]
        probs = [0.7, 0.25, 0.05]
        values = categorical(choices, probs=probs, n=1000)
        
        assert len(values) == 1000
        
        # Check distribution matches weights roughly
        counts = {choice: values.count(choice) for choice in choices}
        assert 650 < counts["common"] < 750  # ~70%
        assert 200 < counts["uncommon"] < 300  # ~25%
        assert 20 < counts["rare"] < 80  # ~5%

    def test_categorical_invalid_probs_length(self):
        """Test categorical raises error for mismatched probs length."""
        with pytest.raises(ValueError, match="probs length"):
            categorical(["a", "b"], probs=[0.5, 0.3, 0.2], n=10)

    def test_categorical_invalid_probs_sum(self):
        """Test categorical raises error for probs not summing to 1."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            categorical(["a", "b"], probs=[0.5, 0.6], n=10)


class TestTemporalPatterns:
    """Tests for temporal pattern functions."""

    def test_random_timestamps_basic(self):
        """Test random timestamp generation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        timestamps = random_timestamps(start, end, n=100)
        
        assert len(timestamps) == 100
        assert all(isinstance(t, datetime) for t in timestamps)
        assert all(start <= t <= end for t in timestamps)

    def test_random_timestamps_sorted(self):
        """Test sorted random timestamps."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        timestamps = random_timestamps(start, end, n=50, sorted=True)
        
        # Check sorted
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1]

    def test_business_hours_basic(self):
        """Test business hours timestamp generation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        timestamps = business_hours_timestamps(start, end, n=100, business_weight=0.7)
        
        assert len(timestamps) == 100
        
        # Count timestamps in business hours (9am-5pm)
        business_count = sum(1 for t in timestamps if 9 <= t.hour < 17)
        
        # Should be roughly 70% (allow some variance)
        assert 60 < business_count < 80

    def test_business_hours_custom_hours(self):
        """Test business hours with custom hours."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        timestamps = business_hours_timestamps(
            start, end, n=100,
            business_start_hour=10,
            business_end_hour=16,
            business_weight=0.8
        )
        
        business_count = sum(1 for t in timestamps if 10 <= t.hour < 16)
        assert business_count >= 70  # At least 70 out of 100

    def test_seasonal_basic(self):
        """Test seasonal timestamp generation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        timestamps = seasonal_timestamps(
            start, end, n=100,
            peak_month=12,  # December
            peak_weight=0.4
        )
        
        assert len(timestamps) == 100
        
        # Count December timestamps
        december_count = sum(1 for t in timestamps if t.month == 12)
        
        # Should be roughly 40% (allow variance)
        assert 30 < december_count < 50

    def test_seasonal_different_peak(self):
        """Test seasonal with different peak month."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        timestamps = seasonal_timestamps(
            start, end, n=200,
            peak_month=7,  # July
            peak_weight=0.3
        )
        
        july_count = sum(1 for t in timestamps if t.month == 7)
        assert 40 < july_count < 80  # ~60 expected

    def test_weekday_basic(self):
        """Test weekday-biased timestamp generation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        timestamps = weekday_timestamps(start, end, n=100, weekday_weight=0.7)
        
        assert len(timestamps) == 100
        
        # Count weekday timestamps (Monday=0, Sunday=6)
        weekday_count = sum(1 for t in timestamps if t.weekday() < 5)
        
        # Should be roughly 70%
        assert 60 < weekday_count < 80

    def test_weekday_high_weight(self):
        """Test weekday with high weekday weight."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        timestamps = weekday_timestamps(start, end, n=100, weekday_weight=0.9)
        
        weekday_count = sum(1 for t in timestamps if t.weekday() < 5)
        assert weekday_count >= 85


class TestEdgeCases:
    """Tests for edge cases."""

    def test_small_sample_size(self):
        """Test distributions with small n."""
        values = normal(100, 15, n=1)
        assert len(values) == 1
        
        timestamps = random_timestamps(datetime(2024, 1, 1), datetime(2024, 1, 2), n=1)
        assert len(timestamps) == 1

    def test_large_sample_size(self):
        """Test distributions with large n."""
        values = normal(100, 15, n=10000)
        assert len(values) == 10000
        
        # Mean should be very close to 100 with large sample
        mean_val = sum(values) / len(values)
        assert 98 < mean_val < 102

    def test_single_day_range(self):
        """Test temporal patterns with single day range."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 1, 23, 59, 59)
        timestamps = random_timestamps(start, end, n=100)
        
        assert all(t.date() == start.date() for t in timestamps)

    def test_categorical_single_choice(self):
        """Test categorical with only one choice."""
        values = categorical(["only_one"], n=100)
        assert all(v == "only_one" for v in values)

    def test_normal_zero_std(self):
        """Test normal with zero standard deviation."""
        values = normal(100, 0, n=10)
        # All values should be exactly the mean
        assert all(abs(v - 100) < 0.01 for v in values)


class TestStatisticalProperties:
    """Tests for statistical properties of distributions."""

    def test_lognormal_always_positive(self):
        """Test lognormal never produces negative values."""
        values = lognormal(0, 2, n=1000)
        assert all(v > 0 for v in values)

    def test_pareto_power_law(self):
        """Test Pareto follows power law (most values low, few very high)."""
        values = pareto(1.16, n=1000, scale=1.0)
        
        # Count values in different ranges
        low = sum(1 for v in values if v < 5)
        high = sum(1 for v in values if v > 20)
        
        # Should have many low values, few high values
        assert low > high * 2

    def test_uniform_spread(self):
        """Test uniform distribution spreads evenly."""
        values = uniform(0, 100, n=10000)
        
        # Divide into 10 bins
        bins = [0] * 10
        for v in values:
            bin_idx = min(int(v / 10), 9)
            bins[bin_idx] += 1
        
        # Each bin should have roughly 1000 values
        for count in bins:
            assert 900 < count < 1100

    def test_timestamp_coverage(self):
        """Test timestamps cover the full date range."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        timestamps = random_timestamps(start, end, n=1000)
        
        # Check we have timestamps in multiple months
        months = {t.month for t in timestamps}
        assert len(months) >= 10  # At least 10 different months
