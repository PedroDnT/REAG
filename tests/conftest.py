"""Shared test fixtures for the REAG fraud detection test suite."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from config.settings import Config
from src.processors.data_processor import DataProcessor
from src.analyzers.anomaly_detector import AnomalyDetector
from src.collectors.cvm_collector import CVMCollector


@pytest.fixture
def config():
    """Shared Config instance."""
    return Config()


@pytest.fixture
def data_processor():
    """DataProcessor instance with default config."""
    return DataProcessor()


@pytest.fixture
def anomaly_detector():
    """AnomalyDetector instance with default config."""
    return AnomalyDetector()


@pytest.fixture
def cvm_collector(tmp_path):
    """CVMCollector writing into a temp directory.

    CVMCollector._ensure_directories() runs at construction, so a default-config
    instance creates data/raw and data/processed inside the working tree just by
    existing.
    """
    config = Config()
    config.RAW_DATA_DIR = tmp_path / "raw"
    config.PROCESSED_DATA_DIR = tmp_path / "processed"
    return CVMCollector(config=config)


@pytest.fixture(autouse=True)
def no_network(request, monkeypatch):
    """Fail any unit test that reaches the network.

    Detectors are meant to work offline, and a test that silently makes a real
    request is both slow and dependent on someone else's uptime. Tests that
    genuinely need the network opt out with @pytest.mark.integration.
    """
    if request.node.get_closest_marker("integration"):
        return

    def blocked(*args, **kwargs):
        raise RuntimeError(
            "network access from a unit test; mock the call, or mark the test "
            "@pytest.mark.integration if it genuinely needs the network"
        )

    monkeypatch.setattr("requests.Session.request", blocked)
    monkeypatch.setattr("requests.api.request", blocked)

    try:
        import yfinance
    except ImportError:
        pass
    else:
        monkeypatch.setattr(yfinance, "download", blocked)


@pytest.fixture
def sample_informe_df():
    """Standard sample informe diario DataFrame (30 days, 2 funds)."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    data = []
    for fund_id in ["12345678000190", "98765432000110"]:
        for date in dates:
            data.append({
                "CNPJ_FUNDO": fund_id,
                "DT_COMPTC": date,
                "VL_QUOTA": 1.0 + np.random.normal(0, 0.01),
                "VL_PATRIM_LIQ": np.random.exponential(1_000_000),
                "CAPTC_DIA": np.random.exponential(10_000),
                "RESG_DIA": np.random.exponential(8_000),
                "NR_COTST": np.random.randint(10, 1000),
            })
    df = pd.DataFrame(data)
    df["FLUXO_LIQ_DIA"] = df["CAPTC_DIA"] - df["RESG_DIA"]
    return df


@pytest.fixture
def sample_cda_df():
    """Standard sample CDA DataFrame with mixed asset types."""
    np.random.seed(42)
    stocks = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3"]
    phantom = ["FAKE4", "GHOST3"]
    assets = stocks * 6 + phantom * 5
    n = len(assets)
    return pd.DataFrame({
        "CNPJ_FUNDO": [f"1234567800019{i % 3}" for i in range(n)],
        "CD_ATIVO": assets,
        "VL_MERCADO": np.random.uniform(100_000, 50_000_000, n),
        "QT_POS": np.random.uniform(1_000, 100_000, n),
        "DT_COMPTC": [datetime(2024, 1, 31)] * n,
        "EMISSOR": ["EMPRESA SA"] * (len(stocks) * 6)
                   + ["EMPRESA FANTASMA LTDA ME"] * (len(phantom) * 5),
    })


@pytest.fixture
def sample_cadastro_df():
    """Standard sample cadastro DataFrame."""
    return pd.DataFrame({
        "CNPJ_FUNDO": ["12345678000190", "98765432000110", "11111111000111"],
        "CNPJ_ADMIN": ["99999999000101", "99999999000101", "88888888000101"],
        "CLASSE": ["Fundo Multimercado", "Fundo de Renda Fixa", "Fundo de Acoes"],
        "DENOM_SOCIAL": ["Fund Alpha", "Fund Beta", "Fund Gamma"],
    })
