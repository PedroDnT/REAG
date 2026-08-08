"""
Statistical utilities for anomaly detection and analysis.

Centralizes common statistical calculations used across analyzers.
"""
import math

import numpy as np
import pandas as pd


def calculate_z_scores(series: pd.Series,
                      robust: bool = False) -> pd.Series:
    """
    Calculate Z-scores for a series.

    Args:
        series: Numeric series
        robust: If True, use median and MAD instead of mean and std

    Returns:
        Series of Z-scores
    """
    if len(series) == 0:
        return pd.Series(dtype=float)

    if robust:
        median = series.median()
        mad = calculate_mad(series)
        if mad == 0:
            return pd.Series(0, index=series.index)
        return (series - median) / mad
    else:
        mean = series.mean()
        std = series.std()
        if std == 0:
            return pd.Series(np.nan, index=series.index, dtype=float)
        return (series - mean) / std


def calculate_mad(series: pd.Series) -> float:
    """
    Calculate Median Absolute Deviation (MAD).

    MAD is a robust measure of variability.

    Args:
        series: Numeric series

    Returns:
        MAD value
    """
    if len(series) == 0:
        return 0.0

    median = series.median()
    return (series - median).abs().median()


def detect_outliers_iqr(series: pd.Series,
                       multiplier: float = 1.5) -> pd.Series:
    """
    Detect outliers using Interquartile Range (IQR) method.

    Args:
        series: Numeric series
        multiplier: IQR multiplier (1.5 for outliers, 3.0 for extreme outliers)

    Returns:
        Boolean series indicating outliers
    """
    if len(series) == 0:
        return pd.Series(dtype=bool)

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr

    return (series < lower_bound) | (series > upper_bound)


def detect_outliers_zscore(series: pd.Series,
                          threshold: float = 3.0,
                          robust: bool = False) -> pd.Series:
    """
    Detect outliers using Z-score method.

    Args:
        series: Numeric series
        threshold: Z-score threshold (typically 2.5-3.0)
        robust: If True, use robust Z-scores (median/MAD)

    Returns:
        Boolean series indicating outliers
    """
    z_scores = calculate_z_scores(series, robust=robust)
    outliers = z_scores.abs() > threshold

    # Fallback for small samples where classic z-score can mask extremes.
    if not robust and not outliers.any():
        robust_z = calculate_z_scores(series, robust=True)
        outliers = outliers | (robust_z.abs() > threshold)

    return outliers.fillna(False)


def calculate_rolling_stats(series: pd.Series,
                           window: int,
                           stat: str = 'mean') -> pd.Series:
    """
    Calculate rolling statistics.

    Args:
        series: Numeric series
        window: Rolling window size
        stat: Statistic to calculate ('mean', 'std', 'median', 'min', 'max')

    Returns:
        Series with rolling statistics
    """
    if stat == 'mean':
        return series.rolling(window=window).mean()
    elif stat == 'std':
        return series.rolling(window=window).std()
    elif stat == 'median':
        return series.rolling(window=window).median()
    elif stat == 'min':
        return series.rolling(window=window).min()
    elif stat == 'max':
        return series.rolling(window=window).max()
    else:
        raise ValueError(f"Unknown statistic: {stat}")


def calculate_pct_change(series: pd.Series,
                        periods: int = 1,
                        fill_method: str | None = None) -> pd.Series:
    """
    Calculate percentage change with optional fill method.

    Args:
        series: Numeric series
        periods: Periods to shift for calculating change
        fill_method: Method to fill NaN values ('ffill', 'bfill', None)

    Returns:
        Series with percentage changes
    """
    pct = series.pct_change(periods=periods)

    if fill_method == 'ffill':
        pct = pct.ffill().bfill()
    elif fill_method == 'bfill':
        pct = pct.bfill().ffill()

    return pct


def winsorize(series: pd.Series,
             lower_percentile: float = 0.05,
             upper_percentile: float = 0.95) -> pd.Series:
    """
    Winsorize series by capping extreme values at percentiles.

    Args:
        series: Numeric series
        lower_percentile: Lower percentile to cap at
        upper_percentile: Upper percentile to cap at

    Returns:
        Winsorized series
    """
    lower_bound = series.quantile(lower_percentile)
    upper_bound = series.quantile(upper_percentile)

    return series.clip(lower=lower_bound, upper=upper_bound)


def chi2_cdf(x: float, df: int) -> float:
    """
    Calculate chi-square cumulative distribution function.

    Evaluates the regularized lower incomplete gamma P(df/2, x/2) by series
    expansion when x/2 < df/2 + 1, and via the complement of the continued
    fraction otherwise -- the regime where the series converges too slowly.
    Accurate to ~1e-12 for all degrees of freedom.

    Args:
        x: Chi-square statistic value
        df: Degrees of freedom

    Returns:
        Cumulative probability P(X <= x)
    """
    if df <= 0:
        raise ValueError("Degrees of freedom must be positive")

    if x <= 0:
        return 0.0

    a = df / 2.0
    x_half = x / 2.0

    if x_half < a + 1.0:
        result = _lower_gamma_series(a, x_half)
    else:
        result = 1.0 - _upper_gamma_continued_fraction(a, x_half)

    return max(0.0, min(1.0, float(result)))


def _lower_gamma_series(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) by series expansion.

    P(a, x) = e^-x * x^a / Gamma(a) * sum_{n=0..inf}(x^n / (a(a+1)...(a+n)))

    Converges quickly for x < a + 1.
    """
    log_prefactor = -x + a * math.log(x) - math.lgamma(a)
    if log_prefactor < -700:  # Underflow protection
        return 0.0

    term = 1.0 / a
    summation = term
    for n in range(1, 1000):
        term *= x / (a + n)
        summation += term
        if abs(term) < 1e-15 * abs(summation):
            break

    return math.exp(log_prefactor) * summation


def _upper_gamma_continued_fraction(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) by continued fraction.

    Modified Lentz algorithm. Converges quickly for x >= a + 1, the regime
    where the series expansion in _lower_gamma_series stalls.
    """
    log_prefactor = -x + a * math.log(x) - math.lgamma(a)
    if log_prefactor < -700:  # Underflow protection
        return 0.0

    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b if b != 0.0 else 1.0 / tiny
    h = d

    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break

    return math.exp(log_prefactor) * h
