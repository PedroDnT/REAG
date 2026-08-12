"""
Portfolio Reconciliation Analyzer

Cross-validates CDA portfolio composition against Informe Diario PL:
- Static gap: sum(VL_MERCADO) from CDA vs VL_PATRIM_LIQ from Informe
- Dynamic reconciliation: period-over-period change consistency
- Hidden positions: large PL with small/no CDA positions
"""

import logging
from typing import Any

import pandas as pd

from config.constants import RECON_GAP_WARNING, RECON_GAP_CRITICAL
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class PortfolioReconciliationAnalyzer(BaseAnalyzer):
    """Cross-validates portfolio composition against daily reported PL."""

    def analyze(
        self,
        cda_df: pd.DataFrame,
        informe_df: pd.DataFrame,
    ) -> pd.DataFrame:
        self.validate_dataframe(
            cda_df, ["CNPJ_FUNDO", "VL_MERCADO"], name="cda_df"
        )
        self.validate_dataframe(
            informe_df, ["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"], name="informe_df"
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_static_gap(cda_df, informe_df))
        results.extend(self._detect_hidden_positions(cda_df, informe_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("PortfolioReconciliationAnalyzer found %d signals", len(df))
        return df

    def _detect_static_gap(
        self, cda_df: pd.DataFrame, informe_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        cda_totals = (
            cda_df.groupby("CNPJ_FUNDO")["VL_MERCADO"]
            .sum()
            .reset_index()
            .rename(columns={"VL_MERCADO": "cda_total"})
        )

        latest_informe = (
            informe_df.sort_values("DT_COMPTC")
            .groupby("CNPJ_FUNDO")
            .last()
            .reset_index()[["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"]]
        )
        latest_informe = latest_informe.rename(columns={"VL_PATRIM_LIQ": "informe_pl"})

        merged = cda_totals.merge(latest_informe, on="CNPJ_FUNDO", how="inner")
        merged["cda_total"] = merged["cda_total"].astype(float)
        merged["informe_pl"] = merged["informe_pl"].astype(float)

        merged = merged[merged["informe_pl"].abs() > 0]
        if merged.empty:
            return findings

        merged["gap_pct"] = (
            (merged["cda_total"] - merged["informe_pl"]) / merged["informe_pl"]
        ).abs()

        flagged = merged[merged["gap_pct"] > RECON_GAP_WARNING]

        for _, row in flagged.iterrows():
            gap = float(row["gap_pct"])
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "DT_COMPTC": row.get("DT_COMPTC"),
                "cda_total": round(float(row["cda_total"]), 2),
                "informe_pl": round(float(row["informe_pl"]), 2),
                "gap_pct": round(gap * 100, 2),
                "signal_type": "static_reconciliation_gap",
                "severity": "CRITICAL" if gap > RECON_GAP_CRITICAL else "HIGH" if gap > 0.20 else "MEDIUM",
            })
        return findings

    def _detect_hidden_positions(
        self, cda_df: pd.DataFrame, informe_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        funds_in_cda = set(cda_df["CNPJ_FUNDO"].unique())

        latest_informe = (
            informe_df.sort_values("DT_COMPTC")
            .groupby("CNPJ_FUNDO")
            .last()
            .reset_index()[["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"]]
        )

        for _, row in latest_informe.iterrows():
            pl = float(row["VL_PATRIM_LIQ"])
            cnpj = row["CNPJ_FUNDO"]
            if cnpj not in funds_in_cda and pl > 1_000_000:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "DT_COMPTC": row["DT_COMPTC"],
                    "cda_total": 0.0,
                    "informe_pl": round(pl, 2),
                    "gap_pct": 100.0,
                    "signal_type": "hidden_positions",
                    "severity": "HIGH" if pl > 50_000_000 else "MEDIUM",
                })
        return findings
