"""
Manager Network Analyzer

Detects fraud signals from CNPJ_GESTOR (fund manager) relationships:
- Shared manager anomaly: single manager across multiple administrators
- Cross-admin asset overlap: same manager holding identical illiquid assets in different admin groups
- Manager concentration: disproportionate AUM under one manager
- Manager-admin circular: manager appearing as issuer in own fund's portfolio
"""

import logging
from typing import Optional, Any

import numpy as np
import pandas as pd

from .base import BaseAnalyzer
from src.utils.validation import normalize_cnpj_digits

logger = logging.getLogger(__name__)


class ManagerNetworkAnalyzer(BaseAnalyzer):
    """Analyzes fund manager network relationships for fraud signals."""

    def analyze(
        self,
        cadastro_df: pd.DataFrame,
        cda_df: Optional[pd.DataFrame] = None,
        informe_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        self.validate_dataframe(
            cadastro_df,
            ["CNPJ_FUNDO", "CNPJ_ADMIN", "CNPJ_GESTOR"],
            name="cadastro_df",
        )

        results: list[dict[str, Any]] = []
        results.extend(self._detect_shared_manager(cadastro_df))
        results.extend(self._detect_manager_concentration(cadastro_df, informe_df))

        if cda_df is not None:
            results.extend(self._detect_cross_admin_overlap(cadastro_df, cda_df))
            results.extend(self._detect_manager_as_issuer(cadastro_df, cda_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("ManagerNetworkAnalyzer found %d signals", len(df))
        return df

    def _detect_shared_manager(self, cadastro_df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        manager_admins = (
            cadastro_df.groupby("CNPJ_GESTOR")["CNPJ_ADMIN"]
            .nunique()
            .reset_index()
            .rename(columns={"CNPJ_ADMIN": "num_admins"})
        )
        manager_funds = (
            cadastro_df.groupby("CNPJ_GESTOR")["CNPJ_FUNDO"]
            .nunique()
            .reset_index()
            .rename(columns={"CNPJ_FUNDO": "num_funds"})
        )
        merged = manager_admins.merge(manager_funds, on="CNPJ_GESTOR")
        flagged = merged[merged["num_admins"] >= 3]

        for _, row in flagged.iterrows():
            findings.append({
                "CNPJ_GESTOR": row["CNPJ_GESTOR"],
                "signal_type": "shared_manager_anomaly",
                "num_admins": int(row["num_admins"]),
                "num_funds": int(row["num_funds"]),
                "total_aum": None,
                "overlap_assets": None,
                "severity": "HIGH" if row["num_admins"] >= 5 else "MEDIUM",
            })
        return findings

    def _detect_manager_concentration(
        self,
        cadastro_df: pd.DataFrame,
        informe_df: Optional[pd.DataFrame],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if informe_df is None or informe_df.empty:
            return findings
        if "VL_PATRIM_LIQ" not in informe_df.columns:
            return findings

        latest = (
            informe_df.sort_values("DT_COMPTC")
            .groupby("CNPJ_FUNDO")
            .last()
            .reset_index()[["CNPJ_FUNDO", "VL_PATRIM_LIQ"]]
        )
        merged = cadastro_df[["CNPJ_FUNDO", "CNPJ_GESTOR"]].merge(
            latest, on="CNPJ_FUNDO", how="inner"
        )
        if merged.empty:
            return findings

        manager_aum = (
            merged.groupby("CNPJ_GESTOR")["VL_PATRIM_LIQ"]
            .sum()
            .reset_index()
            .rename(columns={"VL_PATRIM_LIQ": "total_aum"})
        )
        manager_funds = (
            merged.groupby("CNPJ_GESTOR")["CNPJ_FUNDO"]
            .nunique()
            .reset_index()
            .rename(columns={"CNPJ_FUNDO": "num_funds"})
        )
        stats = manager_aum.merge(manager_funds, on="CNPJ_GESTOR")

        if len(stats) < 3:
            return findings

        mean_aum = stats["total_aum"].astype(float).mean()
        std_aum = stats["total_aum"].astype(float).std()
        if std_aum == 0 or np.isnan(std_aum):
            return findings

        stats["z_score"] = (stats["total_aum"].astype(float) - mean_aum) / std_aum
        outliers = stats[stats["z_score"] > 3.0]

        for _, row in outliers.iterrows():
            findings.append({
                "CNPJ_GESTOR": row["CNPJ_GESTOR"],
                "signal_type": "manager_concentration",
                "num_admins": None,
                "num_funds": int(row["num_funds"]),
                "total_aum": round(float(row["total_aum"]), 2),
                "overlap_assets": None,
                "severity": "HIGH" if row["z_score"] > 4.0 else "MEDIUM",
            })
        return findings

    def _detect_cross_admin_overlap(
        self, cadastro_df: pd.DataFrame, cda_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if "CD_ATIVO" not in cda_df.columns:
            return findings

        fund_admin = cadastro_df[["CNPJ_FUNDO", "CNPJ_ADMIN", "CNPJ_GESTOR"]].drop_duplicates()
        enriched = cda_df[["CNPJ_FUNDO", "CD_ATIVO"]].merge(
            fund_admin, on="CNPJ_FUNDO", how="inner"
        )
        if enriched.empty:
            return findings

        for gestor, gestor_group in enriched.groupby("CNPJ_GESTOR"):
            admins = gestor_group["CNPJ_ADMIN"].nunique()
            if admins < 2:
                continue

            asset_admin = (
                gestor_group.groupby("CD_ATIVO")["CNPJ_ADMIN"]
                .nunique()
                .reset_index()
                .rename(columns={"CNPJ_ADMIN": "admin_count"})
            )
            overlapping = asset_admin[asset_admin["admin_count"] >= 2]
            if overlapping.empty:
                continue

            findings.append({
                "CNPJ_GESTOR": gestor,
                "signal_type": "cross_admin_asset_overlap",
                "num_admins": int(admins),
                "num_funds": int(gestor_group["CNPJ_FUNDO"].nunique()),
                "total_aum": None,
                "overlap_assets": int(len(overlapping)),
                "severity": "HIGH" if len(overlapping) >= 5 else "MEDIUM",
            })
        return findings

    def _detect_manager_as_issuer(
        self, cadastro_df: pd.DataFrame, cda_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if "EMISSOR" not in cda_df.columns:
            return findings

        fund_gestor = cadastro_df[["CNPJ_FUNDO", "CNPJ_GESTOR"]].drop_duplicates()
        enriched = cda_df[["CNPJ_FUNDO", "CD_ATIVO", "EMISSOR"]].merge(
            fund_gestor, on="CNPJ_FUNDO", how="inner"
        )
        if enriched.empty:
            return findings

        enriched["gestor_digits"] = enriched["CNPJ_GESTOR"].apply(normalize_cnpj_digits)
        enriched["emissor_digits"] = enriched["EMISSOR"].apply(normalize_cnpj_digits)

        circular = enriched[
            (enriched["gestor_digits"].str.len() >= 8)
            & (enriched["emissor_digits"].str.len() >= 8)
            & (enriched["gestor_digits"].str[:8] == enriched["emissor_digits"].str[:8])
        ]

        for gestor, group in circular.groupby("CNPJ_GESTOR"):
            findings.append({
                "CNPJ_GESTOR": gestor,
                "signal_type": "manager_admin_circular",
                "num_admins": None,
                "num_funds": int(group["CNPJ_FUNDO"].nunique()),
                "total_aum": None,
                "overlap_assets": int(group["CD_ATIVO"].nunique()),
                "severity": "CRITICAL",
            })
        return findings
