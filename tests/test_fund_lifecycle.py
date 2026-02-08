"""Tests for FundLifecycleAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.fund_lifecycle import FundLifecycleAnalyzer


@pytest.fixture
def analyzer():
    return FundLifecycleAnalyzer()


class TestFundLifecycle:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_cadastro(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "DT_CONST"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_short_lived_fund_detected(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "DT_CONST": ["2024-01-01", "2020-01-01"],
            "DT_CANCEL": ["2024-04-01", "2024-12-01"],  # fund1: 91 days, fund2: ~5 years
        })
        result = analyzer.analyze(cadastro)
        short = result[result["signal_type"] == "short_lived_fund"]
        assert len(short) == 1
        assert short.iloc[0]["CNPJ_FUNDO"] == "fund1"
        assert short.iloc[0]["days_active"] == 91

    def test_coordinated_creation_detected(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["f1", "f2", "f3", "f4"],
            "CNPJ_ADMIN": ["admin1", "admin1", "admin1", "admin2"],
            "DT_CONST": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-01"],
        })
        result = analyzer.analyze(cadastro)
        coordinated = result[result["signal_type"] == "coordinated_creation"]
        assert len(coordinated) == 1
        assert coordinated.iloc[0]["CNPJ_FUNDO"] == "admin1"

    def test_hot_start_detected(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "DT_CONST": ["2024-01-01"],
        })
        informe = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 5,
            "DT_COMPTC": pd.date_range("2024-01-02", periods=5),
            "VL_PATRIM_LIQ": [10_000_000, 30_000_000, 60_000_000, 80_000_000, 100_000_000],
        })
        result = analyzer.analyze(cadastro, informe_df=informe)
        hot = result[result["signal_type"] == "hot_start"]
        assert len(hot) == 1
        assert hot.iloc[0]["severity"] in ("HIGH", "CRITICAL")

    def test_suspicious_inflow_timing(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "DT_CONST": ["2024-01-01"],
        })
        informe = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 3,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=3),
            "VL_PATRIM_LIQ": [0, 50_000_000, 80_000_000],
            "CAPTC_DIA": [0, 50_000_000, 30_000_000],
        })
        result = analyzer.analyze(cadastro, informe_df=informe)
        inflow = result[result["signal_type"] == "suspicious_inflow_timing"]
        assert len(inflow) == 1

    def test_no_signals_for_long_lived_funds(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "DT_CONST": ["2020-01-01"],
            "DT_CANCEL": ["2024-12-31"],
        })
        result = analyzer.analyze(cadastro)
        assert result.empty or len(result[result["signal_type"] == "short_lived_fund"]) == 0
