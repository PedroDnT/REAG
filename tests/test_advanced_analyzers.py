"""
Tests for advanced fraud detection analyzers.

Converted from custom AnalyzerTestSuite to proper pytest format.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime


# ---------------------------------------------------------------------------
# Data factory helpers
# ---------------------------------------------------------------------------

def make_sample_cda(num_records=100):
    """Create sample CDA data with various asset types."""
    np.random.seed(42)
    stocks = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3"] * 10
    etfs = ["BOVA11", "SMAL11", "IVVB11"] * 5
    private_assets = [
        "DEB_PETROBRAS_2025", "CRI_ABC_2024", "CRA_AGRO_2026",
        "CDB_BANCO_XYZ", "DEB_EMPRESA_ME_2024",
    ] * 5
    phantom_stocks = ["FAKE4", "GHOST3", "NOPE4"] * 5
    all_assets = stocks + etfs + private_assets + phantom_stocks

    emissor_options = [
        "PETROBRAS", "VALE", "ITAU", "BRADESCO", "AMBEV",
        "Construtora ABC Ltda", "Agro Brasil SA",
        "Banco XYZ SA", "Empresa Fast LTDA ME",
    ]
    emissor_list = (emissor_options * (num_records // len(emissor_options) + 1))[:num_records]

    return pd.DataFrame({
        "CNPJ_FUNDO": [f"12.345.678/0001-{i:02d}" for i in range(num_records)],
        "CD_ATIVO": np.random.choice(all_assets, num_records),
        "VL_MERCADO": np.random.uniform(100_000, 50_000_000, num_records),
        "QT_POS": np.random.uniform(1_000, 100_000, num_records),
        "DT_COMPTC": [datetime(2024, 1, 31)] * num_records,
        "EMISSOR": emissor_list,
    })


def make_sample_informe():
    """Create sample Informe Diario data (30 days x 18 funds)."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
    funds = [f"12.345.678/0001-{i:02d}" for i in range(18)]
    data = []
    for fund in funds:
        for date in dates:
            data.append({
                "CNPJ_FUNDO": fund,
                "DT_COMPTC": date,
                "VL_QUOTA": 1.0 + np.random.normal(0, 0.01),
                "VL_PATRIM_LIQ": np.random.uniform(10_000_000, 100_000_000),
                "CAPTC_DIA": np.random.uniform(0, 1_000_000),
                "RESG_DIA": np.random.uniform(0, 1_000_000),
                "NR_COTST": np.random.randint(10, 1000),
            })
    df = pd.DataFrame(data)
    df["FLUXO_LIQ_DIA"] = df["CAPTC_DIA"] - df["RESG_DIA"]
    return df


def make_sample_cadastro(num_records=50):
    """Create sample Cadastro data."""
    admin_options = ["99.999.999/0001-01", "88.888.888/0001-01"]
    admin_list = (admin_options * (num_records // len(admin_options) + 1))[:num_records]
    classe_options = ["Fundo de Renda Fixa", "Fundo Multimercado", "Fundo de Ações"]
    classe_list = (classe_options * (num_records // len(classe_options) + 1))[:num_records]
    return pd.DataFrame({
        "CNPJ_FUNDO": [f"12.345.678/0001-{i:02d}" for i in range(num_records)],
        "CNPJ_ADMIN": admin_list,
        "CLASSE": classe_list,
    })


# ---------------------------------------------------------------------------
# Data format compatibility
# ---------------------------------------------------------------------------

class TestDataFormatCompatibility:
    def test_cda_has_required_columns(self):
        cda_df = make_sample_cda(50)
        for col in ["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO", "QT_POS", "DT_COMPTC"]:
            assert col in cda_df.columns

    def test_informe_has_required_columns(self):
        informe_df = make_sample_informe()
        for col in ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ"]:
            assert col in informe_df.columns

    def test_cadastro_has_required_columns(self):
        cadastro_df = make_sample_cadastro(25)
        for col in ["CNPJ_FUNDO", "CNPJ_ADMIN"]:
            assert col in cadastro_df.columns

    def test_date_types(self):
        cda_df = make_sample_cda(50)
        assert isinstance(cda_df["DT_COMPTC"].iloc[0], (datetime, pd.Timestamp))

    def test_numeric_types(self):
        cda_df = make_sample_cda(50)
        informe_df = make_sample_informe()
        assert pd.api.types.is_numeric_dtype(cda_df["VL_MERCADO"])
        assert pd.api.types.is_numeric_dtype(informe_df["VL_QUOTA"])


# ---------------------------------------------------------------------------
# Enhanced Phantom Assets Detector
# ---------------------------------------------------------------------------

class TestEnhancedPhantomDetector:
    def test_import_and_init(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        assert detector is not None

    def test_classify_stock(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("PETR4")
        assert result["type"] == "STOCK"
        assert result["should_be_public"] is True

    def test_classify_etf(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("BOVA11")
        assert result["type"] == "ETF"
        assert result["should_be_public"] is True

    def test_classify_fund_cnpj_before_ticker_suffix(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("54.410.358/0001-11")
        assert result["type"] == "FUND"
        assert result["validation_method"] == "CVM_REGISTRY"

    def test_registry_miss_is_unverified_not_phantom(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.enhanced_validate_asset("FAKE4")
        assert result["status"] == "NEEDS_VERIFICATION"
        assert result["fraud_risk"] == "LOW"
        assert result["is_valid"] is None

    def test_fund_registry_miss_is_emitted_when_cadastro_loaded(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        detector.valid_funds = {"11111111000191"}
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["11111111000191"],
            "CD_ATIVO": ["22222222000172"],
            "VL_MERCADO": [100.0],
        })
        result = detector.detect_enhanced_phantom_assets(cda)
        assert len(result) == 1
        assert result.iloc[0]["status"] == "NEEDS_VERIFICATION"
        assert result.iloc[0]["asset_type"] == "FUND"

    def test_stock_cache_miss_is_not_emitted(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["111"],
            "CD_ATIVO": ["FAKE4"],
            "VL_MERCADO": [10.0],
        })
        result = detector.detect_enhanced_phantom_assets(cda)
        assert result.empty or "FAKE4" not in set(result.get("asset_code", pd.Series(dtype=str)))

    def test_blackrock_master_name_is_not_a_circular_flow_lead(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["111"],
            "CD_ATIVO": ["BLACKROCK MASTER REFERENCIADO DI"],
            "VL_MERCADO": [10.0],
            "EMISSOR": ["BLACKROCK MASTER REFERENCIADO DI"],
        })
        result = detector.detect_enhanced_phantom_assets(cda)
        assert result.empty or "BLACKROCK MASTER REFERENCIADO DI" not in set(
            result.get("asset_code", pd.Series(dtype=str))
        )

    def test_classify_bdr(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("AAPL34")
        assert result["type"] == "BDR"
        assert result["should_be_public"] is True

    def test_classify_debenture(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("DEB_ABC_2025")
        assert result["type"] == "DEBENTURE"
        assert result["should_be_public"] is False

    def test_classify_cri(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("CRI_XYZ_2024")
        assert result["type"] == "CRI"
        assert result["should_be_public"] is False

    def test_classify_unknown(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        result = detector.classify_asset_type("XYZABC")
        assert result["type"] == "UNKNOWN"

    def test_detect_returns_dataframe(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        detector.update_registries()
        cda_df = make_sample_cda(50)
        results = detector.detect_enhanced_phantom_assets(cda_df)
        assert isinstance(results, pd.DataFrame)

    def test_detect_output_columns(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        detector.update_registries()
        cda_df = make_sample_cda(50)
        results = detector.detect_enhanced_phantom_assets(cda_df)
        if not results.empty:
            for col in ["asset_code", "asset_type", "status", "fraud_risk"]:
                assert col in results.columns

    def test_detect_raises_on_missing_column(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        detector = EnhancedPhantomAssetDetector()
        with pytest.raises(ValueError, match="CD_ATIVO"):
            detector.detect_enhanced_phantom_assets(pd.DataFrame({"OTHER": [1]}))


# ---------------------------------------------------------------------------
# Fraud Schemes Detector
# ---------------------------------------------------------------------------

class TestFraudSchemeDetector:
    def test_import_and_init(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        assert detector is not None

    def test_circular_flow_returns_dataframe(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        result = detector.detect_circular_flow(
            make_sample_informe(), make_sample_cda(100), make_sample_cadastro(50),
        )
        assert isinstance(result, pd.DataFrame)

    def test_circular_flow_requires_reciprocal_holdings(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector

        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["FUND_A", "FUND_B", "FUND_C"],
            "CNPJ_ADMIN": ["ADMIN_1", "ADMIN_1", "ADMIN_2"],
        })
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["FUND_B", "FUND_A", "FUND_C"],
            "CD_ATIVO": ["FUND_A", "FUND_B", "FUND_A"],
            "VL_MERCADO": [100.0, 80.0, 50.0],
            "QT_POS": [1.0, 1.0, 1.0],
            "DT_COMPTC": ["2024-01-31"] * 3,
        })
        result = FraudSchemeDetector().detect_circular_flow(
            make_sample_informe(), cda, cadastro
        )
        assert set(result["CNPJ_FUNDO"]) == {"FUND_A", "FUND_B"}
        assert result["total_value"].iloc[0] == 180.0
        assert result.iloc[0]["severity"] == "HIGH"

    def test_one_way_same_admin_holding_is_not_called_circular(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["FUND_A", "FUND_B"],
            "CNPJ_ADMIN": ["ADMIN_1", "ADMIN_1"],
        })
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["FUND_A"],
            "CD_ATIVO": ["FUND_B"],
            "VL_MERCADO": [100.0],
        })
        result = FraudSchemeDetector().detect_circular_flow(
            make_sample_informe(), cda, cadastro
        )
        assert result.empty

    def test_circular_flow_scales_without_per_fund_cda_scans(self):
        """Regression: the old loop filtered the full CDA once per fund."""
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        import time

        n_funds = 2000
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": [f"F{i:04d}" for i in range(n_funds)],
            "CNPJ_ADMIN": [f"A{i // 20:03d}" for i in range(n_funds)],
        })
        # Mostly non-fund assets; a handful of same-admin fund holdings.
        cda = pd.DataFrame({
            "CNPJ_FUNDO": [f"F{i:04d}" for i in range(n_funds)] * 5,
            "CD_ATIVO": [f"ASSET{i % 50}" for i in range(n_funds * 5)],
            "VL_MERCADO": [1.0] * (n_funds * 5),
            "QT_POS": [1.0] * (n_funds * 5),
            "DT_COMPTC": ["2024-01-31"] * (n_funds * 5),
        })
        cda.loc[0, "CD_ATIVO"] = "F0001"
        cda.loc[0, "CNPJ_FUNDO"] = "F0000"
        cda.loc[1, "CD_ATIVO"] = "F0000"
        cda.loc[1, "CNPJ_FUNDO"] = "F0001"

        started = time.perf_counter()
        result = FraudSchemeDetector().detect_circular_flow(
            make_sample_informe(), cda, cadastro
        )
        elapsed = time.perf_counter() - started
        assert elapsed < 2.0
        assert set(result["CNPJ_FUNDO"]) == {"F0000", "F0001"}

    def test_layered_funds_returns_dataframe(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        result = detector.detect_layered_funds(
            make_sample_cda(100), make_sample_informe(), make_sample_cadastro(50),
        )
        assert isinstance(result, pd.DataFrame)

    def test_asset_inflation_returns_dataframe(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        result = detector.detect_asset_inflation(make_sample_cda(100), make_sample_informe())
        assert isinstance(result, pd.DataFrame)

    def test_shell_network_returns_dataframe(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        result = detector.detect_shell_company_network(
            make_sample_cda(100), make_sample_cadastro(50),
        )
        assert isinstance(result, pd.DataFrame)

    def test_full_report_has_all_keys(self):
        from src.analyzers.fraud_schemes import FraudSchemeDetector
        detector = FraudSchemeDetector()
        report = detector.generate_fraud_scheme_report(
            make_sample_informe(), make_sample_cda(100), make_sample_cadastro(50),
        )
        assert "circular_flow" in report
        assert "layered_funds" in report
        assert "asset_inflation" in report
        assert "shell_networks" in report


# ---------------------------------------------------------------------------
# Peer Comparison Analyzer
# ---------------------------------------------------------------------------

class TestPeerComparisonAnalyzer:
    def test_import_and_init(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        assert analyzer is not None

    def test_load_categories(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        cadastro_df = make_sample_cadastro(50)
        analyzer.load_fund_categories(cadastro_df)
        assert len(analyzer.fund_categories) > 0

    def test_calculate_metrics(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        cadastro_df = make_sample_cadastro(50)
        informe_df = make_sample_informe()
        analyzer.load_fund_categories(cadastro_df)
        metrics = analyzer.calculate_fund_metrics(informe_df)
        assert isinstance(metrics, pd.DataFrame)
        assert len(metrics) > 0

    def test_compare_with_peers(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        cadastro_df = make_sample_cadastro(50)
        informe_df = make_sample_informe()
        analyzer.load_fund_categories(cadastro_df)
        metrics = analyzer.calculate_fund_metrics(informe_df)
        target_funds = informe_df["CNPJ_FUNDO"].unique()[:5].tolist()
        comparison = analyzer.compare_with_peers(target_funds, metrics)
        assert isinstance(comparison, pd.DataFrame)

    def test_compare_with_peers_emits_only_actual_outliers(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        metrics = pd.DataFrame({
            "CNPJ_FUNDO": ["target", "p1", "p2", "p3", "p4", "p5", "p6"],
            "category": ["MULTI"] * 7,
            "avg_return": [10.0, 0.0, 1.0, -1.0, 0.5, -0.5, 0.2],
            "volatility": [1.0] * 7,
            "sharpe_ratio": [10.0, 0.0, 1.0, -1.0, 0.5, -0.5, 0.2],
        })
        result = analyzer.compare_with_peers(["target", "p1"], metrics)
        assert result["CNPJ_FUNDO"].tolist() == ["target"]
        assert result.iloc[0]["is_outlier"] == True  # noqa: E712
        assert result.iloc[0]["fraud_flag"] == "RETURNS_TOO_HIGH"
        assert result.iloc[0]["severity"] in ("HIGH", "CRITICAL")

    def test_generate_peer_report_handles_outlier_summary(self):
        """Regression: report logging must use the comparison output schema."""
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        comparison = pd.DataFrame({
            "CNPJ_FUNDO": ["target"],
            "is_outlier": [True],
            "fraud_flag": ["RETURNS_TOO_HIGH"],
            "return_zscore": [4.2],
            "sharpe_zscore": [3.7],
        })
        analyzer.calculate_fund_metrics = lambda _frame: pd.DataFrame()
        analyzer.compare_with_peers = lambda _targets, _metrics: comparison
        analyzer.detect_smoothed_returns = lambda _frame, _targets: pd.DataFrame()

        report = analyzer.generate_peer_report(["target"], pd.DataFrame())
        assert report["peer_comparison"].equals(comparison)

    def test_detect_smoothed_returns(self):
        from src.analyzers.peer_comparison import PeerComparisonAnalyzer
        analyzer = PeerComparisonAnalyzer()
        informe_df = make_sample_informe()
        target_funds = informe_df["CNPJ_FUNDO"].unique()[:5].tolist()
        smoothed = analyzer.detect_smoothed_returns(informe_df, target_funds)
        assert isinstance(smoothed, pd.DataFrame)


# ---------------------------------------------------------------------------
# Concentration Analyzer
# ---------------------------------------------------------------------------

class TestConcentrationAnalyzer:
    def test_import_and_init(self):
        from src.analyzers.concentration import ConcentrationAnalyzer
        analyzer = ConcentrationAnalyzer()
        assert analyzer is not None

    def test_hhi_calculation(self):
        from src.analyzers.concentration import ConcentrationAnalyzer
        analyzer = ConcentrationAnalyzer()
        cda_df = make_sample_cda(100)
        portfolio = cda_df.head(10)
        hhi = analyzer.calculate_herfindahl_index(portfolio)
        assert isinstance(hhi, float)
        assert 0 <= hhi <= 1

    def test_fund_concentration_analysis(self):
        from src.analyzers.concentration import ConcentrationAnalyzer
        analyzer = ConcentrationAnalyzer()
        cda_df = make_sample_cda(100)
        fund_cnpj = cda_df["CNPJ_FUNDO"].iloc[0]
        metrics = analyzer.analyze_fund_concentration(cda_df, fund_cnpj)
        assert isinstance(metrics, dict)
        assert "hhi" in metrics
        assert "top1_pct" in metrics

    def test_excessive_concentration_detection(self):
        from src.analyzers.concentration import ConcentrationAnalyzer
        analyzer = ConcentrationAnalyzer()
        cda_df = make_sample_cda(100)
        violations = analyzer.detect_excessive_concentration(cda_df)
        assert isinstance(violations, pd.DataFrame)


# ---------------------------------------------------------------------------
# Market Data Validator
# ---------------------------------------------------------------------------

class TestMarketDataValidator:
    def test_import_and_init(self):
        from src.analyzers.market_data import MarketDataValidator
        validator = MarketDataValidator()
        assert validator is not None

    def test_cache_operations(self):
        from src.analyzers.market_data import MarketDataValidator
        validator = MarketDataValidator()
        validator._save_cache()
        assert validator.cache_dir.exists()

    @pytest.mark.integration
    def test_api_integration(self):
        from src.analyzers.market_data import MarketDataValidator
        validator = MarketDataValidator()
        from datetime import date
        price = validator.get_market_price("PETR4", date(2024, 1, 15))
        assert price is None or isinstance(price, float)
