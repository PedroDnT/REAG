"""
Integration Test - Full Fraud Detection Workflow

Tests the complete fraud investigation pipeline from data loading
through all analysis stages to final reporting.

Converted from custom IntegrationWorkflowTest class to pytest format.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Fixture: creates a realistic fraud scenario
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fraud_scenario():
    """
    Create realistic test data simulating a fraud scheme.

    Scenario: Small administrator manages multiple funds with:
    1. Circular investments between funds
    2. Phantom assets (fake stocks)
    3. Overvalued private assets
    4. Excessive concentration
    5. Unrealistic returns (Ponzi-like)
    """
    np.random.seed(42)

    admin_fraud = "11111111000101"
    admin_legit = "22222222000101"

    fraud_funds = [f"9000000{i}000101" for i in range(10)]
    legit_funds = [f"8000000{i}000101" for i in range(10)]
    all_funds = fraud_funds + legit_funds

    # Cadastro
    cadastro_data = []
    for fund in fraud_funds:
        cadastro_data.append({
            "CNPJ_FUNDO": fund,
            "CNPJ_ADMIN": admin_fraud,
            "CLASSE": np.random.choice(["Fundo Multimercado", "Fundo de Renda Fixa"]),
        })
    for fund in legit_funds:
        cadastro_data.append({
            "CNPJ_FUNDO": fund,
            "CNPJ_ADMIN": admin_legit,
            "CLASSE": np.random.choice(["Fundo de Ações", "Fundo de Renda Fixa", "Fundo Multimercado"]),
        })
    cadastro_df = pd.DataFrame(cadastro_data)

    # Informe Diario (60 days)
    dates = pd.date_range(start="2024-01-01", periods=60, freq="D")
    informe_data = []
    for fund in all_funds:
        is_fraud = fund in fraud_funds
        base_quota = 1.0
        for date in dates:
            if is_fraud:
                daily_return = np.random.normal(0.003, 0.0005)
            else:
                daily_return = np.random.normal(0.0003, 0.01)
            base_quota *= (1 + daily_return)
            informe_data.append({
                "CNPJ_FUNDO": fund,
                "DT_COMPTC": date,
                "VL_QUOTA": base_quota,
                "VL_PATRIM_LIQ": np.random.uniform(50_000_000, 200_000_000),
                "CAPTC_DIA": np.random.uniform(0, 5_000_000) if is_fraud else np.random.uniform(0, 1_000_000),
                "RESG_DIA": np.random.uniform(0, 1_000_000),
                "NR_COTST": np.random.randint(100, 1000),
            })
    informe_df = pd.DataFrame(informe_data)
    informe_df["FLUXO_LIQ_DIA"] = informe_df["CAPTC_DIA"] - informe_df["RESG_DIA"]

    # CDA
    cda_data = []
    legit_stocks = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "B3SA3"]
    phantom_stocks = ["FAKE4", "GHOST3", "FRAUD4"]
    shell_issuers = [
        "EMPRESA RAPIDA LTDA ME",
        "NEGOCIOS FINANCEIROS EIRELI",
        "INVESTIMENTOS FACIL LTDA ME",
    ]
    date_cda = datetime(2024, 1, 31)

    for fund in all_funds:
        is_fraud = fund in fraud_funds
        if is_fraud:
            other_fraud = [f for f in fraud_funds if f != fund]
            for other_fund in np.random.choice(other_fraud, 3, replace=False):
                cda_data.append({
                    "CNPJ_FUNDO": fund, "CD_ATIVO": other_fund,
                    "VL_MERCADO": np.random.uniform(10_000_000, 30_000_000),
                    "QT_POS": 1, "DT_COMPTC": date_cda, "EMISSOR": "FUNDO DE INVESTIMENTO",
                })
            for phantom in phantom_stocks:
                cda_data.append({
                    "CNPJ_FUNDO": fund, "CD_ATIVO": phantom,
                    "VL_MERCADO": np.random.uniform(5_000_000, 15_000_000),
                    "QT_POS": np.random.uniform(100_000, 500_000),
                    "DT_COMPTC": date_cda, "EMISSOR": "EMPRESA FICTICIA",
                })
            for i, issuer in enumerate(shell_issuers):
                cda_data.append({
                    "CNPJ_FUNDO": fund,
                    "CD_ATIVO": f"DEB_{issuer.split()[0]}_{2024 + i}",
                    "VL_MERCADO": np.random.uniform(20_000_000, 50_000_000),
                    "QT_POS": 1, "DT_COMPTC": date_cda, "EMISSOR": issuer,
                })
            for stock in np.random.choice(legit_stocks, 2):
                cda_data.append({
                    "CNPJ_FUNDO": fund, "CD_ATIVO": stock,
                    "VL_MERCADO": np.random.uniform(1_000_000, 5_000_000),
                    "QT_POS": np.random.uniform(10_000, 50_000),
                    "DT_COMPTC": date_cda, "EMISSOR": "EMPRESA LEGITIMA SA",
                })
        else:
            for stock in np.random.choice(legit_stocks, 5):
                cda_data.append({
                    "CNPJ_FUNDO": fund, "CD_ATIVO": stock,
                    "VL_MERCADO": np.random.uniform(5_000_000, 20_000_000),
                    "QT_POS": np.random.uniform(50_000, 200_000),
                    "DT_COMPTC": date_cda, "EMISSOR": "EMPRESA LEGITIMA SA",
                })
            cda_data.append({
                "CNPJ_FUNDO": fund, "CD_ATIVO": "DEB_PETROBRAS_2025",
                "VL_MERCADO": np.random.uniform(10_000_000, 30_000_000),
                "QT_POS": 1, "DT_COMPTC": date_cda, "EMISSOR": "PETROBRAS",
            })

    cda_df = pd.DataFrame(cda_data)

    return cadastro_df, informe_df, cda_df, fraud_funds


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_phantom_asset_detection(fraud_scenario):
    cadastro_df, informe_df, cda_df, known_fraud_funds = fraud_scenario
    from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector

    detector = EnhancedPhantomAssetDetector()
    detector.update_registries()
    results = detector.detect_enhanced_phantom_assets(cda_df)
    assert isinstance(results, pd.DataFrame)


@pytest.mark.integration
def test_fraud_scheme_detection(fraud_scenario):
    cadastro_df, informe_df, cda_df, known_fraud_funds = fraud_scenario
    from src.analyzers.fraud_schemes import FraudSchemeDetector

    detector = FraudSchemeDetector()
    schemes = detector.generate_fraud_scheme_report(informe_df, cda_df, cadastro_df)

    assert "circular_flow" in schemes
    assert "layered_funds" in schemes
    assert "asset_inflation" in schemes
    assert "shell_networks" in schemes

    for key, df in schemes.items():
        assert isinstance(df, pd.DataFrame)


@pytest.mark.integration
def test_peer_comparison(fraud_scenario):
    cadastro_df, informe_df, cda_df, known_fraud_funds = fraud_scenario
    from src.analyzers.peer_comparison import PeerComparisonAnalyzer

    analyzer = PeerComparisonAnalyzer()
    analyzer.load_fund_categories(cadastro_df)
    metrics = analyzer.calculate_fund_metrics(informe_df)
    assert isinstance(metrics, pd.DataFrame)
    assert len(metrics) > 0

    comparison = analyzer.compare_with_peers(known_fraud_funds[:5], metrics)
    assert isinstance(comparison, pd.DataFrame)

    smoothed = analyzer.detect_smoothed_returns(informe_df, known_fraud_funds)
    assert isinstance(smoothed, pd.DataFrame)


@pytest.mark.integration
def test_concentration_analysis(fraud_scenario):
    cadastro_df, informe_df, cda_df, known_fraud_funds = fraud_scenario
    from src.analyzers.concentration import ConcentrationAnalyzer

    analyzer = ConcentrationAnalyzer()
    violations = analyzer.detect_excessive_concentration(cda_df, cadastro_df)
    assert isinstance(violations, pd.DataFrame)


@pytest.mark.integration
def test_scenario_has_expected_data(fraud_scenario):
    """Verify the test scenario fixture produces expected data shapes."""
    cadastro_df, informe_df, cda_df, fraud_funds = fraud_scenario
    assert len(cadastro_df) == 20
    assert len(fraud_funds) == 10
    assert len(informe_df) > 0
    assert len(cda_df) > 0
    assert "CNPJ_FUNDO" in cadastro_df.columns
    assert "CNPJ_FUNDO" in informe_df.columns
    assert "CNPJ_FUNDO" in cda_df.columns
