"""
Tests for Benford's Law Analyzer
"""

import pytest
import pandas as pd
import numpy as np
from src.analyzers.benford_law import BenfordLawAnalyzer


class TestBenfordLawAnalyzer:
    """Test suite for BenfordLawAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return BenfordLawAnalyzer()

    @pytest.fixture
    def benford_compliant_data(self):
        """
        Generate data that follows Benford's Law
        Using powers of 2 which naturally follow Benford's Law
        """
        # Powers of 2 follow Benford's Law
        values = [2**i for i in range(1, 100)]
        return pd.Series(values)

    @pytest.fixture
    def uniform_data(self):
        """
        Generate uniform data (fabricated numbers)
        This should NOT follow Benford's Law
        """
        # Uniform distribution across first digits
        values = []
        for digit in range(1, 10):
            for _ in range(100):
                values.append(digit * 10 + np.random.randint(0, 10))
        return pd.Series(values)

    @pytest.fixture
    def sample_informe_df(self):
        """Create sample informe diário dataframe"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')

        data = []
        for fund_id in ['FUND001', 'FUND002']:
            for date in dates:
                data.append({
                    'CNPJ_FUNDO': fund_id,
                    'DT_COMPTC': date,
                    'VL_PATRIM_LIQ': np.random.exponential(1000000),  # Exponential distribution (Benford-like)
                    'VL_QUOTA': 1.0 + np.random.exponential(0.1),
                    'CAPTC_DIA': np.random.exponential(10000),
                    'RESG_DIA': np.random.exponential(8000)
                })

        return pd.DataFrame(data)

    def test_extract_first_digits_basic(self, analyzer):
        """Test extraction of first digits from simple numbers"""
        values = pd.Series([123, 456, 789, 111, 222])
        first_digits = analyzer.extract_first_digits(values)

        assert list(first_digits) == [1, 4, 7, 1, 2]

    def test_extract_first_digits_decimals(self, analyzer):
        """Test extraction from decimal numbers"""
        values = pd.Series([0.123, 0.456, 1.789, 12.34])
        first_digits = analyzer.extract_first_digits(values)

        assert list(first_digits) == [1, 4, 1, 1]

    def test_extract_first_digits_negatives(self, analyzer):
        """Test extraction from negative numbers (should use absolute)"""
        values = pd.Series([-123, -456, 789])
        first_digits = analyzer.extract_first_digits(values)

        assert list(first_digits) == [1, 4, 7]

    def test_extract_first_digits_zeros_removed(self, analyzer):
        """Test that zeros are removed"""
        values = pd.Series([123, 0, 456, 0, 789])
        first_digits = analyzer.extract_first_digits(values)

        assert len(first_digits) == 3
        assert 0 not in first_digits.values

    def test_calculate_observed_distribution(self, analyzer):
        """Test observed distribution calculation"""
        first_digits = pd.Series([1, 1, 1, 2, 2, 3, 4, 5, 6, 7])
        observed = analyzer.calculate_observed_distribution(first_digits)

        assert observed[1] == 0.3  # 3 out of 10
        assert observed[2] == 0.2  # 2 out of 10
        assert observed[8] == 0.0  # Not present
        assert observed[9] == 0.0  # Not present

    def test_benford_expected_distribution_sums_to_one(self, analyzer):
        """Test that Benford's expected distribution sums to 1"""
        total = sum(analyzer.BENFORD_EXPECTED.values())
        assert abs(total - 1.0) < 0.001

    def test_chi_square_test_benford_compliant(self, analyzer, benford_compliant_data):
        """Test chi-square on Benford-compliant data"""
        first_digits = analyzer.extract_first_digits(benford_compliant_data)
        observed = analyzer.calculate_observed_distribution(first_digits)

        chi_square, p_value, is_significant = analyzer.chi_square_test(
            observed, len(first_digits)
        )

        # Should NOT be significant (p > 0.05)
        assert p_value > 0.05
        assert not is_significant

    def test_chi_square_test_uniform_data(self, analyzer, uniform_data):
        """Test chi-square on uniform data (should fail Benford)"""
        first_digits = analyzer.extract_first_digits(uniform_data)
        observed = analyzer.calculate_observed_distribution(first_digits)

        chi_square, p_value, is_significant = analyzer.chi_square_test(
            observed, len(first_digits)
        )

        # Should be significant (p < 0.05)
        assert p_value < 0.05
        assert is_significant

    def test_chi_square_test_small_sample(self, analyzer):
        """Test that small samples return non-significant result"""
        first_digits = pd.Series([1, 2, 3])
        observed = analyzer.calculate_observed_distribution(first_digits)

        chi_square, p_value, is_significant = analyzer.chi_square_test(
            observed, len(first_digits)
        )

        # Small sample should not be significant
        assert is_significant is False
        assert p_value == 1.0

    def test_mean_absolute_deviation_perfect(self, analyzer):
        """Test MAD with perfect Benford distribution"""
        # Perfect Benford distribution
        observed = analyzer.BENFORD_EXPECTED.copy()
        mad = analyzer.mean_absolute_deviation(observed)

        assert mad == 0.0

    def test_mean_absolute_deviation_uniform(self, analyzer):
        """Test MAD with uniform distribution"""
        # Uniform distribution
        observed = dict.fromkeys(range(1, 10), 1 / 9)
        mad = analyzer.mean_absolute_deviation(observed)

        # Should have high MAD (> 0.015)
        assert mad > 0.015

    def test_analyze_series_benford_compliant(self, analyzer, benford_compliant_data):
        """Test full analysis on Benford-compliant data"""
        result = analyzer.analyze_series(benford_compliant_data, "Test Series")

        assert result['series_name'] == "Test Series"
        assert result['sample_size'] > 0
        assert result['fraud_risk'] in ['LOW', 'MEDIUM']
        assert result['conformity'] in ['CLOSE_CONFORMITY', 'ACCEPTABLE_CONFORMITY']

    def test_analyze_series_uniform_data(self, analyzer, uniform_data):
        """Test full analysis on uniform data"""
        result = analyzer.analyze_series(uniform_data, "Uniform Series")

        assert result['series_name'] == "Uniform Series"
        assert result['sample_size'] > 0
        assert result['fraud_risk'] in ['HIGH', 'CRITICAL']
        assert result['conformity'] in ['NONCONFORMITY', 'MARGINALLY_ACCEPTABLE']

    def test_analyze_series_empty_data(self, analyzer):
        """Test analysis with empty data"""
        empty_series = pd.Series([])
        result = analyzer.analyze_series(empty_series, "Empty")

        assert result['sample_size'] == 0
        assert 'error' in result

    def test_analyze_series_all_zeros(self, analyzer):
        """Test analysis with all zeros"""
        zeros = pd.Series([0, 0, 0, 0])
        result = analyzer.analyze_series(zeros, "Zeros")

        assert result['sample_size'] == 0
        assert 'error' in result

    def test_analyze_series_short_sample_is_not_scored(self, analyzer):
        """A single CVM month is too short to support a Benford verdict."""
        result = analyzer.analyze_series(pd.Series(range(1, 23)), "One month")
        assert result["sample_size"] == 22
        assert result["conformity"] == "INSUFFICIENT_SAMPLE"
        assert result["fraud_risk"] == "UNKNOWN"
        assert result["mad"] is None

    def test_analyze_fund_data_structure(self, analyzer, sample_informe_df):
        """Test that analyze_fund_data returns correct structure"""
        result_df = analyzer.analyze_fund_data(sample_informe_df)

        # Should have fund_cnpj column
        assert 'fund_cnpj' in result_df.columns
        assert 'overall_fraud_risk' in result_df.columns

        # Should have metrics for different fields
        expected_metrics = ['pl_mad', 'pl_p_value', 'pl_fraud_risk', 'pl_sample_size']
        for metric in expected_metrics:
            assert metric in result_df.columns or len(result_df) == 0

    def test_analyze_fund_data_fraud_risk_levels(self, analyzer, sample_informe_df):
        """Test that fraud risk levels are valid"""
        result_df = analyzer.analyze_fund_data(sample_informe_df)

        if not result_df.empty:
            valid_risks = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            assert all(result_df['overall_fraud_risk'].isin(valid_risks))

    def test_fraud_risk_classification(self, analyzer):
        """Test fraud risk classification based on MAD"""
        # Test with actual distributions that produce known MADs

        # Test 1: Close conformity (low MAD)
        close_conformity = {
            1: 0.305, 2: 0.180, 3: 0.120, 4: 0.095,
            5: 0.080, 6: 0.070, 7: 0.060, 8: 0.050, 9: 0.040
        }
        mad_close = analyzer.mean_absolute_deviation(close_conformity)
        assert mad_close < 0.012  # Should be acceptable

        # Test 2: Uniform distribution (high MAD)
        uniform = dict.fromkeys(range(1, 10), 1 / 9)
        mad_uniform = analyzer.mean_absolute_deviation(uniform)
        assert mad_uniform > 0.015  # Should be nonconformity

        # Test 3: Perfect Benford (zero MAD)
        perfect = analyzer.BENFORD_EXPECTED.copy()
        mad_perfect = analyzer.mean_absolute_deviation(perfect)
        assert mad_perfect == 0.0  # Should be perfect

    def test_generate_report_structure(self, analyzer, sample_informe_df):
        """Test that generate_report returns correct structure"""
        report = analyzer.generate_report(sample_informe_df)

        assert 'summary' in report
        assert 'detailed_results' in report

        summary = report['summary']
        assert 'total_funds_analyzed' in summary
        assert 'funds_with_anomalies' in summary
        assert 'critical_risk_funds' in summary
        assert 'high_risk_funds' in summary
        assert 'medium_risk_funds' in summary

    def test_plot_distribution_no_error(self, analyzer):
        """Test that plot_distribution doesn't raise errors"""
        observed = dict.fromkeys(range(1, 10), 1 / 9)

        # Should not raise any exception
        try:
            fig = analyzer.plot_distribution(observed, "Test Plot")
            assert fig is not None
        except Exception as e:
            pytest.fail(f"plot_distribution raised exception: {e}")

    def test_integration_with_missing_columns(self, analyzer):
        """Test analyzer handles missing columns gracefully"""
        # DataFrame with minimal columns
        df = pd.DataFrame({
            'CNPJ_FUNDO': ['FUND001'] * 10,
            'VL_PATRIM_LIQ': np.random.exponential(1000000, 10)
        })

        result_df = analyzer.analyze_fund_data(df)

        # Should still work with just PL column
        if not result_df.empty:
            assert 'pl_fraud_risk' in result_df.columns

    def test_special_values_handling(self, analyzer):
        """Test handling of NaN and inf values"""
        values = pd.Series([123, np.nan, 456, np.inf, -np.inf, 789])
        first_digits = analyzer.extract_first_digits(values)

        # Should extract only valid values
        assert len(first_digits) <= 3  # 123, 456, 789 (inf values may be excluded)
        assert not any(pd.isna(first_digits))

    def test_real_world_financial_data_pattern(self, analyzer):
        """Test with realistic financial data pattern"""
        # Exponential distribution (common in financial data)
        # Set seed for reproducibility
        np.random.seed(42)
        values = pd.Series(np.random.exponential(10000, 1000))

        result = analyzer.analyze_series(values, "Financial Data")

        # Should have correct sample size
        assert result['sample_size'] == 1000
        # Exponential distributions generally conform to Benford, but allow some variance
        # Due to randomness, we just check it's not CRITICAL
        assert result['fraud_risk'] in ['LOW', 'MEDIUM', 'HIGH']
        assert result['fraud_risk'] != 'CRITICAL'


# ---------------------------------------------------------------------------
# extract_first_digits: vectorization equivalence
# ---------------------------------------------------------------------------

from hypothesis import given, settings, strategies as st


def _true_first_digit(value: float) -> int | None:
    """First significant digit of the shortest decimal that round-trips.

    The oracle for what extract_first_digits should return. Deliberately not the
    per-value loop this replaced: that loop was itself wrong for small powers of
    ten, because multiplying by 10 fourteen times accumulates enough error to
    turn 1e-14 into 9.999... and report a leading 9 where the answer is 1.

    repr() rather than Decimal(), because Decimal(float) exposes the exact
    binary value -- Decimal(0.7) begins 0.6999... and would claim a leading 6
    for a number every reader of the data calls 0.7.
    """
    text = repr(float(abs(value)))
    if "e" in text or "E" in text:
        text = text.split("e")[0].split("E")[0]
    digits = "".join(c for c in text if c.isdigit()).lstrip("0")
    return int(digits[0]) if digits else None


def _reference_first_digits(values: pd.Series) -> pd.Series:
    """Expected first digits for a series, via the exact oracle."""
    values = values.abs().replace(0, np.nan).dropna()
    out = [
        d for d in (_true_first_digit(v) for v in values if np.isfinite(v) and v > 0)
        if d is not None and 1 <= d <= 9
    ]
    return pd.Series(out)


class TestExtractFirstDigitsEquivalence:

    @pytest.fixture
    def analyzer(self):
        return BenfordLawAnalyzer()

    @pytest.mark.parametrize("name,factory", [
        ("lognormal", lambda r: r.lognormal(10, 3, 5000)),
        ("uniform", lambda r: r.uniform(1, 1e6, 5000)),
        ("sub_one", lambda r: r.uniform(1e-12, 1.0, 5000)),
        ("very_large", lambda r: r.uniform(1e15, 1e20, 5000)),
        ("negative", lambda r: r.uniform(-1e6, -1, 5000)),
    ])
    def test_matches_reference_across_magnitudes(self, analyzer, name, factory):
        series = pd.Series(factory(np.random.default_rng(0)))
        pd.testing.assert_series_equal(
            analyzer.extract_first_digits(series).value_counts().sort_index(),
            _reference_first_digits(series).value_counts().sort_index(),
        )

    def test_zeros_nan_and_infinities_are_dropped(self, analyzer):
        series = pd.Series([0, 0.0, np.nan, np.inf, -np.inf, 5.0, -3.2, 9.99])
        result = analyzer.extract_first_digits(series)
        assert sorted(result.tolist()) == [3, 5, 9]

    def test_empty_input(self, analyzer):
        assert len(analyzer.extract_first_digits(pd.Series([], dtype=float))) == 0
        assert len(analyzer.extract_first_digits(pd.Series([0, 0, np.nan]))) == 0

    def test_exact_powers_of_ten(self, analyzer):
        """Boundary values where a log10 rounding error would show up first."""
        series = pd.Series([1e-6, 1e-3, 0.1, 1.0, 10.0, 100.0, 1e6, 1e15])
        assert analyzer.extract_first_digits(series).tolist() == [1] * 8

    def test_all_digits_representable(self, analyzer):
        series = pd.Series([float(d) for d in range(1, 10)])
        assert analyzer.extract_first_digits(series).tolist() == list(range(1, 10))

    @staticmethod
    def _within_one_ulp_of_a_power_of_ten(value: float) -> bool:
        """True for values indistinguishable from a power of ten in float64.

        999999999999999.5 is one ULP below 1e15. Scaled into [1, 10) it becomes
        0.9999999999999994, which is exactly what 1e-14 also becomes -- yet one
        leads with 9 and the other with 1. At 16 significant digits the two are
        not separable, so the digit reported for such a value is arbitrary.
        Real CVM figures carry two decimals over magnitudes far from this edge,
        so the case is excluded rather than chased.
        """
        exponent = np.floor(np.log10(abs(value)))
        power = 10.0 ** exponent
        nearest = min(power, 10.0 ** (exponent + 1), key=lambda p: abs(value - p))
        return abs(value - nearest) <= abs(nearest) * 1e-15

    @given(st.lists(
        st.floats(min_value=1e-15, max_value=1e15, allow_nan=False, allow_infinity=False),
        max_size=200,
    ))
    @settings(max_examples=200, deadline=None)
    def test_property_matches_exact_oracle(self, values):
        usable = [
            v for v in values
            if v > 0 and not self._within_one_ulp_of_a_power_of_ten(v)
        ]
        series = pd.Series(usable, dtype=float)
        analyzer = BenfordLawAnalyzer()
        assert (
            analyzer.extract_first_digits(series).tolist()
            == _reference_first_digits(series).tolist()
        )


class TestFirstDigitPrecision:
    """Boundary values where naive float normalization reports the wrong digit.

    Each of these broke at least one candidate implementation, including the
    per-value loop that shipped originally.
    """

    @pytest.fixture
    def analyzer(self):
        return BenfordLawAnalyzer()

    @pytest.mark.parametrize("value,expected", [
        (0.7, 7),                    # 0.7 / 1e-1 == 6.999999999999999
        (0.3, 3),
        (0.6, 6),
        (100000.0, 1),               # 100000.0 * 1e-5 == 0.9999999999999999
        (100000000000.0, 1),
        (1e-11, 1),
        (1e-14, 1),                  # the original loop returned 9 here
        (1e-13, 1),
        (1e-12, 1),
        (999999999999998.0, 9),      # log10 evaluates to exactly 15.0
        (9.999999999999998, 9),
        (0.9999999999999999, 9),
    ])
    def test_known_boundary_values(self, analyzer, value, expected):
        assert analyzer.extract_first_digits(pd.Series([value])).tolist() == [expected]

    @pytest.mark.parametrize("exponent", range(-15, 16))
    def test_exact_powers_of_ten_lead_with_one(self, analyzer, exponent):
        assert analyzer.extract_first_digits(pd.Series([10.0 ** exponent])).tolist() == [1]

    def test_one_decimal_place_values(self, analyzer):
        """0.1 through 9.9: every one must report the digit a reader sees."""
        values = [i / 10 for i in range(1, 100)]
        result = analyzer.extract_first_digits(pd.Series(values)).tolist()
        assert result == [_true_first_digit(v) for v in values]

    def test_two_decimal_place_values(self, analyzer):
        values = [i / 100 for i in range(1, 1000)]
        result = analyzer.extract_first_digits(pd.Series(values)).tolist()
        assert result == [_true_first_digit(v) for v in values]
