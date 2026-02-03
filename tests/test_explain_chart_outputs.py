from pathlib import Path

import pandas as pd

from src.explain.charts import render_fund_timeseries_charts


def test_render_fund_timeseries_charts_writes_files(tmp_path: Path):
    informe_df = pd.DataFrame(
        {
            "CNPJ_FUNDO": ["12345678000190"] * 3,
            "DT_COMPTC": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "FLUXO_LIQ_DIA": [100.0, -50.0, 25.0],
            "VL_PATRIM_LIQ": [1_000_000.0, 990_000.0, 995_000.0],
            "VL_QUOTA": [1.0, 0.99, 1.01],
        }
    )

    outputs = render_fund_timeseries_charts(
        informe_df=informe_df,
        fund_cnpj="12345678000190",
        output_dir=tmp_path,
        prefix="FUND_12345678000190",
    )

    assert outputs.flow_png is not None
    assert outputs.pl_png is not None
    assert outputs.quota_png is not None
    assert (tmp_path / outputs.flow_png).exists()
    assert (tmp_path / outputs.pl_png).exists()
    assert (tmp_path / outputs.quota_png).exists()

