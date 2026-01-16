import pytest
import pandas as pd
import numpy as np
from src.analyzers.anomaly_detector import AnomalyDetector


def test_detector_initialization():
    detector = AnomalyDetector()
    assert detector is not None


def test_z_score_calculation():
    detector = AnomalyDetector()
    data = pd.Series([1, 2, 3, 4, 5, 100])  # 100 é outlier

    z_scores = detector.calculate_z_scores(data)

    assert len(z_scores) == len(data)
    assert abs(z_scores.iloc[-1]) > 2  # 100 deve ter z-score alto


def test_detect_flow_anomalies():
    detector = AnomalyDetector()
    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90'] * 10,
        'DT_COMPTC': pd.date_range('2024-01-01', periods=10),
        'FLUXO_LIQ_DIA': [100, 120, 110, 105, 115, 1000, 100, 105, 110, 120]  # dia 6 anômalo
    })

    anomalies = detector.detect_flow_anomalies(df, threshold=2.5)

    assert not anomalies.empty
    assert anomalies.iloc[0]['FLUXO_LIQ_DIA'] == 1000
