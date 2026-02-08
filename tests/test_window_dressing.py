"""Tests for WindowDressingDetector."""

import numpy as np
import pandas as pd
import pytest

from src.analyzers.window_dressing import WindowDressingDetector


@pytest.fixture
def analyzer():
    return WindowDressingDetector()


class TestWindowDressing:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_dataframe(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_month_end_spike_detected(self, analyzer):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", "2024-06-30", freq="B")
        quotas = [100.0]
        for i in range(1, len(dates)):
            day = dates[i].day
            days_in_month = dates[i].days_in_month
            if days_in_month - day <= 1:
                # Month-end: artificially high return
                quotas.append(quotas[-1] * 1.02)
            else:
                # Normal: small random return
                quotas.append(quotas[-1] * (1 + np.random.normal(0, 0.001)))

        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * len(dates),
            "DT_COMPTC": dates,
            "VL_QUOTA": quotas,
            "VL_PATRIM_LIQ": [1_000_000] * len(dates),
        })
        result = analyzer.analyze(df)
        spikes = result[result["signal_type"] == "month_end_return_spike"]
        assert len(spikes) >= 1

    def test_flow_reversal_detected(self, analyzer):
        dates = pd.date_range("2024-01-01", "2024-06-30", freq="B")
        captc = []
        resg = []
        for d in dates:
            if d.days_in_month - d.day <= 1:
                captc.append(10_000_000)  # Big inflow at month end
                resg.append(0)
            elif d.day <= 2:
                captc.append(0)
                resg.append(10_000_000)  # Big outflow at month start
            else:
                captc.append(100_000)
                resg.append(100_000)

        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * len(dates),
            "DT_COMPTC": dates,
            "VL_QUOTA": [100.0] * len(dates),
            "VL_PATRIM_LIQ": [1_000_000] * len(dates),
            "CAPTC_DIA": captc,
            "RESG_DIA": resg,
        })
        result = analyzer.analyze(df)
        reversal = result[result["signal_type"] == "flow_reversal_pattern"]
        assert len(reversal) >= 1

    def test_no_signals_for_flat_returns(self, analyzer):
        dates = pd.date_range("2024-01-01", "2024-03-31", freq="B")
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * len(dates),
            "DT_COMPTC": dates,
            "VL_QUOTA": [100.0] * len(dates),
            "VL_PATRIM_LIQ": [1_000_000] * len(dates),
        })
        result = analyzer.analyze(df)
        assert result.empty

    def test_insufficient_data_returns_empty(self, analyzer):
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 3,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=3),
            "VL_QUOTA": [100.0, 100.1, 100.2],
            "VL_PATRIM_LIQ": [1e6, 1e6, 1e6],
        })
        result = analyzer.analyze(df)
        assert result.empty
