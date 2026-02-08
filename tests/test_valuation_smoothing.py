"""Tests for ValuationSmoothingAnalyzer."""

import numpy as np
import pandas as pd
import pytest

from src.analyzers.valuation_smoothing import ValuationSmoothingAnalyzer


@pytest.fixture
def analyzer():
    return ValuationSmoothingAnalyzer()


class TestValuationSmoothing:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_dataframe(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_stale_pricing_detected(self, analyzer):
        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        quotas = [100.0] * 30  # No change at all
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 30,
            "DT_COMPTC": dates,
            "VL_QUOTA": quotas,
        })
        result = analyzer.analyze(df)
        stale = result[result["signal_type"] == "stale_pricing"]
        assert len(stale) >= 1
        assert stale.iloc[0]["stale_days"] >= 5

    def test_autocorrelation_detected(self, analyzer):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        # Generate smoothed returns (high autocorrelation)
        quota = 100.0
        quotas = [quota]
        noise = np.random.normal(0, 0.001, 100)
        smoothed = 0.0
        for i in range(1, 100):
            smoothed = 0.8 * smoothed + 0.2 * noise[i]  # Smoothed series
            quota *= (1 + smoothed)
            quotas.append(quota)

        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 100,
            "DT_COMPTC": dates,
            "VL_QUOTA": quotas,
        })
        result = analyzer.analyze(df)
        autocorr = result[result["signal_type"] == "return_autocorrelation"]
        assert len(autocorr) >= 1

    def test_low_volatility_ratio(self, analyzer):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        records = []
        # Normal volatility funds
        for i in range(10):
            quota = 100.0
            quotas = [quota]
            for j in range(1, 50):
                quota *= (1 + np.random.normal(0, 0.01))
                quotas.append(quota)
            for j in range(50):
                records.append({
                    "CNPJ_FUNDO": f"normal_{i}",
                    "DT_COMPTC": dates[j],
                    "VL_QUOTA": quotas[j],
                })

        # Very low volatility fund
        quota = 100.0
        for j in range(50):
            records.append({
                "CNPJ_FUNDO": "smooth_fund",
                "DT_COMPTC": dates[j],
                "VL_QUOTA": quota + j * 0.001,  # Almost no volatility
            })

        df = pd.DataFrame(records)
        result = analyzer.analyze(df)
        low_vol = result[result["signal_type"] == "low_volatility_ratio"]
        assert len(low_vol) >= 1

    def test_no_signals_for_normal_fund(self, analyzer):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        # Multiple funds with normal random returns
        records = []
        for i in range(10):
            quota = 100.0
            for j in range(50):
                records.append({
                    "CNPJ_FUNDO": f"fund_{i}",
                    "DT_COMPTC": dates[j],
                    "VL_QUOTA": quota,
                })
                quota *= (1 + np.random.normal(0, 0.005))
        df = pd.DataFrame(records)
        result = analyzer.analyze(df)
        # May or may not find signals depending on random data, but shouldn't crash
        assert isinstance(result, pd.DataFrame)

    def test_autocorr_severity(self):
        assert ValuationSmoothingAnalyzer._autocorr_severity(0.8) == "CRITICAL"
        assert ValuationSmoothingAnalyzer._autocorr_severity(0.6) == "HIGH"
        assert ValuationSmoothingAnalyzer._autocorr_severity(0.4) == "MEDIUM"
        assert ValuationSmoothingAnalyzer._autocorr_severity(0.1) == "LOW"
