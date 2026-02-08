"""
Valuation Smoothing Analyzer

Replaces the valuation_smoothing_stub in signal_registry.
Detects return manipulation patterns:
- Return autocorrelation (smoothed pricing)
- Stale pricing (zero price change for consecutive days)
- Volatility ratio (fund volatility vs expected)
- Return distribution anomalies (excess kurtosis)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.constants import AUTOCORRELATION_THRESHOLD, STALE_PRICE_DAYS, VOLATILITY_RATIO_MIN
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class ValuationSmoothingAnalyzer(BaseAnalyzer):
    """Detects valuation smoothing and stale pricing patterns."""

    def analyze(self, informe_df: pd.DataFrame) -> pd.DataFrame:
        self.validate_dataframe(
            informe_df,
            ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"],
            name="informe_df",
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_autocorrelation(informe_df))
        results.extend(self._detect_stale_pricing(informe_df))
        results.extend(self._detect_low_volatility_ratio(informe_df))
        results.extend(self._detect_distribution_anomaly(informe_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("ValuationSmoothingAnalyzer found %d signals", len(df))
        return df

    def _detect_autocorrelation(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            returns = group["VL_QUOTA"].astype(float).pct_change().dropna()
            if len(returns) < 20:
                continue

            autocorr = returns.autocorr(lag=1)
            if autocorr is None or np.isnan(autocorr):
                continue

            if autocorr > AUTOCORRELATION_THRESHOLD:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "return_autocorrelation",
                    "autocorrelation": round(float(autocorr), 4),
                    "stale_days": None,
                    "vol_ratio": None,
                    "severity": self._autocorr_severity(autocorr),
                })
        return findings

    def _detect_stale_pricing(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            quota = group["VL_QUOTA"].astype(float)
            if len(quota) < STALE_PRICE_DAYS + 1:
                continue

            changes = quota.diff()
            # Count max consecutive zeros
            max_stale = 0
            current_stale = 0
            for change in changes.values:
                if change == 0:
                    current_stale += 1
                    max_stale = max(max_stale, current_stale)
                else:
                    current_stale = 0

            if max_stale >= STALE_PRICE_DAYS:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "stale_pricing",
                    "autocorrelation": None,
                    "stale_days": max_stale,
                    "vol_ratio": None,
                    "severity": "CRITICAL" if max_stale >= 15 else "HIGH" if max_stale >= 10 else "MEDIUM",
                })
        return findings

    def _detect_low_volatility_ratio(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        fund_vols: dict[str, float] = {}
        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            returns = group["VL_QUOTA"].astype(float).pct_change().dropna()
            if len(returns) < 20:
                continue
            fund_vols[cnpj] = float(returns.std())

        if len(fund_vols) < 5:
            return findings

        vols = pd.Series(fund_vols)
        median_vol = vols.median()
        if median_vol == 0:
            return findings

        for cnpj, vol in fund_vols.items():
            ratio = vol / median_vol
            if ratio < VOLATILITY_RATIO_MIN and vol > 0:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "low_volatility_ratio",
                    "autocorrelation": None,
                    "stale_days": None,
                    "vol_ratio": round(ratio, 4),
                    "severity": "HIGH" if ratio < 0.15 else "MEDIUM",
                })
        return findings

    def _detect_distribution_anomaly(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for cnpj, group in df.groupby("CNPJ_FUNDO"):
            group = group.sort_values("DT_COMPTC")
            returns = group["VL_QUOTA"].astype(float).pct_change().dropna()
            if len(returns) < 30:
                continue

            kurtosis = float(returns.kurtosis())
            if np.isnan(kurtosis):
                continue

            # Negative excess kurtosis suggests manufactured returns (too thin tails)
            if kurtosis < -1.0:
                findings.append({
                    "CNPJ_FUNDO": cnpj,
                    "signal_type": "return_distribution_anomaly",
                    "autocorrelation": None,
                    "stale_days": None,
                    "vol_ratio": round(kurtosis, 4),
                    "severity": "MEDIUM",
                })
        return findings

    @staticmethod
    def _autocorr_severity(autocorr: float) -> str:
        if autocorr > 0.7:
            return "CRITICAL"
        if autocorr > 0.5:
            return "HIGH"
        if autocorr > 0.3:
            return "MEDIUM"
        return "LOW"
