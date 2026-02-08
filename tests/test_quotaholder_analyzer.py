"""Tests for QuotaholderAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.quotaholder_analyzer import QuotaholderAnalyzer


@pytest.fixture
def analyzer():
    return QuotaholderAnalyzer()


def _make_informe(records):
    df = pd.DataFrame(records)
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])
    return df


class TestQuotaholderAnalyzer:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_dataframe(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "NR_COTST", "VL_PATRIM_LIQ"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_mass_exodus_detected(self, analyzer):
        records = []
        for i in range(10):
            cotst = 100 if i < 5 else 30  # 70% drop at day 5
            records.append({
                "CNPJ_FUNDO": "12345678000100",
                "DT_COMPTC": f"2024-01-{i+1:02d}",
                "NR_COTST": cotst,
                "VL_PATRIM_LIQ": 1_000_000,
            })
        df = _make_informe(records)
        result = analyzer.analyze(df)
        exodus = result[result["signal_type"] == "mass_exodus"]
        assert len(exodus) > 0
        assert exodus.iloc[0]["severity"] in ("MEDIUM", "HIGH", "CRITICAL")

    def test_phantom_participation_detected(self, analyzer):
        records = [
            {"CNPJ_FUNDO": "11111111000100", "DT_COMPTC": "2024-01-01", "NR_COTST": 100, "VL_PATRIM_LIQ": 1e6},
            {"CNPJ_FUNDO": "11111111000100", "DT_COMPTC": "2024-01-02", "NR_COTST": 150, "VL_PATRIM_LIQ": 1e6},  # +50%
            {"CNPJ_FUNDO": "11111111000100", "DT_COMPTC": "2024-01-03", "NR_COTST": 90, "VL_PATRIM_LIQ": 1e6},   # -40%
        ]
        df = _make_informe(records)
        result = analyzer.analyze(df)
        phantom = result[result["signal_type"] == "phantom_participation"]
        assert len(phantom) >= 1

    def test_per_capita_aum_anomaly(self, analyzer):
        records = []
        # Many normal funds
        for i in range(20):
            records.append({
                "CNPJ_FUNDO": f"fund{i:04d}0000000100",
                "DT_COMPTC": "2024-01-01",
                "NR_COTST": 100,
                "VL_PATRIM_LIQ": 1_000_000,
            })
        # One extreme outlier
        records.append({
            "CNPJ_FUNDO": "outlier00000100",
            "DT_COMPTC": "2024-01-01",
            "NR_COTST": 2,
            "VL_PATRIM_LIQ": 500_000_000,
        })
        df = _make_informe(records)
        result = analyzer.analyze(df)
        per_capita = result[result["signal_type"] == "per_capita_aum_anomaly"]
        assert len(per_capita) >= 1
        assert per_capita.iloc[0]["CNPJ_FUNDO"] == "outlier00000100"

    def test_no_signals_for_stable_data(self, analyzer):
        records = []
        for i in range(10):
            records.append({
                "CNPJ_FUNDO": "12345678000100",
                "DT_COMPTC": f"2024-01-{i+1:02d}",
                "NR_COTST": 100,
                "VL_PATRIM_LIQ": 1_000_000,
            })
        df = _make_informe(records)
        result = analyzer.analyze(df)
        assert result.empty or len(result) == 0

    def test_severity_levels(self):
        assert QuotaholderAnalyzer._exodus_severity(65) == "CRITICAL"
        assert QuotaholderAnalyzer._exodus_severity(50) == "HIGH"
        assert QuotaholderAnalyzer._exodus_severity(35) == "MEDIUM"
        assert QuotaholderAnalyzer._exodus_severity(10) == "LOW"
