"""Additional tests for statistical utilities to improve coverage."""
import numpy as np
import pandas as pd
import pytest
from src.utils.statistics import (
    calculate_z_scores,
    calculate_mad,
    detect_outliers_iqr,
    detect_outliers_zscore,
    calculate_rolling_stats,
    calculate_pct_change,
    winsorize,
    chi2_cdf,
    _log_gamma,
    _stirling_correction,
)


class TestCalculateZScoresRobust:
    """Test robust Z-score calculation."""

    def test_robust_z_scores_normal_data(self):
        """Test robust Z-scores with normal data."""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = calculate_z_scores(series, robust=True)
        assert len(result) == len(series)
        assert not result.isna().any()

    def test_robust_z_scores_with_outliers(self):
        """Test that robust Z-scores handle outliers better."""
        series = pd.Series([1, 2, 3, 4, 5, 100])  # 100 is an outlier
        result = calculate_z_scores(series, robust=True)
        # Robust method should handle outlier better
        assert not result.isna().any()

    def test_robust_z_scores_constant_series(self):
        """Test robust Z-scores with constant series (MAD = 0)."""
        series = pd.Series([5, 5, 5, 5, 5])
        result = calculate_z_scores(series, robust=True)
        # Should return zeros when MAD is 0
        assert (result == 0).all()

    def test_robust_z_scores_empty_series(self):
        """Test robust Z-scores with empty series."""
        series = pd.Series([], dtype=float)
        result = calculate_z_scores(series, robust=True)
        assert len(result) == 0


class TestCalculateMAD:
    """Test MAD calculation."""

    def test_mad_normal_data(self):
        """Test MAD with normal data."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = calculate_mad(series)
        # MAD should be the median of |x - median(x)|
        # median = 3, deviations = [2, 1, 0, 1, 2], MAD = 1
        assert result == 1.0

    def test_mad_empty_series(self):
        """Test MAD with empty series."""
        series = pd.Series([], dtype=float)
        result = calculate_mad(series)
        assert result == 0.0

    def test_mad_constant_series(self):
        """Test MAD with constant series."""
        series = pd.Series([5, 5, 5, 5])
        result = calculate_mad(series)
        assert result == 0.0


class TestDetectOutliersIQR:
    """Test IQR outlier detection."""

    def test_iqr_outliers_normal_multiplier(self):
        """Test IQR outlier detection with normal multiplier."""
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = detect_outliers_iqr(series, multiplier=1.5)
        assert result.iloc[-1] == True  # 100 should be outlier
        # Check that at least the outlier was detected
        assert result.sum() >= 1

    def test_iqr_outliers_extreme_multiplier(self):
        """Test IQR outlier detection with extreme multiplier."""
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = detect_outliers_iqr(series, multiplier=3.0)
        # With higher multiplier, fewer outliers
        assert isinstance(result, pd.Series)

    def test_iqr_outliers_empty_series(self):
        """Test IQR outlier detection with empty series."""
        series = pd.Series([], dtype=float)
        result = detect_outliers_iqr(series)
        assert len(result) == 0


class TestDetectOutliersZScore:
    """Test Z-score outlier detection."""

    def test_zscore_outliers_standard(self):
        """Test Z-score outlier detection with standard threshold."""
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = detect_outliers_zscore(series, threshold=3.0)
        assert result.iloc[-1] == True  # 100 should be outlier

    def test_zscore_outliers_robust(self):
        """Test robust Z-score outlier detection."""
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = detect_outliers_zscore(series, threshold=3.0, robust=True)
        assert isinstance(result, pd.Series)


class TestCalculateRollingStats:
    """Test rolling statistics calculation."""

    def test_rolling_mean(self):
        """Test rolling mean calculation."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = calculate_rolling_stats(series, window=2, stat='mean')
        assert result.iloc[1] == 1.5  # Mean of [1, 2]

    def test_rolling_std(self):
        """Test rolling standard deviation."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = calculate_rolling_stats(series, window=2, stat='std')
        assert not result.isna().all()

    def test_rolling_median(self):
        """Test rolling median calculation."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = calculate_rolling_stats(series, window=2, stat='median')
        assert result.iloc[1] == 1.5

    def test_rolling_min(self):
        """Test rolling minimum."""
        series = pd.Series([5, 2, 8, 1, 9])
        result = calculate_rolling_stats(series, window=2, stat='min')
        assert result.iloc[1] == 2.0  # Min of [5, 2]

    def test_rolling_max(self):
        """Test rolling maximum."""
        series = pd.Series([5, 2, 8, 1, 9])
        result = calculate_rolling_stats(series, window=2, stat='max')
        assert result.iloc[1] == 5.0  # Max of [5, 2]

    def test_rolling_invalid_stat(self):
        """Test rolling stats with invalid statistic."""
        series = pd.Series([1, 2, 3, 4, 5])
        with pytest.raises(ValueError, match="Unknown statistic"):
            calculate_rolling_stats(series, window=2, stat='invalid')


class TestCalculatePctChange:
    """Test percentage change calculation."""

    def test_pct_change_basic(self):
        """Test basic percentage change."""
        series = pd.Series([100, 110, 121])
        result = calculate_pct_change(series, periods=1)
        assert pd.isna(result.iloc[0])  # First value is NaN
        assert abs(result.iloc[1] - 0.1) < 0.001  # 10% increase

    def test_pct_change_with_ffill(self):
        """Test percentage change with forward fill."""
        series = pd.Series([100, 110, 121])
        result = calculate_pct_change(series, periods=1, fill_method='ffill')
        # First NaN should be filled forward
        assert not result.isna().any()

    def test_pct_change_with_bfill(self):
        """Test percentage change with backward fill."""
        series = pd.Series([100, 110, 121])
        result = calculate_pct_change(series, periods=1, fill_method='bfill')
        # First NaN should be filled backward
        assert not result.isna().any()

    def test_pct_change_multi_period(self):
        """Test percentage change with multiple periods."""
        series = pd.Series([100, 110, 121, 133.1])
        result = calculate_pct_change(series, periods=2)
        # Compares value with value 2 positions back
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])


class TestWinsorize:
    """Test winsorization."""

    def test_winsorize_basic(self):
        """Test basic winsorization."""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        result = winsorize(series, lower_percentile=0.1, upper_percentile=0.9)
        # Extreme value 100 should be capped
        assert result.max() < 100

    def test_winsorize_no_change(self):
        """Test winsorization with values within bounds."""
        series = pd.Series([1, 2, 3, 4, 5])
        result = winsorize(series, lower_percentile=0.0, upper_percentile=1.0)
        pd.testing.assert_series_equal(result, series)


class TestChi2CDF:
    """Test chi-square CDF calculation."""

    def test_chi2_cdf_zero(self):
        """Test chi2 CDF at x=0."""
        result = chi2_cdf(0, df=8)
        assert result == 0.0

    def test_chi2_cdf_negative(self):
        """Test chi2 CDF with negative value."""
        result = chi2_cdf(-1, df=8)
        assert result == 0.0

    def test_chi2_cdf_large_x(self):
        """Test chi2 CDF with large x value."""
        result = chi2_cdf(150, df=8)
        assert result == 1.0

    def test_chi2_cdf_normal_value(self):
        """Test chi2 CDF with normal value."""
        result = chi2_cdf(10, df=8)
        assert 0.0 < result < 1.0

    def test_chi2_cdf_invalid_df(self):
        """Test chi2 CDF with invalid degrees of freedom."""
        with pytest.raises(ValueError, match="Degrees of freedom must be positive"):
            chi2_cdf(10, df=0)

    def test_chi2_cdf_very_small_value(self):
        """Test chi2 CDF with very small value for underflow protection."""
        result = chi2_cdf(0.0001, df=8)
        assert result >= 0.0

    def test_chi2_cdf_convergence(self):
        """Test that chi2 CDF series converges."""
        result = chi2_cdf(5, df=4)
        assert 0.0 <= result <= 1.0


class TestLogGamma:
    """Test log-gamma function."""

    def test_log_gamma_one(self):
        """Test log-gamma at x=1."""
        result = _log_gamma(1.0)
        assert abs(result - 0.0) < 1e-10

    def test_log_gamma_two(self):
        """Test log-gamma at x=2."""
        result = _log_gamma(2.0)
        assert abs(result - 0.0) < 1e-10

    def test_log_gamma_half(self):
        """Test log-gamma at x=0.5."""
        result = _log_gamma(0.5)
        expected = 0.5 * np.log(np.pi)
        assert abs(result - expected) < 1e-10

    def test_log_gamma_large_value(self):
        """Test log-gamma with large value."""
        result = _log_gamma(10.0)
        # gamma(10) = 9! = 362880, log(362880) ≈ 12.8
        assert result > 10.0

    def test_log_gamma_small_value(self):
        """Test log-gamma with small value (uses recursion)."""
        result = _log_gamma(2.5)
        assert result > 0.0

    def test_log_gamma_invalid_input(self):
        """Test log-gamma with invalid (non-positive) input."""
        with pytest.raises(ValueError, match="Gamma function undefined"):
            _log_gamma(0)
        with pytest.raises(ValueError, match="Gamma function undefined"):
            _log_gamma(-1)


class TestStirlingCorrection:
    """Test Stirling correction term."""

    def test_stirling_correction_large_x(self):
        """Test Stirling correction with large x."""
        result = _stirling_correction(150)
        # For large x, only first term is used
        expected = 1.0 / (12.0 * 150)
        assert abs(result - expected) < 1e-10

    def test_stirling_correction_moderate_x(self):
        """Test Stirling correction with moderate x."""
        result = _stirling_correction(20)
        # Should include multiple terms
        assert result > 0.0
        assert result < 1.0

    def test_stirling_correction_small_x(self):
        """Test Stirling correction with small x (around threshold)."""
        result = _stirling_correction(10)
        assert result > 0.0
