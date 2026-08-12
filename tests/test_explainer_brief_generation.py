from pathlib import Path

import pandas as pd

from src.explain.explainer import Explainer


def test_explainer_generates_briefs_and_evidence(tmp_path: Path):
    # Minimal cadastro for metadata
    cadastro_df = pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12.345.678/0001-90"],
            "DENOM_SOCIAL": ["Example Fund"],
            "CNPJ_ADMIN": ["99.999.999/0001-01"],
        }
    )

    # Minimal informe for charts
    informe_df = pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12345678000190"] * 3,
            "DT_COMPTC": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "FLUXO_LIQ_DIA": [100.0, -50.0, 25.0],
            "VL_PATRIM_LIQ": [1_000_000.0, 990_000.0, 995_000.0],
            "VL_QUOTA": [1.0, 0.99, 1.01],
        }
    )

    results = {
        "flow_anomalies": pd.DataFrame(
            {
                "CNPJ_FUNDO": ["12.345.678/0001-90"],
                "DT_COMPTC": ["2024-01-02"],
                "FLUXO_LIQ_DIA": [-500000.0],
                "Z_SCORE_FLOW": [5.2],
            }
        ),
        "circular_flow": pd.DataFrame(
            {
                "admin_cnpj": ["99.999.999/0001-01"],
                "fund_as_asset": ["12.345.678/0001-90"],
                "held_by_funds": [["11.111.111/0001-11"]],
                "num_circular_connections": [1],
                "total_value": [12_000_000.0],
                "severity": ["CRITICAL"],
                "banco_master_similarity": ["HIGH"],
            }
        ),
    }
    sources = {"flow_anomalies": "findings/flow_anomalies.csv", "circular_flow": "findings/circular_flow.csv"}

    explainer = Explainer()
    summary_df = explainer.generate(
        results=results,
        output_dir=tmp_path,
        informe_df=informe_df,
        cadastro_df=cadastro_df,
        sources=sources,
        explain_max_entities=10,
        explain_top_findings=6,
        explain_format="both",
    )

    assert not summary_df.empty
    assert (tmp_path / "report.html").exists()

    fund_dir = tmp_path / "entities" / "FUND_12345678000190"
    assert (fund_dir / "brief.md").exists()
    assert (fund_dir / "brief.html").exists()
    assert (fund_dir / "evidence.json").exists()



class TestMetricSelection:
    """A brief must name a metric the finding actually carries.

    Several analyzers write more than one signal type into one findings table,
    each populating its own metric column. Naming a fixed column labelled 33 of
    one real CVM month's brief lines "autocorrelation: nan".
    """

    def test_falls_back_to_the_column_the_row_populated(self):
        from src.explain.explainer import _describe_metric

        row = {"autocorrelation": float("nan"), "vol_ratio": 0.0136, "stale_days": None}
        assert _describe_metric(row, ("autocorrelation", "vol_ratio", "stale_days")) == (
            "vol_ratio: 0.0136"
        )

    def test_reports_n_a_rather_than_nan_when_nothing_is_populated(self):
        from src.explain.explainer import _describe_metric

        assert _describe_metric({"gap_pct": None}, "gap_pct") == "gap_pct: n/a"
        assert _describe_metric({}, ("a", "b")) == "a: n/a"

    def test_a_plain_string_column_still_works(self):
        from src.explain.explainer import _describe_metric

        assert _describe_metric({"gap_pct": 12.5}, "gap_pct") == "gap_pct: 12.5"

    def test_float_precision_is_trimmed_for_a_human_reader(self):
        from src.explain.explainer import _format_metric_value

        assert _format_metric_value(75.09326146714412) == "75.09"
        assert _format_metric_value(3.1172363353256385) == "3.117"
        assert _format_metric_value(0.1831111111111111) == "0.1831"
        assert _format_metric_value(-100.0) == "-100"

    def test_large_numbers_keep_their_magnitude_and_stay_sortable(self):
        from src.explain.explainer import _format_metric_value, _metric_sort_value

        rendered = _format_metric_value(1_234_567_890.125)
        assert rendered == "1234567890.12"
        # No thousands separators: _metric_sort_value splits on commas, so a
        # grouped number would sort by its last three digits.
        assert _metric_sort_value(f"max_pl: {rendered}") == 1_234_567_890.12

    def test_non_numeric_metrics_pass_through(self):
        from src.explain.explainer import _format_metric_value

        assert _format_metric_value("OVERVALUATION") == "OVERVALUATION"
        assert _format_metric_value(True) == "True"
