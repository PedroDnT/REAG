"""
Cost Basis Analyzer

Detects fraud signals from VL_CUSTO_POS_FINAL (cost basis) patterns:
- Unrealized gain anomaly (extreme mark-to-cost ratios)
- Zero-cost assets (phantom or donated positions)
- Negative cost basis (data fabrication)
- Systematic overvaluation across a fund's portfolio
"""

import logging
from typing import Optional, Any

import numpy as np
import pandas as pd

from config.constants import (
    COST_BASIS_GAIN_THRESHOLD,
    COST_BASIS_ZERO_VALUE_MIN,
)
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class CostBasisAnalyzer(BaseAnalyzer):
    """Analyzes cost basis vs market value for fraud signals."""

    def analyze(self, cda_df: pd.DataFrame) -> pd.DataFrame:
        self.validate_dataframe(
            cda_df,
            ["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO", "VL_CUSTO_POS_FINAL"],
            name="cda_df",
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_unrealized_gain_anomaly(cda_df))
        results.extend(self._detect_zero_cost_assets(cda_df))
        results.extend(self._detect_negative_cost(cda_df))
        results.extend(self._detect_systematic_overvaluation(cda_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("CostBasisAnalyzer found %d signals", len(df))
        return df

    def _detect_unrealized_gain_anomaly(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        work = df[df["VL_CUSTO_POS_FINAL"].astype(float) > 0].copy()
        if work.empty:
            return findings

        work["gain_ratio"] = (
            work["VL_MERCADO"].astype(float) / work["VL_CUSTO_POS_FINAL"].astype(float)
        )

        extreme = work[work["gain_ratio"] > COST_BASIS_GAIN_THRESHOLD]
        for _, row in extreme.iterrows():
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "CD_ATIVO": row["CD_ATIVO"],
                "signal_type": "unrealized_gain_anomaly",
                "VL_MERCADO": float(row["VL_MERCADO"]),
                "VL_CUSTO_POS_FINAL": float(row["VL_CUSTO_POS_FINAL"]),
                "gain_ratio": round(float(row["gain_ratio"]), 2),
                "severity": self._gain_severity(float(row["gain_ratio"])),
            })
        return findings

    def _detect_zero_cost_assets(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        zero_cost = df[
            (df["VL_CUSTO_POS_FINAL"].astype(float) == 0)
            & (df["VL_MERCADO"].astype(float) > COST_BASIS_ZERO_VALUE_MIN)
        ]

        for _, row in zero_cost.iterrows():
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "CD_ATIVO": row["CD_ATIVO"],
                "signal_type": "zero_cost_asset",
                "VL_MERCADO": float(row["VL_MERCADO"]),
                "VL_CUSTO_POS_FINAL": 0.0,
                "gain_ratio": None,
                "severity": "HIGH",
            })
        return findings

    def _detect_negative_cost(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        negative = df[df["VL_CUSTO_POS_FINAL"].astype(float) < 0]

        for _, row in negative.iterrows():
            findings.append({
                "CNPJ_FUNDO": row["CNPJ_FUNDO"],
                "CD_ATIVO": row["CD_ATIVO"],
                "signal_type": "negative_cost_basis",
                "VL_MERCADO": float(row["VL_MERCADO"]),
                "VL_CUSTO_POS_FINAL": float(row["VL_CUSTO_POS_FINAL"]),
                "gain_ratio": None,
                "severity": "CRITICAL",
            })
        return findings

    def _detect_systematic_overvaluation(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        work = df[df["VL_CUSTO_POS_FINAL"].astype(float) > 0].copy()
        if work.empty:
            return findings

        work["gain_ratio"] = (
            work["VL_MERCADO"].astype(float) / work["VL_CUSTO_POS_FINAL"].astype(float)
        )

        fund_avg = work.groupby("CNPJ_FUNDO")["gain_ratio"].mean()
        if len(fund_avg) < 3:
            return findings

        mean_ratio = fund_avg.mean()
        std_ratio = fund_avg.std()
        if std_ratio == 0 or np.isnan(std_ratio):
            return findings

        z_scores = (fund_avg - mean_ratio) / std_ratio
        outliers = z_scores[z_scores > 3.0]

        for cnpj, z in outliers.items():
            findings.append({
                "CNPJ_FUNDO": cnpj,
                "CD_ATIVO": "FUND_LEVEL",
                "signal_type": "systematic_overvaluation",
                "VL_MERCADO": None,
                "VL_CUSTO_POS_FINAL": None,
                "gain_ratio": round(float(fund_avg[cnpj]), 2),
                "severity": "HIGH" if z > 4.0 else "MEDIUM",
            })
        return findings

    @staticmethod
    def _gain_severity(gain_ratio: float) -> str:
        if gain_ratio >= 20.0:
            return "CRITICAL"
        if gain_ratio >= 10.0:
            return "HIGH"
        if gain_ratio >= 5.0:
            return "MEDIUM"
        return "LOW"
