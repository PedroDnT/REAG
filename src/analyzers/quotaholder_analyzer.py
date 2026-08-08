"""
Quotaholder Analyzer

Detects fraud signals from NR_COTST (number of quota holders) patterns:
- Mass exodus (sudden drops in quotaholder count)
- Phantom participation (spike-then-drop patterns)
- Per-capita AUM anomalies
- Coordinated movement across funds under the same administrator
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.constants import (
    QUOTAHOLDER_DROP_PCT,
    QUOTAHOLDER_DROP_WINDOW,
    PER_CAPITA_AUM_ZSCORE,
)
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class QuotaholderAnalyzer(BaseAnalyzer):
    """Analyzes quotaholder count patterns for fraud signals."""

    def analyze(
        self,
        informe_df: pd.DataFrame,
        cadastro_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        self.validate_dataframe(
            informe_df,
            ["CNPJ_FUNDO", "DT_COMPTC", "NR_COTST", "VL_PATRIM_LIQ"],
            name="informe_df",
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_mass_exodus(informe_df))
        results.extend(self._detect_phantom_participation(informe_df))
        results.extend(self._detect_per_capita_anomaly(informe_df))

        if cadastro_df is not None and "CNPJ_ADMIN" in cadastro_df.columns:
            results.extend(
                self._detect_coordinated_movement(informe_df, cadastro_df)
            )

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("QuotaholderAnalyzer found %d signals", len(df))
        return df

    def _detect_mass_exodus(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        window = QUOTAHOLDER_DROP_WINDOW
        threshold = QUOTAHOLDER_DROP_PCT

        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            cotst = group["NR_COTST"].astype(float)
            if cotst.max() == 0:
                continue

            pct_change = cotst.pct_change(periods=window) * 100.0
            drops = group[pct_change <= -threshold]

            for _, row in drops.iterrows():
                severity = self._exodus_severity(abs(float(pct_change.loc[row.name])))
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "DT_COMPTC": row["DT_COMPTC"],
                    "signal_type": "mass_exodus",
                    "NR_COTST": row["NR_COTST"],
                    "pct_change": round(float(pct_change.loc[row.name]), 2),
                    "per_capita_aum": None,
                    "severity": severity,
                })
        return findings

    def _detect_phantom_participation(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC").reset_index(drop=True)
            cotst = group["NR_COTST"].astype(float)
            if len(cotst) < 3:
                continue

            for i in range(1, len(cotst) - 1):
                prev_val = cotst.iloc[i - 1]
                curr_val = cotst.iloc[i]
                next_val = cotst.iloc[i + 1]
                if prev_val == 0:
                    continue
                spike = (curr_val - prev_val) / prev_val
                drop = (next_val - curr_val) / curr_val if curr_val > 0 else 0

                if spike > 0.20 and drop < -0.15:
                    findings.append({
                        "CNPJ_FUNDO": cnpj,
                        "DT_COMPTC": group.iloc[i]["DT_COMPTC"],
                        "signal_type": "phantom_participation",
                        "NR_COTST": int(curr_val),
                        "pct_change": round(spike * 100, 2),
                        "per_capita_aum": None,
                        "severity": "MEDIUM",
                    })
        return findings

    def _detect_per_capita_anomaly(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        latest = df.sort_values("DT_COMPTC").groupby("CNPJ_FUNDO").last().reset_index()
        latest = latest[latest["NR_COTST"].astype(float) > 0].copy()
        if latest.empty:
            return findings

        latest["per_capita_aum"] = (
            latest["VL_PATRIM_LIQ"].astype(float) / latest["NR_COTST"].astype(float)
        )

        mean_pc = latest["per_capita_aum"].mean()
        std_pc = latest["per_capita_aum"].std()
        if std_pc == 0 or np.isnan(std_pc):
            return findings

        latest["z_score"] = (latest["per_capita_aum"] - mean_pc) / std_pc
        outliers = latest[latest["z_score"].abs() > PER_CAPITA_AUM_ZSCORE]

        for _, row in outliers.iterrows():
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "DT_COMPTC": row["DT_COMPTC"],
                "signal_type": "per_capita_aum_anomaly",
                "NR_COTST": row["NR_COTST"],
                "pct_change": None,
                "per_capita_aum": round(float(row["per_capita_aum"]), 2),
                "severity": self._per_capita_severity(abs(float(row["z_score"]))),
            })
        return findings

    def _detect_coordinated_movement(
        self, informe_df: pd.DataFrame, cadastro_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        fund_admin = cadastro_df[["CNPJ_FUNDO", "CNPJ_ADMIN"]].drop_duplicates()
        merged = informe_df.merge(fund_admin, on="CNPJ_FUNDO", how="inner")

        if merged.empty:
            return findings

        for admin, admin_group in merged.groupby("CNPJ_ADMIN"):
            funds_in_admin = admin_group["CNPJ_FUNDO"].nunique()
            if funds_in_admin < 3:
                continue

            for dt, day_group in admin_group.groupby("DT_COMPTC"):
                if len(day_group) < 3:
                    continue
                cotst_prev = day_group.sort_values("CNPJ_FUNDO")
                # Check if we have prior day data
                prior_date = informe_df[informe_df["DT_COMPTC"] < dt]["DT_COMPTC"].max()
                if pd.isna(prior_date):
                    continue
                prior = merged[
                    (merged["DT_COMPTC"] == prior_date) & (merged["CNPJ_ADMIN"] == admin)
                ]
                if prior.empty:
                    continue

                current_map = dict(zip(
                    cotst_prev["CNPJ_FUNDO"], cotst_prev["NR_COTST"].astype(float), strict=True
                ))
                prior_map = dict(zip(
                    prior["CNPJ_FUNDO"], prior["NR_COTST"].astype(float), strict=True
                ))
                common = set(current_map.keys()) & set(prior_map.keys())
                if len(common) < 3:
                    continue

                drops = sum(
                    1 for f in common
                    if prior_map[f] > 0 and (current_map[f] - prior_map[f]) / prior_map[f] < -0.10
                )
                if drops >= 3:
                    findings.append({
                        "CNPJ_FUNDO": str(admin),
                        "DT_COMPTC": dt,
                        "signal_type": "coordinated_exodus",
                        "NR_COTST": drops,
                        "pct_change": None,
                        "per_capita_aum": None,
                        "severity": "HIGH" if drops >= 5 else "MEDIUM",
                    })
        return findings

    @staticmethod
    def _exodus_severity(drop_pct: float) -> str:
        if drop_pct >= 60:
            return "CRITICAL"
        if drop_pct >= 45:
            return "HIGH"
        if drop_pct >= 30:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _per_capita_severity(z_score: float) -> str:
        if z_score >= 5.0:
            return "CRITICAL"
        if z_score >= 4.0:
            return "HIGH"
        if z_score >= 3.0:
            return "MEDIUM"
        return "LOW"
