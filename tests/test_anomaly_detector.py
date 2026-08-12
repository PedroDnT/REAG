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


# ---------------------------------------------------------------------------
# Regression tests for audit fixes
# ---------------------------------------------------------------------------


class TestMissingFundColumn:
    """detect_pl_drops / detect_runs used to raise KeyError without CNPJ_FUNDO.

    detect_flow_anomalies has always handled that case by treating the frame as
    a single series; its two siblings went straight to groupby('CNPJ_FUNDO').
    """

    def test_detect_pl_drops_without_fund_column(self, detector):
        df = pd.DataFrame({
            "DT_COMPTC": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "VL_PATRIM_LIQ": [100.0, 50.0],
        })
        result = detector.detect_pl_drops(df)
        assert len(result) == 1
        assert result["PL_VAR_PCT"].iloc[0] == pytest.approx(-50.0)

    def test_detect_runs_without_fund_column(self, detector):
        df = pd.DataFrame({
            "DT_COMPTC": pd.date_range("2024-01-01", periods=8),
            "FLUXO_LIQ_DIA": [-1.0] * 8,
        })
        result = detector.detect_runs(df, consecutive_days=5)
        # Days 5..8 of the run qualify.
        assert len(result) == 4

    def test_detect_runs_without_fund_column_resets_on_positive_flow(self, detector):
        df = pd.DataFrame({
            "DT_COMPTC": pd.date_range("2024-01-01", periods=8),
            "FLUXO_LIQ_DIA": [-1.0, -1.0, 5.0, -1.0, -1.0, -1.0, -1.0, -1.0],
        })
        # Longest negative streak after the reset is 5 days, so only its last day
        # reaches RUN_LENGTH >= 5.
        assert len(detector.detect_runs(df, consecutive_days=5)) == 1

    def test_flow_anomalies_still_handles_missing_column(self, detector):
        """The sibling that always worked must keep working."""
        df = pd.DataFrame({"FLUXO_LIQ_DIA": [1.0] * 19 + [500.0]})
        assert isinstance(detector.detect_flow_anomalies(df), pd.DataFrame)


class TestReportUsesCorrectConstants:
    """generate_anomaly_report passed FLOW_WINDOW_DAYS as a run length."""

    def test_runs_use_redemption_run_days_not_flow_window(self, detector):
        from config.constants import REDEMPTION_RUN_DAYS

        # A 6-day redemption streak shedding 5% of net assets a day: caught at
        # the intended 5-day threshold, missed at the 10-day FLOW_WINDOW_DAYS
        # value that was wired in before.
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["F1"] * 6,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=6),
            "VL_QUOTA": [1.0] * 6,
            "VL_PATRIM_LIQ": [1_000_000.0] * 6,
            "FLUXO_LIQ_DIA": [-50_000.0] * 6,
        })
        assert REDEMPTION_RUN_DAYS == 5
        assert len(detector.generate_anomaly_report(df)["runs"]) > 0


class TestRunMagnitudeGate:
    """A run must be material, not merely long.

    Counting consecutive negative days alone flagged 75% of funds in a synthetic
    universe containing no fraud: net flow crosses zero constantly, so long
    negative streaks arise by chance. See evals/ and REDEMPTION_RUN_MIN_PCT.
    """

    @staticmethod
    def _run(daily_outflow, assets=1_000_000.0, days=8):
        return pd.DataFrame({
            "CNPJ_FUNDO": ["F1"] * days,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=days),
            "VL_PATRIM_LIQ": [assets] * days,
            "FLUXO_LIQ_DIA": [-daily_outflow] * days,
        })

    def test_trivial_outflows_are_not_a_run(self, detector):
        """Eight days of losing 0.01% a day is not a redemption run."""
        assert detector.detect_runs(self._run(100.0)).empty

    def test_material_outflows_are_a_run(self, detector):
        """Eight days of losing 5% a day is."""
        assert not detector.detect_runs(self._run(50_000.0)).empty

    def test_gate_is_measured_over_the_whole_run_not_one_day(self, detector):
        """No single day clears 10%, but the run cumulatively sheds 16%."""
        result = detector.detect_runs(self._run(20_000.0), min_pct_of_assets=10.0)
        assert not result.empty

    def test_gate_can_be_disabled(self, detector):
        assert not detector.detect_runs(self._run(100.0), min_pct_of_assets=0).empty

    def test_duration_is_still_required(self, detector):
        """A single enormous outflow is a PL event, not a run."""
        df = self._run(500_000.0, days=8)
        df.loc[df.index[1:], "FLUXO_LIQ_DIA"] = 1000.0  # only day 0 is negative
        assert detector.detect_runs(df).empty

    def test_missing_pl_column_warns_and_skips_the_gate(self, detector, caplog):
        import logging

        df = self._run(100.0).drop(columns=["VL_PATRIM_LIQ"])
        with caplog.at_level(logging.WARNING):
            result = detector.detect_runs(df)

        assert not result.empty, "without PL the gate cannot apply"
        assert any("VL_PATRIM_LIQ" in r.message for r in caplog.records)

    def test_gate_applies_per_fund(self, detector):
        """One fund's material run must not qualify another's trivial one."""
        big = self._run(50_000.0)
        small = self._run(100.0)
        small["CNPJ_FUNDO"] = "F2"

        result = detector.detect_runs(pd.concat([big, small], ignore_index=True))

        assert set(result["CNPJ_FUNDO"]) == {"F1"}

    def test_pl_drops_use_pl_drop_critical(self, detector, monkeypatch):
        """The threshold must come from the constant, not a hardcoded 20.0."""
        import src.analyzers.anomaly_detector as module

        monkeypatch.setattr(module, "PL_DROP_CRITICAL", 60.0)
        df = pd.DataFrame({
            "CNPJ_FUNDO": ["F1"] * 3,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=3),
            "VL_QUOTA": [1.0] * 3,
            "VL_PATRIM_LIQ": [1_000_000.0, 700_000.0, 690_000.0],  # -30% then -1.4%
            "FLUXO_LIQ_DIA": [0.0] * 3,
        })
        # A 30% drop is below the patched 60% threshold, so raising the constant
        # must suppress it. With the old literal it would still be reported.
        assert len(detector.generate_anomaly_report(df)["pl_drops"]) == 0


class TestDivergenceThreshold:
    """DIVERGENCE_SCORE is a product of Z-scores (unit z^2), not a Z-score."""

    def test_threshold_default_is_the_product_constant(self, detector):
        import inspect

        from config.constants import DIVERGENCE_SCORE_THRESHOLD

        sig = inspect.signature(detector.detect_divergence_flow_performance)
        assert sig.parameters["threshold"].default == DIVERGENCE_SCORE_THRESHOLD
        assert DIVERGENCE_SCORE_THRESHOLD == 4.0

    @pytest.fixture
    def divergent_df(self):
        """Fund data containing divergence scores on both sides of 2.0 and 4.0."""
        n = 60
        rng = np.random.default_rng(0)
        flow = rng.normal(0, 1, n)
        ret = rng.normal(0, 1, n)
        flow[10], ret[10] = 1.6, -1.6   # mild opposite pair, score ~2.5
        flow[20], ret[20] = 3.5, -3.5   # strong opposite pair, score well past 4
        return pd.DataFrame({
            "CNPJ_FUNDO": ["F1"] * n,
            "DT_COMPTC": pd.date_range("2024-01-01", periods=n),
            "VL_QUOTA": 1.0 + np.cumsum(ret) / 1000,
            "FLUXO_LIQ_DIA": flow,
        })

    def test_scores_between_2_and_4_are_excluded(self, detector, divergent_df):
        """Rows the old z-score cutoff admitted are now correctly excluded."""
        lenient = detector.detect_divergence_flow_performance(divergent_df, threshold=2.0)
        strict = detector.detect_divergence_flow_performance(divergent_df, threshold=4.0)

        borderline = lenient[
            (lenient["DIVERGENCE_SCORE"] > 2.0) & (lenient["DIVERGENCE_SCORE"] <= 4.0)
        ]
        assert not borderline.empty, "fixture must contain borderline rows to be meaningful"
        assert len(strict) < len(lenient)
        assert (strict["DIVERGENCE_SCORE"] > 4.0).all()

    def test_strong_opposite_move_survives_the_stricter_threshold(self, detector, divergent_df):
        result = detector.detect_divergence_flow_performance(divergent_df)
        assert not result.empty
        assert result["DIVERGENCE_SCORE"].max() > 4.0


class TestConcentrationNaming:
    """detect_concentration_spikes never detected a spike; it measured a level."""

    @pytest.fixture
    def cda_df(self):
        return pd.DataFrame({
            "CNPJ_FUNDO": ["F1"] * 3,
            "DT_COMPTC": pd.to_datetime(["2024-01-01"] * 3),
            "VL_MERC_POS_FINAL": [800_000, 150_000, 50_000],
            "CD_ATIVO": ["A1", "A2", "A3"],
        })

    def test_detect_high_concentration_flags_dominant_asset(self, detector, cda_df):
        result = detector.detect_high_concentration(cda_df)
        assert len(result) == 1
        assert result["CD_ATIVO"].iloc[0] == "A1"
        assert result["PCT_CARTEIRA"].iloc[0] == pytest.approx(80.0)

    def test_old_name_still_works_and_agrees(self, detector, cda_df):
        pd.testing.assert_frame_equal(
            detector.detect_concentration_spikes(cda_df),
            detector.detect_high_concentration(cda_df),
        )
