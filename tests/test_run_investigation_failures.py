"""A crashed analyzer must be visible, not silently absent.

run_investigation used to wrap nine analyzers in `except Exception: pass`,
which made a crashed analyzer indistinguishable from one that found nothing.
For a forensic tool that is the worst possible failure mode: the report reads
clean because the detector died.
"""

import json
import logging

import pandas as pd
import pytest

from scripts.run_investigation import (
    AnalyzerSpec,
    _analyzer_specs,
    _has,
    _parse_args,
    run_investigation,
)


@pytest.fixture
def informe_csv(tmp_path):
    """A minimal but complete informe diário CSV on disk."""
    path = tmp_path / "inf_diario_fi_202401.csv"
    dates = pd.date_range("2024-01-01", periods=12)
    frame = pd.DataFrame({
        "CNPJ_FUNDO": ["12345678000190"] * 12,
        "DT_COMPTC": dates.strftime("%Y-%m-%d"),
        "VL_QUOTA": [1.0 + i / 1000 for i in range(12)],
        "VL_PATRIM_LIQ": [1_000_000.0] * 12,
        "CAPTC_DIA": [1000.0] * 12,
        "RESG_DIA": [900.0] * 12,
        "NR_COTST": [50] * 12,
    })
    frame.to_csv(path, sep=";", index=False, encoding="latin1")
    return path


def _args(tmp_path, informe_csv, **overrides):
    argv = [
        "--informe", str(informe_csv),
        "--output-dir", str(tmp_path / "out"),
        # Point discovery at an empty directory. Without this the run picks up
        # whatever real CVM files happen to sit in data/raw, so the test's
        # result depends on the developer's working tree.
        "--public-data-dir", str(tmp_path / "empty"),
        "--processed-data-dir", str(tmp_path / "empty"),
        "--run-id", "testrun",
        "--no-explain",
    ]
    for flag, value in overrides.items():
        argv.append(f"--{flag.replace('_', '-')}")
        if value is not True:
            argv.append(str(value))
    return _parse_args(argv)


def _summary(tmp_path):
    return json.loads((tmp_path / "out" / "summary.json").read_text())


class TestFailuresAreRecorded:

    def test_failing_analyzer_is_logged(self, tmp_path, informe_csv, monkeypatch, caplog):
        def exploding_specs(config):
            return (
                AnalyzerSpec(
                    name="quotaholder",
                    is_runnable=lambda d: True,
                    run=lambda d: (_ for _ in ()).throw(RuntimeError("analyzer exploded")),
                ),
            )

        monkeypatch.setattr("scripts.run_investigation._analyzer_specs", exploding_specs)

        with caplog.at_level(logging.ERROR):
            run_investigation(_args(tmp_path, informe_csv))

        assert any("Analyzer quotaholder failed" in r.message for r in caplog.records)
        assert any(r.exc_info for r in caplog.records), "traceback must be captured"

    def test_failing_analyzer_is_recorded_in_metadata(self, tmp_path, informe_csv, monkeypatch):
        def exploding_specs(config):
            return (
                AnalyzerSpec(
                    name="quotaholder",
                    is_runnable=lambda d: True,
                    run=lambda d: (_ for _ in ()).throw(RuntimeError("boom")),
                ),
            )

        monkeypatch.setattr("scripts.run_investigation._analyzer_specs", exploding_specs)
        run_investigation(_args(tmp_path, informe_csv))

        execution = _summary(tmp_path)["execution"]
        assert execution["complete"] is False
        assert execution["failed_analyzers"] == ["quotaholder"]

    def test_incomplete_run_is_called_out_in_the_disclaimer(self, tmp_path, informe_csv, monkeypatch):
        """A reader of the report must be told coverage was incomplete."""
        monkeypatch.setattr(
            "scripts.run_investigation._analyzer_specs",
            lambda config: (
                AnalyzerSpec(
                    name="lifecycle",
                    is_runnable=lambda d: True,
                    run=lambda d: (_ for _ in ()).throw(ValueError("bad data")),
                ),
            ),
        )
        run_investigation(_args(tmp_path, informe_csv))

        disclaimer = " ".join(_summary(tmp_path)["disclaimer"])
        assert "INCOMPLETE RUN" in disclaimer
        assert "lifecycle" in disclaimer

    def test_clean_run_is_marked_complete(self, tmp_path, informe_csv):
        run_investigation(_args(tmp_path, informe_csv))

        execution = _summary(tmp_path)["execution"]
        assert execution["complete"] is True
        assert execution["failed_analyzers"] == []

    def test_skipped_analyzers_are_distinguished_from_failures(self, tmp_path, informe_csv):
        """Missing inputs is not the same as crashing, and is reported separately."""
        run_investigation(_args(tmp_path, informe_csv))

        execution = _summary(tmp_path)["execution"]
        # No CDA or cadastro was supplied, so those analyzers cannot run.
        assert "cost_basis" in execution["skipped_analyzers"]
        assert execution["failed_analyzers"] == []


class TestStrictMode:

    def test_strict_exits_non_zero_on_failure(self, tmp_path, informe_csv, monkeypatch):
        monkeypatch.setattr(
            "scripts.run_investigation._analyzer_specs",
            lambda config: (
                AnalyzerSpec(
                    name="quotaholder",
                    is_runnable=lambda d: True,
                    run=lambda d: (_ for _ in ()).throw(RuntimeError("boom")),
                ),
            ),
        )
        assert run_investigation(_args(tmp_path, informe_csv, strict=True)) == 1

    def test_without_strict_a_failure_still_exits_zero(self, tmp_path, informe_csv, monkeypatch):
        monkeypatch.setattr(
            "scripts.run_investigation._analyzer_specs",
            lambda config: (
                AnalyzerSpec(
                    name="quotaholder",
                    is_runnable=lambda d: True,
                    run=lambda d: (_ for _ in ()).throw(RuntimeError("boom")),
                ),
            ),
        )
        assert run_investigation(_args(tmp_path, informe_csv)) == 0

    def test_strict_exits_zero_on_a_clean_run(self, tmp_path, informe_csv):
        assert run_investigation(_args(tmp_path, informe_csv, strict=True)) == 0


class TestAnalyzerSpecTable:
    """The declarative table must cover the analyzers it replaced."""

    def test_covers_every_optional_analysis_choice(self):
        from config.settings import Config
        from scripts.run_investigation import ANALYSIS_CHOICES

        declared = {spec.name for spec in _analyzer_specs(Config())}
        # flow, schemes and phantom_assets keep bespoke blocks; the rest are declarative.
        core = {"flow", "schemes", "phantom_assets"}
        assert declared == set(ANALYSIS_CHOICES) - core

    def test_spec_names_are_unique(self):
        from config.settings import Config

        names = [spec.name for spec in _analyzer_specs(Config())]
        assert len(names) == len(set(names))


class TestHasHelper:

    def test_none_and_empty_are_not_runnable(self):
        assert _has(None) is False
        assert _has(pd.DataFrame()) is False

    def test_requires_every_named_column(self):
        frame = pd.DataFrame({"A": [1], "B": [2]})
        assert _has(frame, "A") is True
        assert _has(frame, "A", "B") is True
        assert _has(frame, "A", "C") is False
