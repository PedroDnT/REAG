"""Tests for PortfolioReconciliationAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.portfolio_reconciliation import PortfolioReconciliationAnalyzer


@pytest.fixture
def analyzer():
    return PortfolioReconciliationAnalyzer()


class TestPortfolioReconciliation:
    def test_missing_cda_columns_raises(self, analyzer):
        cda = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        informe = pd.DataFrame({"CNPJ_FUNDO": ["123"], "DT_COMPTC": ["2024-01-01"], "VL_PATRIM_LIQ": [1e6]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(cda, informe)

    def test_missing_informe_columns_raises(self, analyzer):
        cda = pd.DataFrame({"CNPJ_FUNDO": ["123"], "VL_MERCADO": [1e6]})
        informe = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(cda, informe)

    def test_empty_dataframes(self, analyzer):
        cda = pd.DataFrame(columns=["CNPJ_FUNDO", "VL_MERCADO"])
        informe = pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"])
        result = analyzer.analyze(cda, informe)
        assert result.empty

    def test_static_gap_detected(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund1"],
            "VL_MERCADO": [300_000, 200_000],  # total = 500k
        })
        informe = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "DT_COMPTC": ["2024-01-01"],
            "VL_PATRIM_LIQ": [1_000_000],  # CDA total is 50% of PL
        })
        result = analyzer.analyze(cda, informe)
        gaps = result[result["signal_type"] == "static_reconciliation_gap"]
        assert len(gaps) == 1
        assert gaps.iloc[0]["gap_pct"] == 50.0

    def test_hidden_positions_detected(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "VL_MERCADO": [100_000],
        })
        informe = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "DT_COMPTC": ["2024-01-01", "2024-01-01"],
            "VL_PATRIM_LIQ": [100_000, 10_000_000],  # fund2 not in CDA
        })
        result = analyzer.analyze(cda, informe)
        hidden = result[result["signal_type"] == "hidden_positions"]
        assert len(hidden) == 1
        assert hidden.iloc[0]["CNPJ_FUNDO"] == "fund2"

    def test_no_signals_when_aligned(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund1"],
            "VL_MERCADO": [500_000, 500_000],  # total = 1M
        })
        informe = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "DT_COMPTC": ["2024-01-01"],
            "VL_PATRIM_LIQ": [1_000_000],
        })
        result = analyzer.analyze(cda, informe)
        assert result.empty
