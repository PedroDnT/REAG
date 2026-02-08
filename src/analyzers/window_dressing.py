"""
Window Dressing Detector

Detects temporal manipulation patterns around reporting dates:
- Month-end return spikes
- Quarter-end PL inflation
- Flow reversal patterns (inflow before month-end, outflow after)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.constants import MONTH_END_RETURN_ZSCORE, QUARTER_END_PL_THRESHOLD
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class WindowDressingDetector(BaseAnalyzer):
    """Detects temporal manipulation patterns around reporting dates."""

    def analyze(self, informe_df: pd.DataFrame) -> pd.DataFrame:
        self.validate_dataframe(
            informe_df,
            ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ"],
            name="informe_df",
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_month_end_spikes(informe_df))
        results.extend(self._detect_quarter_end_pl_inflation(informe_df))

        if "CAPTC_DIA" in informe_df.columns and "RESG_DIA" in informe_df.columns:
            results.extend(self._detect_flow_reversal(informe_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("WindowDressingDetector found %d signals", len(df))
        return df

    def _detect_month_end_spikes(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        work = df.copy()
        work["DT_COMPTC"] = pd.to_datetime(work["DT_COMPTC"], errors="coerce")
        work = work.dropna(subset=["DT_COMPTC"])
        work = work.sort_values(["CNPJ_FUNDO", "DT_COMPTC"])

        for cnpj, group in work.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            quota = group["VL_QUOTA"].astype(float)
            if len(quota) < 10:
                continue

            group = group.copy()
            group["daily_return"] = quota.pct_change()
            group["day_of_month"] = group["DT_COMPTC"].dt.day
            group["days_in_month"] = group["DT_COMPTC"].dt.days_in_month
            group["is_month_end"] = (
                group["days_in_month"] - group["day_of_month"]
            ) <= 1

            month_end = group[group["is_month_end"]]["daily_return"]
            mid_month = group[~group["is_month_end"]]["daily_return"]

            if len(month_end) < 2 or len(mid_month) < 5:
                continue

            me_mean = month_end.mean()
            mm_mean = mid_month.mean()
            mm_std = mid_month.std()

            if mm_std == 0 or np.isnan(mm_std):
                continue

            z_score = (me_mean - mm_mean) / mm_std
            if z_score > MONTH_END_RETURN_ZSCORE:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "month_end_return_spike",
                    "period": "month_end",
                    "metric_value": round(float(me_mean) * 100, 4),
                    "baseline_value": round(float(mm_mean) * 100, 4),
                    "deviation_pct": round(float(z_score), 2),
                    "severity": "HIGH" if z_score > 4.0 else "MEDIUM",
                })
        return findings

    def _detect_quarter_end_pl_inflation(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        work = df.copy()
        work["DT_COMPTC"] = pd.to_datetime(work["DT_COMPTC"], errors="coerce")
        work = work.dropna(subset=["DT_COMPTC"])

        for cnpj, group in work.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            if len(group) < 20:
                continue

            group = group.copy()
            group["month"] = group["DT_COMPTC"].dt.month
            group["is_quarter_end"] = group["month"].isin([3, 6, 9, 12])
            group["day_of_month"] = group["DT_COMPTC"].dt.day
            group["days_in_month"] = group["DT_COMPTC"].dt.days_in_month
            group["is_last_day"] = (
                group["days_in_month"] - group["day_of_month"]
            ) <= 1

            qe = group[group["is_quarter_end"] & group["is_last_day"]]
            if len(qe) < 2:
                continue

            group["pl_change"] = group["VL_PATRIM_LIQ"].astype(float).pct_change()
            qe_changes = group.loc[qe.index, "pl_change"].dropna()
            non_qe = group[~(group["is_quarter_end"] & group["is_last_day"])]["pl_change"].dropna()

            if len(qe_changes) < 2 or len(non_qe) < 10:
                continue

            qe_mean = qe_changes.mean()
            non_qe_mean = non_qe.mean()

            if abs(non_qe_mean) < 1e-10:
                continue

            inflation = qe_mean - non_qe_mean
            if inflation > QUARTER_END_PL_THRESHOLD:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "quarter_end_pl_inflation",
                    "period": "quarter_end",
                    "metric_value": round(float(qe_mean) * 100, 4),
                    "baseline_value": round(float(non_qe_mean) * 100, 4),
                    "deviation_pct": round(float(inflation) * 100, 2),
                    "severity": "HIGH" if inflation > 0.30 else "MEDIUM",
                })
        return findings

    def _detect_flow_reversal(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        work = df.copy()
        work["DT_COMPTC"] = pd.to_datetime(work["DT_COMPTC"], errors="coerce")
        work = work.dropna(subset=["DT_COMPTC"])

        for cnpj, group in work.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            if len(group) < 20:
                continue

            group = group.copy()
            group["net_flow"] = (
                group["CAPTC_DIA"].astype(float) - group["RESG_DIA"].astype(float)
            )
            group["day_of_month"] = group["DT_COMPTC"].dt.day
            group["days_in_month"] = group["DT_COMPTC"].dt.days_in_month

            # Last 2 days of month = pre-month-end, first 2 days = post-month-end
            group["pre_end"] = (group["days_in_month"] - group["day_of_month"]) <= 1
            group["post_start"] = group["day_of_month"] <= 2

            pre_flows = group[group["pre_end"]]["net_flow"]
            post_flows = group[group["post_start"]]["net_flow"]

            if len(pre_flows) < 2 or len(post_flows) < 2:
                continue

            avg_pre = pre_flows.mean()
            avg_post = post_flows.mean()

            # Flag: positive pre-end, negative post-start
            if avg_pre > 0 and avg_post < 0:
                magnitude = abs(avg_pre) + abs(avg_post)
                overall_avg = group["net_flow"].abs().mean()
                if overall_avg > 0 and magnitude / overall_avg > 2.0:
                    findings.append({
                        "CNPJ_FUNDO": cnpj,
                        "signal_type": "flow_reversal_pattern",
                        "period": "month_boundary",
                        "metric_value": round(float(avg_pre), 2),
                        "baseline_value": round(float(avg_post), 2),
                        "deviation_pct": round(float(magnitude / overall_avg), 2),
                        "severity": "HIGH" if magnitude / overall_avg > 3.0 else "MEDIUM",
                    })
        return findings
