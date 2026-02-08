"""Tests for ManagerNetworkAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.manager_network import ManagerNetworkAnalyzer


@pytest.fixture
def analyzer():
    return ManagerNetworkAnalyzer()


class TestManagerNetwork:
    def test_missing_columns_raises(self, analyzer):
        df = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(df)

    def test_empty_cadastro(self, analyzer):
        df = pd.DataFrame(columns=["CNPJ_FUNDO", "CNPJ_ADMIN", "CNPJ_GESTOR"])
        result = analyzer.analyze(df)
        assert result.empty

    def test_shared_manager_detected(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": [f"fund{i}" for i in range(6)],
            "CNPJ_ADMIN": ["admin1", "admin2", "admin3", "admin4", "admin1", "admin2"],
            "CNPJ_GESTOR": ["gestor1"] * 6,
        })
        result = analyzer.analyze(cadastro)
        shared = result[result["signal_type"] == "shared_manager_anomaly"]
        assert len(shared) == 1
        assert shared.iloc[0]["num_admins"] == 4

    def test_no_shared_manager_for_single_admin(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CNPJ_ADMIN": ["admin1", "admin1"],
            "CNPJ_GESTOR": ["gestor1", "gestor1"],
        })
        result = analyzer.analyze(cadastro)
        shared = result[result["signal_type"] == "shared_manager_anomaly"] if not result.empty else pd.DataFrame()
        assert shared.empty

    def test_manager_concentration_detected(self, analyzer):
        # Create many managers with normal AUM and one outlier
        records = []
        for i in range(15):
            records.append({
                "CNPJ_FUNDO": f"fund{i}",
                "CNPJ_ADMIN": f"admin{i}",
                "CNPJ_GESTOR": f"gestor{i}",
            })
        records.append({
            "CNPJ_FUNDO": "fund_big",
            "CNPJ_ADMIN": "admin_big",
            "CNPJ_GESTOR": "gestor_big",
        })
        cadastro = pd.DataFrame(records)

        informe_records = []
        for i in range(15):
            informe_records.append({
                "CNPJ_FUNDO": f"fund{i}",
                "DT_COMPTC": "2024-01-01",
                "VL_PATRIM_LIQ": 1_000_000,
            })
        informe_records.append({
            "CNPJ_FUNDO": "fund_big",
            "DT_COMPTC": "2024-01-01",
            "VL_PATRIM_LIQ": 500_000_000,
        })
        informe = pd.DataFrame(informe_records)

        result = analyzer.analyze(cadastro, informe_df=informe)
        concentration = result[result["signal_type"] == "manager_concentration"] if not result.empty else pd.DataFrame()
        assert len(concentration) >= 1

    def test_cross_admin_overlap(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CNPJ_ADMIN": ["admin1", "admin2"],
            "CNPJ_GESTOR": ["gestor1", "gestor1"],
        })
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund1", "fund2", "fund2"],
            "CD_ATIVO": ["asset_shared", "asset_unique1", "asset_shared", "asset_unique2"],
            "VL_MERCADO": [100_000, 200_000, 150_000, 250_000],
        })
        result = analyzer.analyze(cadastro, cda_df=cda)
        overlap = result[result["signal_type"] == "cross_admin_asset_overlap"] if not result.empty else pd.DataFrame()
        assert len(overlap) >= 1

    def test_manager_as_issuer(self, analyzer):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "CNPJ_ADMIN": ["admin1"],
            "CNPJ_GESTOR": ["12345678000100"],
        })
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1"],
            "CD_ATIVO": ["bond1"],
            "VL_MERCADO": [1_000_000],
            "EMISSOR": ["12345678000200"],  # Same first 8 digits as gestor
        })
        result = analyzer.analyze(cadastro, cda_df=cda)
        circular = result[result["signal_type"] == "manager_admin_circular"] if not result.empty else pd.DataFrame()
        assert len(circular) >= 1
        assert circular.iloc[0]["severity"] == "CRITICAL"
