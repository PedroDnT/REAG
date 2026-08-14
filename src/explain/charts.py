from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


@dataclass(frozen=True)
class FundChartOutputs:
    flow_png: str | None
    pl_png: str | None
    quota_png: str | None


def _safe_filename(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)


def render_fund_timeseries_charts(
    *,
    informe_df: pd.DataFrame,
    fund_cnpj: str,
    output_dir: Path,
    prefix: str,
) -> FundChartOutputs:
    """
    Render small, readable time series charts for a fund.

    This is best-effort: it will produce only the charts for which the
    required columns exist.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = informe_df.copy()
    if "CNPJ_FUNDO" not in df.columns or "DT_COMPTC" not in df.columns:
        return FundChartOutputs(flow_png=None, pl_png=None, quota_png=None)

    df = df[df["CNPJ_FUNDO"].astype(str) == str(fund_cnpj)].copy()
    if df.empty:
        return FundChartOutputs(flow_png=None, pl_png=None, quota_png=None)

    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
    df = df.dropna(subset=["DT_COMPTC"]).sort_values("DT_COMPTC")

    safe_prefix = _safe_filename(prefix)

    flow_png = None
    if "FLUXO_LIQ_DIA" in df.columns:
        path = output_dir / f"{safe_prefix}_flow.png"
        _plot_series(
            df=df,
            x="DT_COMPTC",
            y="FLUXO_LIQ_DIA",
            title="Net flow (daily)",
            ylabel="BRL",
            output_path=path,
        )
        flow_png = path.name

    pl_png = None
    if "VL_PATRIM_LIQ" in df.columns:
        path = output_dir / f"{safe_prefix}_pl.png"
        _plot_series(
            df=df,
            x="DT_COMPTC",
            y="VL_PATRIM_LIQ",
            title="AUM/PL (reported)",
            ylabel="BRL",
            output_path=path,
        )
        pl_png = path.name

    quota_png = None
    if "VL_QUOTA" in df.columns:
        path = output_dir / f"{safe_prefix}_quota.png"
        _plot_series(
            df=df,
            x="DT_COMPTC",
            y="VL_QUOTA",
            title="Quota value",
            ylabel="Value",
            output_path=path,
        )
        quota_png = path.name

    return FundChartOutputs(flow_png=flow_png, pl_png=pl_png, quota_png=quota_png)


def _plot_series(*, df: pd.DataFrame, x: str, y: str, title: str, ylabel: str, output_path: Path) -> None:
    plt.figure(figsize=(10, 3.8))
    plt.plot(df[x], df[y], linewidth=1.2)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def write_mermaid_diagram(*, mermaid_source: str, output_path: Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(mermaid_source, encoding="utf-8")
    return output_path.name


def build_circular_flow_mermaid(row: dict[str, Any]) -> str:
    """
    Best-effort mermaid diagram for a circular-flow record.
    """
    admin = str(row.get("admin_cnpj", "")).strip() or "ADMIN"
    fund = str(row.get("CNPJ_FUNDO", "")).strip() or "FUND"
    counterparty = str(row.get("counterparty_cnpj", "")).strip()

    lines = ["flowchart LR", f'  A["Administrator {admin}"] --> F["Fund {fund}"]']
    if counterparty:
        lines.append(f'  F --> C["Fund {counterparty}"]')
        lines.append("  C --> F")
    return "\n".join(lines) + "\n"
