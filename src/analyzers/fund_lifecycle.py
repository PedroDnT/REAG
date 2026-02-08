"""
Fund Lifecycle Analyzer

Detects fraud signals from fund constitution/cancellation patterns:
- Hot start: funds reaching large PL very quickly after constitution
- Short-lived funds: created and canceled within a short period
- Coordinated creation: multiple funds under same admin created in a narrow window
- Suspicious inflow timing: large inflows starting immediately after fund creation
"""

import logging
from typing import Optional, Any

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
        informe_df: Optional[pd.DataFrame] = None,
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
        findings: list[dict[str, Any]] = []
        cad = cadastro_df[["CNPJ_FUNDO", "DT_CONST"]].dropna(subset=["DT_CONST"]).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST"])

        for _, fund_row in cad.iterrows():
            cnpj = fund_row["CNPJ_FUNDO"]
            dt_const = fund_row["DT_CONST"]

            fund_informe = informe_df[informe_df["CNPJ_FUNDO"] == cnpj].copy()
            if fund_informe.empty:
                continue

            fund_informe["DT_COMPTC"] = pd.to_datetime(fund_informe["DT_COMPTC"], errors="coerce")
            early = fund_informe[
                (fund_informe["DT_COMPTC"] >= dt_const)
                & (fund_informe["DT_COMPTC"] <= dt_const + pd.Timedelta(days=HOT_START_DAYS))
            ]
            if early.empty:
                continue

            max_pl = early["VL_PATRIM_LIQ"].astype(float).max()
            if max_pl >= HOT_START_PL_MIN:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "hot_start",
                    "DT_CONST": str(dt_const.date()),
                    "DT_CANCEL": None,
                    "days_active": None,
                    "max_pl": round(float(max_pl), 2),
                    "severity": "CRITICAL" if max_pl >= HOT_START_PL_MIN * 5 else "HIGH",
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

        for admin, group in cad.groupby("CNPJ_ADMIN"):
            if len(group) < 3:
                continue
            sorted_group = group.sort_values("DT_CONST")
            dates = sorted_group["DT_CONST"].values

            for i in range(len(dates)):
                window_end = dates[i] + pd.Timedelta(days=COORDINATED_CREATION_WINDOW)
                cluster = sorted_group[
                    (sorted_group["DT_CONST"] >= dates[i])
                    & (sorted_group["DT_CONST"] <= window_end)
                ]
                if len(cluster) >= 3:
                    findings.append({
                        "CNPJ_FUNDO": str(admin),
                        "signal_type": "coordinated_creation",
                        "DT_CONST": str(pd.Timestamp(dates[i]).date()),
                        "DT_CANCEL": None,
                        "days_active": len(cluster),
                        "max_pl": None,
                        "severity": "HIGH" if len(cluster) >= 5 else "MEDIUM",
                    })
                    break  # One finding per admin

        return findings

    def _detect_suspicious_inflow(
        self, cadastro_df: pd.DataFrame, informe_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        cad = cadastro_df[["CNPJ_FUNDO", "DT_CONST"]].dropna(subset=["DT_CONST"]).copy()
        cad["DT_CONST"] = pd.to_datetime(cad["DT_CONST"], errors="coerce")
        cad = cad.dropna(subset=["DT_CONST"])

        for _, fund_row in cad.iterrows():
            cnpj = fund_row["CNPJ_FUNDO"]
            dt_const = fund_row["DT_CONST"]

            fund_informe = informe_df[informe_df["CNPJ_FUNDO"] == cnpj].copy()
            if fund_informe.empty:
                continue

            fund_informe["DT_COMPTC"] = pd.to_datetime(fund_informe["DT_COMPTC"], errors="coerce")
            first_week = fund_informe[
                (fund_informe["DT_COMPTC"] >= dt_const)
                & (fund_informe["DT_COMPTC"] <= dt_const + pd.Timedelta(days=7))
            ]
            if first_week.empty:
                continue

            total_inflow = first_week["CAPTC_DIA"].astype(float).sum()
            if total_inflow >= HOT_START_PL_MIN:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "suspicious_inflow_timing",
                    "DT_CONST": str(dt_const.date()),
                    "DT_CANCEL": None,
                    "days_active": None,
                    "max_pl": round(float(total_inflow), 2),
                    "severity": "HIGH",
                })
        return findings
