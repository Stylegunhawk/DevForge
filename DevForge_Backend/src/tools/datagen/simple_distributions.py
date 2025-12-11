"""Simple distribution functions for realistic data generation.

Provides practical distributions for numeric and categorical data,
plus temporal patterns for timestamp generation.
"""

import random
from datetime import datetime, timedelta
from typing import Any, Optional
import numpy as np


# =============================================================================
# Numeric Distributions
# =============================================================================

def normal(mean: float, std: float, n: int, min_val: Optional[float] = None, max_val: Optional[float] = None) -> list[float]:
    """Generate values from normal (Gaussian) distribution.
    
    Args:
        mean: Mean of distribution
        std: Standard deviation
        n: Number of values to generate
        min_val: Optional minimum value (clamp)
        max_val: Optional maximum value (clamp)
        
    Returns:
        List of n floats from normal distribution
        
    Example:
        >>> values = normal(100, 15, 1000)  # IQ scores
        >>> values = normal(0, 1, 100, min_val=-3, max_val=3)  # Standard normal, clamped
    """
    values = np.random.normal(mean, std, n)
    
    # Clamp if bounds specified
    if min_val is not None:
        values = np.maximum(values, min_val)
    if max_val is not None:
        values = np.minimum(values, max_val)
    
    return values.tolist()


def lognormal(mean: float, std: float, n: int, min_val: float = 0.01) -> list[float]:
    """Generate values from lognormal distribution.
    
    Good for: prices, salaries, file sizes, wait times.
    Always positive with right-skewed tail.
    
    Args:
        mean: Mean of underlying normal distribution (not the lognormal mean!)
        std: Standard deviation of underlying normal
        n: Number of values to generate
        min_val: Minimum value (default 0.01 to avoid zeros)
        
    Returns:
        List of n positive floats
        
    Example:
        >>> prices = lognormal(3, 1, 1000)  # Product prices
        >>> salaries = lognormal(10.5, 0.5, 500)  # Employee salaries
    """
    values = np.random.lognormal(mean, std, n)
    values = np.maximum(values, min_val)
    return values.tolist()


def pareto(alpha: float, n: int, scale: float = 1.0) -> list[float]:
    """Generate values from Pareto (power law) distribution.
    
    Good for: wealth distribution, city sizes, 80/20 phenomena.
    
    Args:
        alpha: Shape parameter (smaller = more extreme inequality)
        n: Number of values to generate
        scale: Scale parameter (minimum value)
        
    Returns:
        List of n floats following Pareto distribution
        
    Example:
        >>> wealth = pareto(1.16, 1000, scale=1000)  # 80/20 rule
        >>> engagement = pareto(2.0, 500)  # User engagement
    """
    values = (np.random.pareto(alpha, n) + 1) * scale
    return values.tolist()


def uniform(min_val: float, max_val: float, n: int) -> list[float]:
    """Generate values from uniform distribution.
    
    Args:
        min_val: Minimum value (inclusive)
        max_val: Maximum value (exclusive)
        n: Number of values to generate
        
    Returns:
        List of n floats uniformly distributed
    """
    values = np.random.uniform(min_val, max_val, n)
    return values.tolist()


def categorical(choices: list[Any], probs: Optional[list[float]] = None, n: int = 1) -> list[Any]:
    """Generate categorical values with optional probabilities.
    
    Args:
        choices: List of possible values
        probs: Optional probability for each choice (must sum to 1.0)
        n: Number of values to generate
        
    Returns:
        List of n values sampled from choices
        
    Example:
        >>> tiers = categorical(["free", "pro", "enterprise"], [0.7, 0.25, 0.05], 1000)
        >>> colors = categorical(["red", "blue", "green"], n=100)  # Equal probability
    """
    if probs is not None:
        if len(probs) != len(choices):
            raise ValueError(f"probs length ({len(probs)}) must match choices length ({len(choices)})")
        if not abs(sum(probs) - 1.0) < 0.01:  # Allow small floating point error
            raise ValueError(f"probs must sum to 1.0, got {sum(probs)}")
    
    return list(np.random.choice(choices, size=n, p=probs))


# =============================================================================
# Temporal Patterns
# =============================================================================

def random_timestamps(
    start: datetime, 
    end: datetime, 
    n: int,
    sorted: bool = False
) -> list[datetime]:
    """Generate random timestamps between start and end.
    
    Args:
        start: Start datetime
        end: End datetime
        n: Number of timestamps to generate
        sorted: If True, return sorted timestamps
        
    Returns:
        List of n random timestamps
        
    Example:
        >>> from datetime import datetime
        >>> start = datetime(2024, 1, 1)
        >>> end = datetime(2024, 12, 31)
        >>> timestamps = random_timestamps(start, end, 1000)
    """
    time_delta = (end - start).total_seconds()
    random_seconds = np.random.uniform(0, time_delta, n)
    timestamps = [start + timedelta(seconds=float(s)) for s in random_seconds]
    
    if sorted:
        timestamps.sort()
    
    return timestamps


def business_hours_timestamps(
    start: datetime,
    end: datetime,
    n: int,
    business_start_hour: int = 9,
    business_end_hour: int = 17,
    business_weight: float = 0.7,
    sorted: bool = False
) -> list[datetime]:
    """Generate timestamps biased toward business hours.
    
    Args:
        start: Start datetime
        end: End datetime
        n: Number of timestamps to generate
        business_start_hour: Start of business hours (default 9am)
        business_end_hour: End of business hours (default 5pm)
        business_weight: Fraction of timestamps in business hours (default 0.7)
        sorted: If True, return sorted timestamps
        
    Returns:
        List of n timestamps biased toward business hours
        
    Example:
        >>> timestamps = business_hours_timestamps(
        ...     datetime(2024, 1, 1), 
        ...     datetime(2024, 12, 31), 
        ...     1000
        ... )  # 70% between 9am-5pm
    """
    n_business = int(n * business_weight)
    n_other = n - n_business
    
    timestamps = []
    
    # Generate business hours timestamps
    current = start
    while current <= end and len([t for t in timestamps if business_start_hour <= t.hour < business_end_hour]) < n_business:
        # Random day between start and end
        time_delta = (end - start).total_seconds()
        random_seconds = np.random.uniform(0, time_delta)
        candidate = start + timedelta(seconds=float(random_seconds))
        
        # Adjust to business hours
        candidate = candidate.replace(
            hour=np.random.randint(business_start_hour, business_end_hour),
            minute=np.random.randint(0, 60),
            second=np.random.randint(0, 60)
        )
        
        if start <= candidate <= end:
            timestamps.append(candidate)
    
    # Generate non-business hours timestamps
    while len(timestamps) < n:
        time_delta = (end - start).total_seconds()
        random_seconds = np.random.uniform(0, time_delta)
        candidate = start + timedelta(seconds=float(random_seconds))
        
        # Accept if outside business hours
        if candidate.hour < business_start_hour or candidate.hour >= business_end_hour:
            timestamps.append(candidate)
    
    # Trim to exact count (in case we generated extra)
    timestamps = timestamps[:n]
    
    if sorted:
        timestamps.sort()
    
    return timestamps


def seasonal_timestamps(
    start: datetime,
    end: datetime,
    n: int,
    peak_month: int = 12,  # December
    peak_weight: float = 0.4,
    sorted: bool = False
) -> list[datetime]:
    """Generate timestamps with seasonal bias.
    
    Simple seasonal pattern: higher weight toward a specific month.
    
    Args:
        start: Start datetime
        end: End datetime
        n: Number of timestamps to generate
        peak_month: Month with highest activity (1-12)
        peak_weight: Fraction of timestamps in peak month (default 0.4)
        sorted: If True, return sorted timestamps
        
    Returns:
        List of n timestamps with seasonal bias
        
    Example:
        >>> # Holiday shopping peak in December
        >>> timestamps = seasonal_timestamps(
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 12, 31),
        ...     1000,
        ...     peak_month=12,
        ...     peak_weight=0.4
        ... )
    """
    n_peak = int(n * peak_weight)
    n_other = n - n_peak
    
    timestamps = []
    
    # Generate peak month timestamps
    year = start.year
    peak_start = datetime(year, peak_month, 1)
    
    # Handle peak month that might span year boundary
    if peak_month == 12:
        peak_end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        peak_end = datetime(year, peak_month + 1, 1) - timedelta(seconds=1)
    
    # Ensure peak period is within overall range
    peak_start = max(peak_start, start)
    peak_end = min(peak_end, end)
    
    if peak_start < peak_end:
        peak_timestamps = random_timestamps(peak_start, peak_end, n_peak)
        timestamps.extend(peak_timestamps)
    
    # Generate other timestamps (outside peak month)
    while len(timestamps) < n:
        candidate = random_timestamps(start, end, 1)[0]
        if candidate.month != peak_month:
            timestamps.append(candidate)
    
    # Trim to exact count
    timestamps = timestamps[:n]
    
    if sorted:
        timestamps.sort()
    
    return timestamps


def weekday_timestamps(
    start: datetime,
    end: datetime,
    n: int,
    weekday_weight: float = 0.7,
    sorted: bool = False
) -> list[datetime]:
    """Generate timestamps biased toward weekdays (Mon-Fri).
    
    Args:
        start: Start datetime
        end: End datetime
        n: Number of timestamps to generate
        weekday_weight: Fraction on weekdays (default 0.7)
        sorted: If True, return sorted timestamps
        
    Returns:
        List of n timestamps biased toward weekdays
        
    Example:
        >>> timestamps = weekday_timestamps(
        ...     datetime(2024, 1, 1),
        ...     datetime(2024, 12, 31),
        ...     1000
        ... )  # 70% on Mon-Fri
    """
    n_weekday = int(n * weekday_weight)
    n_weekend = n - n_weekday
    
    timestamps = []
    
    # Generate weekday timestamps (0=Monday, 6=Sunday)
    while len([t for t in timestamps if t.weekday() < 5]) < n_weekday:
        candidate = random_timestamps(start, end, 1)[0]
        if candidate.weekday() < 5:  # Monday-Friday
            timestamps.append(candidate)
    
    # Generate weekend timestamps
    while len(timestamps) < n:
        candidate = random_timestamps(start, end, 1)[0]
        if candidate.weekday() >= 5:  # Saturday-Sunday
            timestamps.append(candidate)
    
    # Trim to exact count
    timestamps = timestamps[:n]
    
    if sorted:
        timestamps.sort()
    
    return timestamps
