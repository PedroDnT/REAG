"""
Fund Lifecycle Analyzer

Detects fraud signals from fund constitution/cancellation patterns:
- Hot start: funds reaching large PL very quickly after constitution
- Short-lived funds: created and canceled within a short period
- Coordinated creation: multiple funds under same admin created in a narrow window
- Suspicious inflow timing: large inflows starting immediately after fund creation
"""

import logging
from typing import Any

import pandas as pd

from config.constants import (
    HOT_START_DAYS,
    HOT_START_PL_MIN,
    SHORT_LIVED_DAYS,
    COORDINATED_CREATION_WINDOW,
)
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class FundLifecycleAnalyzer(BaseAnalyzer):
    """Analyzes fund lifecycle patterns for fraud signals."""

    def analyze(
        self,
        cadastro_df: pd.DataFrame,
        informe_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        self.validate_dataframe(
            cadastro_df, ["CNPJ_FUNDO", "DT_CONST"], name="cadastro_df"
        )

        results: list[dict[str, Any]] = []

        if "DT_CANCEL" in cadastro_df.columns:
            results.extend(self._detect_short_lived(cadastro_df))

        if "CNPJ_ADMIN" in cadastro_df.columns:
            results.extend(self._detect_coordinated_creation(cadastro_df))

        if informe_df is not None:
            self.validate_dataframe(
                informe_df,
                ["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"],
                name="informe_df",
            )
            results.extend(self._detect_hot_start(cadastro_df, informe_df))
            if "CAPTC_DIA" in informe_df.columns:
                results.extend(self._detect_suspicious_inflow(cadastro_df, informe_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("FundLifecycleAnalyzer found %d signals", len(df))
        return df

    def _detect_hot_start(
        self, cadastro_df: pd.DataFrame, informe_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        cad = cadastro_df[["CNPJ_FUNDO", "DT_CONST"]].dropna(subset=["DT_CONST"]).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST"]).drop_duplicates("CNPJ_FUNDO")
        if cad.empty:
            return []

        # Merge once instead of filtering the full informe per fund (O(funds x rows)).
        inf = informe_df[["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"]].copy()
        inf["DT_COMPTC"] = pd.to_datetime(inf["DT_COMPTC"], errors="coerce")
        inf["VL_PATRIM_LIQ"] = pd.to_numeric(inf["VL_PATRIM_LIQ"], errors="coerce")
        inf = inf.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"])

        merged = inf.merge(cad, on="CNPJ_FUNDO", how="inner")
        if merged.empty:
            return []

        early = merged[
            (merged["DT_COMPTC"] >= merged["DT_CONST"])
            & (
                merged["DT_COMPTC"]
                <= merged["DT_CONST"] + pd.Timedelta(days=HOT_START_DAYS)
            )
        ]
        if early.empty:
            return []

        max_pl = (
            early.groupby("CNPJ_FUNDO", sort=False)
            .agg(max_pl=("VL_PATRIM_LIQ", "max"), DT_CONST=("DT_CONST", "first"))
        )
        flagged = max_pl[max_pl["max_pl"] >= HOT_START_PL_MIN]
        findings: list[dict[str, Any]] = []
        for cnpj, row in flagged.iterrows():
            max_pl_value = float(row["max_pl"])
            findings.append({
                "CNPJ_FUNDO": cnpj,
                "signal_type": "hot_start",
                "DT_CONST": str(pd.Timestamp(row["DT_CONST"]).date()),
                "DT_CANCEL": None,
                "days_active": None,
                "max_pl": round(max_pl_value, 2),
                "severity": (
                    "CRITICAL" if max_pl_value >= HOT_START_PL_MIN * 5 else "HIGH"
                ),
            })
        return findings

    def _detect_short_lived(self, cadastro_df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        cad = cadastro_df[["CNPJ_FUNDO", "DT_CONST", "DT_CANCEL"]].dropna(
            subset=["DT_CONST", "DT_CANCEL"]
        ).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad["DT_CANCEL"] = pd.to_datetime(cad["DT_CANCEL"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST", "DT_CANCEL"])

        cad["days_active"] = (cad["DT_CANCEL"] - cad["DT_CONST"]).dt.days

        short = cad[
            (cad["days_active"] > 0) & (cad["days_active"] <= SHORT_LIVED_DAYS)
        ]

        for _, row in short.iterrows():
            days = int(row["days_active"])
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "signal_type": "short_lived_fund",
                "DT_CONST": str(row["DT_CONST"].date()),
                "DT_CANCEL": str(row["DT_CANCEL"].date()),
                "days_active": days,
                "max_pl": None,
                "severity": "HIGH" if days <= 90 else "MEDIUM",
            })
        return findings

    def _detect_coordinated_creation(self, cadastro_df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        cad = cadastro_df[["CNPJ_FUNDO", "CNPJ_ADMIN", "DT_CONST"]].dropna(
            subset=["DT_CONST", "CNPJ_ADMIN"]
        ).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST"])

        window = pd.Timedelta(days=COORDINATED_CREATION_WINDOW)
        for admin, group in cad.groupby("CNPJ_ADMIN"):
            if len(group) < 3:
                continue
            dates = group["DT_CONST"].sort_values().reset_index(drop=True)
            # Sliding window over sorted constitution dates: O(n) per admin.
            left = 0
            for right in range(len(dates)):
                while dates.iloc[right] - dates.iloc[left] > window:
                    left += 1
                cluster_size = right - left + 1
                if cluster_size >= 3:
                    findings.append({
                        "CNPJ_FUNDO": str(admin),
                        "signal_type": "coordinated_creation",
                        "DT_CONST": str(pd.Timestamp(dates.iloc[left]).date()),
                        "DT_CANCEL": None,
                        "days_active": cluster_size,
                        "max_pl": None,
                        "severity": "HIGH" if cluster_size >= 5 else "MEDIUM",
                    })
                    break  # One finding per admin

        return findings

    def _detect_suspicious_inflow(
        self, cadastro_df: pd.DataFrame, informe_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        cad = cadastro_df[["CNPJ_FUNDO", "DT_CONST"]].dropna(subset=["DT_CONST"]).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST"]).drop_duplicates("CNPJ_FUNDO")
        if cad.empty or "CAPTC_DIA" not in informe_df.columns:
            return []

        inf = informe_df[["CNPJ_FUNDO", "DT_COMPTC", "CAPTC_DIA"]].copy()
        inf["DT_COMPTC"] = pd.to_datetime(inf["DT_COMPTC"], errors="coerce")
        inf["CAPTC_DIA"] = pd.to_numeric(inf["CAPTC_DIA"], errors="coerce")
        inf = inf.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "CAPTC_DIA"])

        merged = inf.merge(cad, on="CNPJ_FUNDO", how="inner")
        if merged.empty:
            return []

        first_week = merged[
            (merged["DT_COMPTC"] >= merged["DT_CONST"])
            & (merged["DT_COMPTC"] <= merged["DT_CONST"] + pd.Timedelta(days=7))
        ]
        if first_week.empty:
            return []

        totals = (
            first_week.groupby("CNPJ_FUNDO", sort=False)
            .agg(total_inflow=("CAPTC_DIA", "sum"), DT_CONST=("DT_CONST", "first"))
        )
        flagged = totals[totals["total_inflow"] >= HOT_START_PL_MIN]
        findings: list[dict[str, Any]] = []
        for cnpj, row in flagged.iterrows():
            findings.append({
                "CNPJ_FUNDO": cnpj,
                "signal_type": "suspicious_inflow_timing",
                "DT_CONST": str(pd.Timestamp(row["DT_CONST"]).date()),
                "DT_CANCEL": None,
                "days_active": None,
                "max_pl": round(float(row["total_inflow"]), 2),
                "severity": "HIGH",
            })
        return findings
