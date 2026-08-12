"""
Cross-Fund Price Divergence Analyzer

Detects asset mismarking without any external price source.

When several funds hold the same asset on the same date, each declares its own
market value and quantity in the CDA. The implied unit price
(``VL_MERCADO / QT_POS``) should agree across them: they are marking the same
instrument on the same day. A fund whose declared price diverges materially from
the cross-fund consensus is either using a different valuation methodology or
mismarking the position -- inflating it to prop up NAV, or suppressing it to
hide a loss.

Why this rather than a market data feed:

- **Coverage.** CDA holdings are dominated by unlisted credit -- CRI, CRA,
  debêntures, cotas de fundos. No public price feed covers them, and they are
  precisely where discretionary marking, and therefore mismarking, happens.
  Listed equities are the easy case and the least interesting one.
- **Provenance.** Every number here comes from a CVM filing the fund itself
  submitted. There is no third-party scraper in the evidentiary chain.
- **Availability.** No network, no API key, no rate limit.

The consensus is the median rather than the mean, and dispersion is measured
with MAD rather than standard deviation, so a single grossly mismarked fund
cannot drag the reference toward itself.

See ``src/analyzers/market_data.py`` for the complementary listed-equity check,
which requires the optional ``yfinance`` dependency.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.constants import (
    PRICE_DIVERGENCE_SEVERE,
    PRICE_DIVERGENCE_THRESHOLD,
)
from src.utils.statistics import calculate_mad

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)

# An asset must be held by at least this many funds on a date for a consensus
# price to mean anything. With two, "divergence from the median" is just the gap
# between the pair and there is no way to say which side is wrong.
MIN_FUNDS_FOR_CONSENSUS = 3

# Robust z-score cutoff, applied alongside the percentage threshold. A fund must
# clear both: a large percentage gap is unremarkable when every fund disagrees
# by that much, and a large z-score is unremarkable when the spread is pennies.
DIVERGENCE_ROBUST_Z = 3.0


class CrossFundPriceDivergenceAnalyzer(BaseAnalyzer):
    """Flags funds whose declared unit price disagrees with their peers'."""

    def analyze(self, cda_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compare each fund's declared unit price against the cross-fund median.

        Args:
            cda_df: CDA portfolio composition. Requires CNPJ_FUNDO, CD_ATIVO,
                DT_COMPTC, VL_MERCADO and QT_POS.

        Returns:
            DataFrame of divergence findings, empty if none were detected
        """
        self.validate_dataframe(
            cda_df,
            ["CNPJ_FUNDO", "CD_ATIVO", "DT_COMPTC", "VL_MERCADO", "QT_POS"],
            name="cda_df",
        )

        priced = self._declared_unit_prices(cda_df)
        if priced.empty:
            logger.info("No positions with a usable declared unit price")
            return pd.DataFrame()

        findings: list[dict[str, Any]] = []
        for (asset, comptc_date), group in priced.groupby(["CD_ATIVO", "DT_COMPTC"]):
            findings.extend(self._divergences_within_group(asset, comptc_date, group))

        if not findings:
            return pd.DataFrame()

        result = pd.DataFrame(findings).sort_values(
            "divergence_pct", key=abs, ascending=False
        )
        logger.info(
            "CrossFundPriceDivergenceAnalyzer found %d signals across %d assets",
            len(result),
            result["CD_ATIVO"].nunique(),
        )
        return result.reset_index(drop=True)

    @staticmethod
    def _declared_unit_prices(cda_df: pd.DataFrame) -> pd.DataFrame:
        """Derive per-position unit prices, dropping rows that cannot yield one."""
        df = cda_df.copy()

        quantity = pd.to_numeric(df["QT_POS"], errors="coerce")
        value = pd.to_numeric(df["VL_MERCADO"], errors="coerce")

        # A zero or missing quantity gives no price, and a non-positive value is
        # not a mark. Both are dropped rather than recorded as a zero price,
        # which would otherwise register as a 100% divergence.
        usable = quantity.notna() & (quantity > 0) & value.notna() & (value > 0)

        df = df.loc[usable].copy()
        if df.empty:
            return df

        # Only compare rows identified by a specific instrument. Some CDA blocks
        # carry no asset code and fall back to the issuer, but a bank issues
        # dozens of CDBs with different maturities and rates -- comparing their
        # unit prices compares different paper and manufactures divergences.
        # Verified against real CVM data, where the issuer fallback produced
        # "BANCO BRADESCO" as a single asset with an 858% spread.
        if "CD_ATIVO_FONTE" in df.columns:
            from src.processors.data_processor import DataProcessor

            instrument_level = df["CD_ATIVO_FONTE"].isin(
                DataProcessor.INSTRUMENT_LEVEL_ASSET_SOURCES
            )
            dropped = int((~instrument_level).sum())
            if dropped:
                logger.info(
                    "Ignorando %d posicao(oes) identificadas apenas pelo emissor", dropped
                )
            df = df.loc[instrument_level].copy()
            if df.empty:
                return df

        df["declared_unit_price"] = value.loc[df.index] / quantity.loc[df.index]
        return df[np.isfinite(df["declared_unit_price"])]

    def _divergences_within_group(
        self, asset: Any, comptc_date: Any, group: pd.DataFrame
    ) -> list[dict[str, Any]]:
        """Compare one asset's declared prices on one date across funds."""
        # Several positions in one fund (different maturities, tranches) would
        # each vote; collapse to one price per fund first.
        by_fund = group.groupby("CNPJ_FUNDO").agg(
            declared_unit_price=("declared_unit_price", "median"),
            position_value=("VL_MERCADO", "sum"),
        )

        if len(by_fund) < MIN_FUNDS_FOR_CONSENSUS:
            return []

        prices = by_fund["declared_unit_price"]
        consensus = prices.median()
        if not np.isfinite(consensus) or consensus <= 0:
            return []

        mad = calculate_mad(prices)
        divergence_pct = (prices - consensus) / consensus * 100.0

        # MAD of zero means every fund agrees exactly; any outlier would be
        # infinitely many MADs away, so fall back to the percentage test alone.
        robust_z = (prices - consensus) / mad if mad > 0 else pd.Series(
            np.inf, index=prices.index
        ).where(prices != consensus, 0.0)

        findings: list[dict[str, Any]] = []
        for cnpj in prices.index:
            pct = float(divergence_pct.loc[cnpj])
            z = float(robust_z.loc[cnpj])

            if abs(pct) < PRICE_DIVERGENCE_THRESHOLD or abs(z) < DIVERGENCE_ROBUST_Z:
                continue

            findings.append({
                "CNPJ_FUNDO": cnpj,
                "CD_ATIVO": asset,
                "DT_COMPTC": comptc_date,
                "signal_type": "cross_fund_price_divergence",
                "declared_unit_price": round(float(prices.loc[cnpj]), 6),
                "consensus_unit_price": round(float(consensus), 6),
                "divergence_pct": round(pct, 2),
                "robust_z": round(z, 2) if np.isfinite(z) else None,
                "peer_fund_count": int(len(by_fund)),
                "position_value": float(by_fund.loc[cnpj, "position_value"]),
                "direction": "OVERVALUATION" if pct > 0 else "UNDERVALUATION",
                "severity": self._severity(pct),
            })

        return findings

    @staticmethod
    def _severity(divergence_pct: float) -> str:
        """Grade a divergence by how far it sits from the cross-fund consensus."""
        magnitude = abs(divergence_pct)
        if magnitude >= PRICE_DIVERGENCE_SEVERE * 2:
            return "CRITICAL"
        if magnitude >= PRICE_DIVERGENCE_SEVERE:
            return "HIGH"
        if magnitude >= PRICE_DIVERGENCE_THRESHOLD * 2:
            return "MEDIUM"
        return "LOW"
