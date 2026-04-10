from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pytest

from config.settings import Config
from scripts import investigation_tui
from scripts import run_investigation
from scripts.run_investigation import sanitize_run_id
from src.processors.data_processor import DataProcessor


# ---------------------------------------------------------------------------
# sanitize_run_id
# ---------------------------------------------------------------------------

class TestSanitizeRunId:
    @pytest.mark.parametrize("valid_id", [
        "abc",
        "ABC",
        "run-1",
        "run_1",
        "A0",
        "a" * 64,
        "20240101_120000",
    ])
    def test_valid_ids_pass_through(self, valid_id):
        assert sanitize_run_id(valid_id) == valid_id

    @pytest.mark.parametrize("invalid_id", [
        "/tmp/x",           # absolute path
        "../x",             # traversal
        "../../etc/passwd", # traversal
        "run/sub",          # separator
        "run id",           # space
        "",                 # empty
        "a" * 65,           # too long
        "-start",           # must start with alnum
        "_start",           # must start with alnum
    ])
    def test_invalid_ids_return_timestamp_fallback(self, invalid_id):
        result = sanitize_run_id(invalid_id)
        # Must not equal the invalid input
        assert result != invalid_id
        # Fallback must itself be a valid run_id
        assert sanitize_run_id(result) == result


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
            return {"flow_anomalies": informe[["CNPJ_FUNDO"]].drop_duplicates().reset_index(drop=True)}

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
            informe=pd.DataFrame(
                {
                    "CNPJ_FUNDO": ["12345678000190", "99999999000199"],
                    "DT_COMPTC": ["2024-01-01", "2024-01-01"],
                }
            ),
            cda=pd.DataFrame({"placeholder": [1]}),
        ),
    )

    args = run_investigation.build_parser().parse_args(
        ["--analysis", "flow", "--no-explain", "--output-dir", str(tmp_path)]
    )
    args.selected_cnpjs = ["12345678000190"]

    exit_code = run_investigation.run_investigation(args)

    assert exit_code == 0
    assert (tmp_path / "findings" / "flow_anomalies.csv").exists()
    assert (tmp_path / "summary.json").exists()
    assert not (tmp_path / "report.html").exists()
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["scope"]["fund_filter_enabled"] is True
    assert summary["scope"]["selected_funds_count"] == 1


def test_load_data_filters_selected_funds(tmp_path):
    cadastro_path = tmp_path / "cad_fi_test.csv"
    informe_path = tmp_path / "inf_diario_fi_test.csv"
    cda_path = tmp_path / "cda_fi_test.csv"

    pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12345678000190", "99999999000199"],
            "DENOM_SOCIAL": ["Fundo A", "Fundo B"],
        }
    ).to_csv(cadastro_path, sep=";", index=False)
    pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12345678000190", "99999999000199"],
            "DT_COMPTC": ["2024-01-01", "2024-01-01"],
            "VL_TOTAL": [1.0, 1.0],
            "VL_QUOTA": [1.0, 1.0],
            "VL_PATRIM_LIQ": [1.0, 1.0],
            "CAPTC_DIA": [1.0, 1.0],
            "RESG_DIA": [1.0, 1.0],
            "NR_COTST": [1.0, 1.0],
        }
    ).to_csv(informe_path, sep=";", index=False)
    pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12345678000190", "99999999000199"],
            "DT_COMPTC": ["2024-01-01", "2024-01-01"],
            "VL_MERC_POS_FINAL": [1.0, 1.0],
            "QT_POS_FINAL": [1.0, 1.0],
            "VL_CUSTO_POS_FINAL": [1.0, 1.0],
        }
    ).to_csv(cda_path, sep=";", index=False)

    args = argparse.Namespace(
        cadastro=str(cadastro_path),
        informe=str(informe_path),
        cda=str(cda_path),
        public_data_dir=str(tmp_path),
        processed_data_dir=str(tmp_path),
        selected_cnpjs=["12345678000190"],
    )
    loaded = run_investigation._load_data(
        args=args,
        config=Config(),
        processor=DataProcessor(Config()),
    )

    assert loaded.cadastro is not None
    assert loaded.informe is not None
    assert loaded.cda is not None
    assert loaded.cadastro["CNPJ_FUNDO"].tolist() == ["12345678000190"]
    assert loaded.informe["CNPJ_FUNDO"].tolist() == ["12345678000190"]
    assert loaded.cda["CNPJ_FUNDO"].tolist() == ["12345678000190"]


def test_build_tui_args_collects_custom_inputs():
    responses = iter(
        [
            "2",
            "1",
            "demo-run",
            "",
            "/tmp/raw",
            "/tmp/processed",
            "",
            "/tmp/informe_processed.csv",
            "",
            "1",
            "n",
            "y",
            "1",
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


def test_build_tui_args_collects_selected_funds(monkeypatch):
    monkeypatch.setattr(
        investigation_tui,
        "_load_fund_catalog",
        lambda **kwargs: [
            ("12345678000190", "Fundo Alpha"),
            ("98765432000110", "Fundo Beta"),
        ],
    )
    responses = iter(
        [
            "1",
            "1",
            "demo-run",
            "",
            "2",
            "",
            "1,2",
            "done",
            "n",
            "y",
            "3",
            "y",
        ]
    )
    args = investigation_tui.build_tui_args(
        input_fn=lambda _: next(responses),
        print_fn=lambda _: None,
    )

    assert args is not None
    assert args.selected_cnpjs == ["12345678000190", "98765432000110"]
    assert args.explain is True
    assert args.explain_format == "both"


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


def test_build_tui_args_warns_on_invalid_run_id():
    """TUI should emit a warning and substitute a safe run_id when the user enters an invalid one."""
    responses = iter(["1", "1", "../bad-id", "", "1", "n", "y", "1", "y"])
    warnings: list[str] = []

    args = investigation_tui.build_tui_args(
        input_fn=lambda _: next(responses),
        print_fn=warnings.append,
    )

    assert args is not None
    # The stored run_id must not contain the traversal component
    assert args.run_id != "../bad-id"
    # A warning must have been emitted
    assert any("[warning]" in w for w in warnings)
