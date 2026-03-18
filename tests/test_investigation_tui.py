from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scripts import investigation_tui
from scripts import run_investigation


def test_run_investigation_selected_analyses_expands_all():
    assert run_investigation._selected_analyses(["all"]) == set(run_investigation.ANALYSIS_CHOICES)


def test_run_investigation_respects_analysis_filter(tmp_path, monkeypatch):
    class StubProcessor:
        def __init__(self, config):
            self.config = config

        def calculate_net_flow(self, df):
            return df

    class StubAnomalyDetector:
        def __init__(self, config):
            self.config = config

        def generate_anomaly_report(self, informe, cda_df=None):
            return {"flow_anomalies": pd.DataFrame({"CNPJ_FUNDO": ["12345678000190"]})}

    def should_not_be_called(*args, **kwargs):
        raise AssertionError("analysis outside the requested filter should not run")

    monkeypatch.setattr(run_investigation, "DataProcessor", StubProcessor)
    monkeypatch.setattr(run_investigation, "AnomalyDetector", StubAnomalyDetector)
    monkeypatch.setattr(run_investigation, "FraudSchemeDetector", should_not_be_called)
    monkeypatch.setattr(run_investigation, "EnhancedPhantomAssetDetector", should_not_be_called)
    monkeypatch.setattr(run_investigation, "PortfolioReconciliationAnalyzer", should_not_be_called)
    monkeypatch.setattr(run_investigation, "CrossFundIssuerAnalyzer", should_not_be_called)
    monkeypatch.setattr(
        run_investigation,
        "_load_data",
        lambda **kwargs: run_investigation.LoadedData(
            cadastro=pd.DataFrame({"placeholder": [1]}),
            informe=pd.DataFrame({"CNPJ_FUNDO": ["12345678000190"], "DT_COMPTC": ["2024-01-01"]}),
            cda=pd.DataFrame({"placeholder": [1]}),
        ),
    )

    args = run_investigation.build_parser().parse_args(
        ["--analysis", "flow", "--no-explain", "--output-dir", str(tmp_path)]
    )

    exit_code = run_investigation.run_investigation(args)

    assert exit_code == 0
    assert (tmp_path / "findings" / "flow_anomalies.csv").exists()
    assert (tmp_path / "summary.json").exists()
    assert not (tmp_path / "report.html").exists()


def test_build_tui_args_collects_custom_inputs():
    responses = iter(
        [
            "2",
            "1",
            "1",
            "demo-run",
            "",
            "/tmp/raw",
            "/tmp/processed",
            "",
            "/tmp/informe_processed.csv",
            "",
            "n",
            "y",
        ]
    )

    args = investigation_tui.build_tui_args(
        input_fn=lambda _: next(responses),
        print_fn=lambda _: None,
    )

    assert args is not None
    assert args.run_id == "demo-run"
    assert args.analysis == ["flow", "quotaholder", "window_dressing", "valuation_smoothing"]
    assert args.explain is True
    assert args.explain_format == "html"
    assert args.public_data_dir == "/tmp/raw"
    assert args.processed_data_dir == "/tmp/processed"
    assert args.informe == "/tmp/informe_processed.csv"


def test_tui_main_runs_pipeline_and_prints_summary(tmp_path, monkeypatch):
    args = argparse.Namespace(
        run_id="demo-run",
        output_dir=str(tmp_path),
        public_data_dir="data/raw",
        processed_data_dir="data/processed",
        cadastro=None,
        informe=None,
        cda=None,
        explain=True,
        explain_max_entities=200,
        explain_top_findings=6,
        explain_format="both",
        analysis=["all"],
        enable_enrichment=False,
        enrichment_provider="exa",
        enrichment_since_days=365,
        enrichment_max_results=8,
    )
    outputs: list[str] = []

    def fake_build_tui_args(*, input_fn, print_fn):
        return args

    def fake_run_investigation(received_args):
        output_dir = Path(received_args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.json").write_text(
            json.dumps({"outputs": {"counts": {"flow_anomalies": 2}}}),
            encoding="utf-8",
        )
        (output_dir / "report.html").write_text("<html></html>", encoding="utf-8")
        return 0

    monkeypatch.setattr(investigation_tui, "build_tui_args", fake_build_tui_args)
    monkeypatch.setattr(investigation_tui, "run_investigation", fake_run_investigation)

    exit_code = investigation_tui.main(
        input_fn=lambda _: "",
        print_fn=outputs.append,
    )

    assert exit_code == 0
    assert any("Report:" in line for line in outputs)
    assert any("flow_anomalies: 2" in line for line in outputs)
