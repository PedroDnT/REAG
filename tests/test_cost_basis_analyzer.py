"""Tests for CostBasisAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.cost_basis_analyzer import CostBasisAnalyzer


@pytest.fixture
def analyzer():
    return CostBasisAnalyzer()


class TestCostBasisAnalyzer:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_dataframe(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO", "VL_CUSTO_POS_FINAL"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_unrealized_gain_anomaly(self, analyzer):
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"] * 3,
            "CD_ATIVO": ["A", "B", "C"],
            "VL_MERCADO": [1_000_000, 500_000, 100_000],
            "VL_CUSTO_POS_FINAL": [100_000, 400_000, 80_000],  # A has 10x gain
        })
        result = analyzer.analyze(df)
        gain_anomalies = result[result["signal_type"] == "unrealized_gain_anomaly"]
        assert len(gain_anomalies) >= 1
        assert gain_anomalies.iloc[0]["CD_ATIVO"] == "A"
        assert gain_anomalies.iloc[0]["gain_ratio"] == 10.0

    def test_zero_cost_assets(self, analyzer):
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CD_ATIVO": ["A", "B"],
            "VL_MERCADO": [500_000, 50_000],
            "VL_CUSTO_POS_FINAL": [0, 0],
        })
        result = analyzer.analyze(df)
        zero_cost = result[result["signal_type"] == "zero_cost_asset"]
        assert len(zero_cost) == 1  # Only fund1 exceeds COST_BASIS_ZERO_VALUE_MIN
        assert zero_cost.iloc[0]["severity"] == "HIGH"

    def test_negative_cost_basis(self, analyzer):
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "CD_ATIVO": ["A"],
            "VL_MERCADO": [100_000],
            "VL_CUSTO_POS_FINAL": [-50_000],
        })
        result = analyzer.analyze(df)
        negative = result[result["signal_type"] == "negative_cost_basis"]
        assert len(negative) == 1
        assert negative.iloc[0]["severity"] == "CRITICAL"

    def test_systematic_overvaluation(self, analyzer):
        records = []
        # Many normal funds with gain ratio ~1.0
        for i in range(20):
            records.append({
                "CNPJ_FUNDO": f"fund{i:04d}",
                "CD_ATIVO": "A",
                "VL_MERCADO": 100_000,
                "VL_CUSTO_POS_FINAL": 95_000,
            })
        # One outlier with very high gain ratio
        records.append({
            "CNPJ_FUNDO": "outlier",
            "CD_ATIVO": "X",
            "VL_MERCADO": 1_000_000,
            "VL_CUSTO_POS_FINAL": 50_000,
        })
        df = pd.DataFrame(records)
        result = analyzer.analyze(df)
        overval = result[result["signal_type"] == "systematic_overvaluation"]
        assert len(overval) >= 1
        assert overval.iloc[0]["CNPJ_FUNDO"] == "outlier"

    def test_no_signals_for_normal_data(self, analyzer):
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CD_ATIVO": ["A", "B"],
            "VL_MERCADO": [100_000, 200_000],
            "VL_CUSTO_POS_FINAL": [95_000, 190_000],
        })
        result = analyzer.analyze(df)
        assert result.empty

    def test_gain_severity(self):
        assert CostBasisAnalyzer._gain_severity(25.0) == "CRITICAL"
        assert CostBasisAnalyzer._gain_severity(12.0) == "HIGH"
        assert CostBasisAnalyzer._gain_severity(6.0) == "MEDIUM"
        assert CostBasisAnalyzer._gain_severity(2.0) == "LOW"
