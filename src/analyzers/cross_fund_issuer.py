"""
Cross-Fund Issuer Analyzer

System-wide issuer analysis across all funds:
- Captive issuers: issuers appearing in only one administrator's funds
- Name similarity clustering: near-identical issuer names with different CNPJs
- Universe concentration: issuers heavily weighted under one admin
- Issuer-admin relationship: issuer CNPJ sharing digits with admin CNPJ
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.constants import CAPTIVE_ISSUER_MIN_FUNDS, ISSUER_NAME_SIMILARITY
from .base import BaseAnalyzer
from src.utils.validation import normalize_cnpj_digits

logger = logging.getLogger(__name__)


def _jaro_winkler_similarity(s1: str, s2: str) -> float:
    """Simple Jaro-Winkler similarity implementation."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 0:
        max_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(len2, i + max_dist + 1)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

    # Winkler prefix bonus
    prefix = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * 0.1 * (1 - jaro)


class CrossFundIssuerAnalyzer(BaseAnalyzer):
    """Analyzes issuer relationships across funds for fraud signals."""

    def analyze(
        self,
        cda_df: pd.DataFrame,
        cadastro_df: pd.DataFrame,
    ) -> pd.DataFrame:
        self.validate_dataframe(
            cda_df, ["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO"], name="cda_df"
        )
        self.validate_dataframe(
            cadastro_df, ["CNPJ_FUNDO", "CNPJ_ADMIN"], name="cadastro_df"
        )

        results: list[dict[str, Any]] = []

        if "EMISSOR" in cda_df.columns:
            enriched = self._enrich_with_admin(cda_df, cadastro_df)
            results.extend(self._detect_captive_issuers(enriched))
            results.extend(self._detect_name_similarity(enriched))
            results.extend(self._detect_universe_concentration(enriched))
            results.extend(self._detect_issuer_admin_relationship(enriched, cadastro_df))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info("CrossFundIssuerAnalyzer found %d signals", len(df))
        return df

    def _enrich_with_admin(
        self, cda_df: pd.DataFrame, cadastro_df: pd.DataFrame
    ) -> pd.DataFrame:
        fund_admin = cadastro_df[["CNPJ_FUNDO", "CNPJ_ADMIN"]].drop_duplicates()
        return cda_df.merge(fund_admin, on="CNPJ_FUNDO", how="inner")

    def _detect_captive_issuers(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        issuer_stats = (
            df.groupby("EMISSOR")
            .agg(
                num_funds=("CNPJ_FUNDO", "nunique"),
                num_admins=("CNPJ_ADMIN", "nunique"),
                total_exposure=("VL_MERCADO", "sum"),
            )
            .reset_index()
        )

        captive = issuer_stats[
            (issuer_stats["num_admins"] == 1)
            & (issuer_stats["num_funds"] >= CAPTIVE_ISSUER_MIN_FUNDS)
        ]

        for _, row in captive.iterrows():
            admin = df[df["EMISSOR"] == row["EMISSOR"]]["CNPJ_ADMIN"].iloc[0]
            findings.append({
                "EMISSOR": row["EMISSOR"],
                "signal_type": "captive_issuer",
                "num_funds": int(row["num_funds"]),
                "num_admins": 1,
                "total_exposure": round(float(row["total_exposure"]), 2),
                "captive_admin": admin,
                "severity": "HIGH" if row["num_funds"] >= 5 else "MEDIUM",
            })
        return findings

    def _detect_name_similarity(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        issuers = df["EMISSOR"].dropna().unique()
        if len(issuers) < 2 or len(issuers) > 500:
            # Skip if too many issuers (O(n^2) comparison)
            return findings

        issuer_list = sorted(set(str(e).strip().upper() for e in issuers if str(e).strip()))
        seen_pairs: set[tuple[str, str]] = set()

        for i in range(len(issuer_list)):
            for j in range(i + 1, len(issuer_list)):
                if issuer_list[i] == issuer_list[j]:
                    continue
                sim = _jaro_winkler_similarity(issuer_list[i], issuer_list[j])
                if sim >= ISSUER_NAME_SIMILARITY and sim < 1.0:
                    pair = (issuer_list[i], issuer_list[j])
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        findings.append({
                            "EMISSOR": f"{issuer_list[i]} | {issuer_list[j]}",
                            "signal_type": "name_similarity_cluster",
                            "num_funds": None,
                            "num_admins": None,
                            "total_exposure": None,
                            "captive_admin": None,
                            "severity": "MEDIUM",
                        })
        return findings

    def _detect_universe_concentration(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        admin_issuer = (
            df.groupby(["CNPJ_ADMIN", "EMISSOR"])
            .agg(
                total_value=("VL_MERCADO", "sum"),
                num_funds=("CNPJ_FUNDO", "nunique"),
            )
            .reset_index()
        )

        admin_total = df.groupby("CNPJ_ADMIN")["VL_MERCADO"].sum().reset_index()
        admin_total = admin_total.rename(columns={"VL_MERCADO": "admin_total"})

        merged = admin_issuer.merge(admin_total, on="CNPJ_ADMIN")
        merged["pct_of_admin"] = (
            merged["total_value"].astype(float) / merged["admin_total"].astype(float)
        )

        concentrated = merged[
            (merged["pct_of_admin"] > 0.30) & (merged["num_funds"] >= 2)
        ]

        for _, row in concentrated.iterrows():
            findings.append({
                "EMISSOR": row["EMISSOR"],
                "signal_type": "universe_concentration",
                "num_funds": int(row["num_funds"]),
                "num_admins": 1,
                "total_exposure": round(float(row["total_value"]), 2),
                "captive_admin": row["CNPJ_ADMIN"],
                "severity": "CRITICAL" if row["pct_of_admin"] > 0.50 else "HIGH",
            })
        return findings

    def _detect_issuer_admin_relationship(
        self, enriched_df: pd.DataFrame, cadastro_df: pd.DataFrame
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        admins = cadastro_df["CNPJ_ADMIN"].dropna().unique()
        admin_prefixes = {d[:8]: str(a) for a in admins if (d := normalize_cnpj_digits(a)) and len(d) >= 8}

        issuers = enriched_df[["EMISSOR", "CNPJ_ADMIN"]].drop_duplicates()

        for _, row in issuers.iterrows():
            emissor_digits = normalize_cnpj_digits(row["EMISSOR"])
            if not emissor_digits or len(emissor_digits) < 8:
                continue
            emissor_prefix = emissor_digits[:8]
            if emissor_prefix in admin_prefixes:
                findings.append({
                    "EMISSOR": row["EMISSOR"],
                    "signal_type": "issuer_admin_affiliation",
                    "num_funds": None,
                    "num_admins": None,
                    "total_exposure": None,
                    "captive_admin": admin_prefixes[emissor_prefix],
                    "severity": "HIGH",
                })
        return findings
