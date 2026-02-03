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

