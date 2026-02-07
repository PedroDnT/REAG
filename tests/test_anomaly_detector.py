"""Tests for the AnomalyDetector module."""

import pytest
import pandas as pd
import numpy as np
from src.analyzers.anomaly_detector import AnomalyDetector


@pytest.fixture
def detector():
    return AnomalyDetector()


def test_detector_initialization(detector):
    assert detector is not None
    assert detector.config is not None


def test_z_score_calculation(detector):
    data = pd.Series([1, 2, 3, 4, 5, 100])
    z_scores = detector.calculate_z_scores(data)
    assert len(z_scores) == len(data)
    assert abs(z_scores.iloc[-1]) > 2  # 100 should have a high z-score


def test_z_score_constant_series(detector):
    """Z-scores of a constant series should be NaN (std=0)."""
    data = pd.Series([5, 5, 5, 5])
    z_scores = detector.calculate_z_scores(data)
    assert z_scores.isna().all()


def test_detect_flow_anomalies(detector):
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["12345678000190"] * 10,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=10),
        "FLUXO_LIQ_DIA": [100, 120, 110, 105, 115, 1000, 100, 105, 110, 120],
    })
    anomalies = detector.detect_flow_anomalies(df, threshold=2.5)
    assert not anomalies.empty
    assert anomalies.iloc[0]["FLUXO_LIQ_DIA"] == 1000


def test_detect_flow_anomalies_missing_column(detector):
    """Should return empty DataFrame if flow column missing."""
    df = pd.DataFrame({"OTHER": [1, 2, 3]})
    result = detector.detect_flow_anomalies(df)
    assert result.empty


def test_detect_flow_anomalies_no_fund_column(detector):
    """Should still work without CNPJ_FUNDO column (global z-score)."""
    df = pd.DataFrame({
        "FLUXO_LIQ_DIA": [100, 120, 110, 105, 115, 1000, 100, 105, 110, 120],
    })
    anomalies = detector.detect_flow_anomalies(df, threshold=2.5)
    assert not anomalies.empty


def test_detect_pl_drops(detector):
    """Should detect significant PL drops."""
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 5,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=5),
        "VL_PATRIM_LIQ": [1_000_000, 1_000_000, 1_000_000, 500_000, 500_000],
    })
    drops = detector.detect_pl_drops(df, threshold_pct=20.0)
    assert not drops.empty
    assert drops.iloc[0]["PL_VAR_PCT"] < -20


def test_detect_pl_drops_missing_columns(detector):
    """Should return empty DataFrame if required columns missing."""
    df = pd.DataFrame({"OTHER": [1, 2, 3]})
    result = detector.detect_pl_drops(df)
    assert result.empty


def test_detect_runs(detector):
    """Should detect consecutive negative flow runs."""
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 8,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=8),
        "FLUXO_LIQ_DIA": [-10, -20, -30, -40, -50, -60, 100, -10],
    })
    runs = detector.detect_runs(df, consecutive_days=5)
    assert not runs.empty


def test_detect_runs_no_runs(detector):
    """Should return empty when no runs present."""
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 5,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=5),
        "FLUXO_LIQ_DIA": [100, -10, 100, -10, 100],
    })
    runs = detector.detect_runs(df, consecutive_days=3)
    assert runs.empty


def test_detect_divergence_flow_performance(detector):
    """Should detect flow-performance divergence."""
    np.random.seed(42)
    n = 20
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * n,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=n),
        "VL_QUOTA": [1.0 + 0.001 * i for i in range(n)],
        "FLUXO_LIQ_DIA": [100] * (n - 1) + [-100_000],
    })
    divergences = detector.detect_divergence_flow_performance(df)
    assert isinstance(divergences, pd.DataFrame)


def test_detect_divergence_missing_columns(detector):
    """Should return empty DataFrame if required columns missing."""
    df = pd.DataFrame({"OTHER": [1, 2, 3]})
    result = detector.detect_divergence_flow_performance(df)
    assert result.empty


def test_generate_anomaly_report(detector):
    """generate_anomaly_report should return a dict with expected keys."""
    np.random.seed(42)
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 20,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=20),
        "VL_QUOTA": [1.0 + 0.001 * i for i in range(20)],
        "VL_PATRIM_LIQ": [1_000_000] * 20,
        "FLUXO_LIQ_DIA": [100] * 19 + [100_000],
    })
    report = detector.generate_anomaly_report(df)
    assert isinstance(report, dict)
    assert "flow_anomalies" in report
    assert "pl_drops" in report
    assert "runs" in report
    assert "divergences" in report
    for key, value in report.items():
        assert isinstance(value, pd.DataFrame)


def test_generate_anomaly_report_with_cda(detector):
    """generate_anomaly_report with CDA data should include concentration_spikes."""
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 10,
        "DT_COMPTC": pd.date_range("2024-01-01", periods=10),
        "VL_QUOTA": [1.0] * 10,
        "VL_PATRIM_LIQ": [1_000_000] * 10,
        "FLUXO_LIQ_DIA": [100] * 10,
    })
    cda_df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1"] * 3,
        "DT_COMPTC": pd.to_datetime(["2024-01-01"] * 3),
        "VL_MERC_POS_FINAL": [500_000, 300_000, 200_000],
        "CD_ATIVO": ["A1", "A2", "A3"],
    })
    report = detector.generate_anomaly_report(df, cda_df=cda_df)
    assert "concentration_spikes" in report
