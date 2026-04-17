"""Fund Selection Module - Flexible Fund Filtering.

This module provides utilities for selecting funds based on various criteria:
- Administrator name
- Manager name
- Explicit CNPJ list
- All funds (for benchmarking)

The module centralizes fund selection logic, making the investigation system
flexible enough to analyze any fund or fund group, not just REAG-specific funds.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

import pandas as pd

from src.utils.cnpj_utils import normalize_cnpj

logger = logging.getLogger(__name__)


class FundSelector:
    """Flexible fund selection utility.

    Supports multiple selection modes:
    - By administrator name (e.g., "REAG DTVM")
    - By manager name (e.g., "XYZ Gestora")
    - By explicit CNPJ list
    - All funds (for market-wide analysis)
    """

    def __init__(self, cadastro_df: pd.DataFrame):
        """Initialize fund selector with cadastro data.

        Args:
            cadastro_df: CVM cadastro DataFrame with fund registration data
        """
        self.cadastro_df = cadastro_df.copy()
        self._normalize_cadastro()

    def _normalize_cadastro(self) -> None:
        """Normalize cadastro DataFrame column names and data."""
        # Ensure required columns exist
        required_cols = ['CNPJ_FUNDO', 'DENOM_SOCIAL']
        missing = [col for col in required_cols if col not in self.cadastro_df.columns]
        if missing:
            logger.warning(f"Missing required columns in cadastro: {missing}")

        # Normalize CNPJs if column exists
        if 'CNPJ_FUNDO' in self.cadastro_df.columns:
            self.cadastro_df['CNPJ_FUNDO'] = self.cadastro_df['CNPJ_FUNDO'].apply(
                lambda x: normalize_cnpj(str(x)) if pd.notna(x) else x
            )

        if 'CNPJ_ADMIN' in self.cadastro_df.columns:
            self.cadastro_df['CNPJ_ADMIN'] = self.cadastro_df['CNPJ_ADMIN'].apply(
                lambda x: normalize_cnpj(str(x)) if pd.notna(x) else x
            )

    def select_by_administrator(
        self,
        admin_name: str,
        case_sensitive: bool = False
    ) -> pd.DataFrame:
        """Select funds by administrator name.

        Args:
            admin_name: Administrator name or partial name to search
            case_sensitive: Whether to perform case-sensitive matching

        Returns:
            DataFrame with funds administered by the specified administrator
        """
        if 'ADMIN' not in self.cadastro_df.columns and 'DENOM_SOCIAL' not in self.cadastro_df.columns:
            logger.error("No administrator column found in cadastro")
            return pd.DataFrame()

        # Try ADMIN column first, fall back to DENOM_SOCIAL
        search_col = 'ADMIN' if 'ADMIN' in self.cadastro_df.columns else 'DENOM_SOCIAL'

        mask = self.cadastro_df[search_col].str.contains(
            admin_name,
            case=case_sensitive,
            na=False
        )

        result = self.cadastro_df[mask].copy()
        logger.info(f"Selected {len(result)} funds for administrator '{admin_name}'")
        return result

    def select_by_administrator_cnpj(self, admin_cnpjs: List[str]) -> pd.DataFrame:
        """Select funds by administrator CNPJ(s).

        Args:
            admin_cnpjs: List of administrator CNPJs

        Returns:
            DataFrame with funds administered by the specified CNPJs
        """
        if 'CNPJ_ADMIN' not in self.cadastro_df.columns:
            logger.error("CNPJ_ADMIN column not found in cadastro")
            return pd.DataFrame()

        # Normalize input CNPJs
        normalized_cnpjs = [normalize_cnpj(cnpj) for cnpj in admin_cnpjs]

        mask = self.cadastro_df['CNPJ_ADMIN'].isin(normalized_cnpjs)
        result = self.cadastro_df[mask].copy()
        logger.info(f"Selected {len(result)} funds for {len(admin_cnpjs)} administrator CNPJs")
        return result

    def select_by_manager(
        self,
        manager_name: str,
        case_sensitive: bool = False
    ) -> pd.DataFrame:
        """Select funds by manager name.

        Args:
            manager_name: Manager name or partial name to search
            case_sensitive: Whether to perform case-sensitive matching

        Returns:
            DataFrame with funds managed by the specified manager
        """
        if 'GESTOR' not in self.cadastro_df.columns:
            logger.error("GESTOR column not found in cadastro")
            return pd.DataFrame()

        mask = self.cadastro_df['GESTOR'].str.contains(
            manager_name,
            case=case_sensitive,
            na=False
        )

        result = self.cadastro_df[mask].copy()
        logger.info(f"Selected {len(result)} funds for manager '{manager_name}'")
        return result

    def select_by_cnpj_list(self, cnpj_list: List[str]) -> pd.DataFrame:
        """Select funds by explicit CNPJ list.

        Args:
            cnpj_list: List of fund CNPJs to select

        Returns:
            DataFrame with the specified funds
        """
        if 'CNPJ_FUNDO' not in self.cadastro_df.columns:
            logger.error("CNPJ_FUNDO column not found in cadastro")
            return pd.DataFrame()

        # Normalize input CNPJs
        normalized_cnpjs = [normalize_cnpj(cnpj) for cnpj in cnpj_list]

        mask = self.cadastro_df['CNPJ_FUNDO'].isin(normalized_cnpjs)
        result = self.cadastro_df[mask].copy()

        found_count = len(result)
        not_found = set(normalized_cnpjs) - set(result['CNPJ_FUNDO'].unique())

        logger.info(f"Selected {found_count}/{len(cnpj_list)} funds by CNPJ")
        if not_found:
            logger.warning(f"{len(not_found)} CNPJs not found in cadastro")

        return result

    def select_all(self) -> pd.DataFrame:
        """Select all funds in the cadastro.

        Returns:
            Complete cadastro DataFrame
        """
        logger.info(f"Selected all {len(self.cadastro_df)} funds")
        return self.cadastro_df.copy()

    def select_active_only(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to only active funds.

        Args:
            df: DataFrame with fund data

        Returns:
            DataFrame with only active funds (SIT == 'EM FUNCIONAMENTO NORMAL')
        """
        if 'SIT' not in df.columns:
            logger.warning("SIT column not found, returning all funds")
            return df.copy()

        mask = df['SIT'] == 'EM FUNCIONAMENTO NORMAL'
        result = df[mask].copy()
        logger.info(f"Filtered to {len(result)} active funds (from {len(df)} total)")
        return result

    def get_selection_summary(self, selected_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary metadata about fund selection.

        Args:
            selected_df: DataFrame with selected funds

        Returns:
            Dictionary with selection metadata
        """
        summary = {
            'total_funds': len(selected_df),
            'unique_cnpjs': selected_df['CNPJ_FUNDO'].nunique() if 'CNPJ_FUNDO' in selected_df.columns else 0,
        }

        # Add administrator info if available
        if 'CNPJ_ADMIN' in selected_df.columns:
            summary['unique_administrators'] = selected_df['CNPJ_ADMIN'].nunique()

        if 'ADMIN' in selected_df.columns:
            summary['top_administrators'] = selected_df['ADMIN'].value_counts().head(5).to_dict()

        # Add status breakdown if available
        if 'SIT' in selected_df.columns:
            summary['status_breakdown'] = selected_df['SIT'].value_counts().to_dict()
            summary['active_funds'] = (selected_df['SIT'] == 'EM FUNCIONAMENTO NORMAL').sum()

        # Add manager info if available
        if 'GESTOR' in selected_df.columns:
            summary['unique_managers'] = selected_df['GESTOR'].nunique()

        return summary


# Convenience functions for common selection patterns

def select_funds_by_administrator(
    cadastro_df: pd.DataFrame,
    admin_name: str,
    active_only: bool = True
) -> pd.DataFrame:
    """Convenience function to select funds by administrator name.

    Args:
        cadastro_df: CVM cadastro DataFrame
        admin_name: Administrator name to search
        active_only: If True, return only active funds

    Returns:
        DataFrame with selected funds
    """
    selector = FundSelector(cadastro_df)
    result = selector.select_by_administrator(admin_name)

    if active_only:
        result = selector.select_active_only(result)

    return result


def select_funds_by_manager(
    cadastro_df: pd.DataFrame,
    manager_name: str,
    active_only: bool = True
) -> pd.DataFrame:
    """Convenience function to select funds by manager name.

    Args:
        cadastro_df: CVM cadastro DataFrame
        manager_name: Manager name to search
        active_only: If True, return only active funds

    Returns:
        DataFrame with selected funds
    """
    selector = FundSelector(cadastro_df)
    result = selector.select_by_manager(manager_name)

    if active_only:
        result = selector.select_active_only(result)

    return result


def select_funds_by_cnpj_list(
    cadastro_df: pd.DataFrame,
    cnpj_list: List[str]
) -> pd.DataFrame:
    """Convenience function to select funds by CNPJ list.

    Args:
        cadastro_df: CVM cadastro DataFrame
        cnpj_list: List of fund CNPJs

    Returns:
        DataFrame with selected funds
    """
    selector = FundSelector(cadastro_df)
    return selector.select_by_cnpj_list(cnpj_list)


def select_all_funds(cadastro_df: pd.DataFrame, active_only: bool = False) -> pd.DataFrame:
    """Convenience function to select all funds.

    Args:
        cadastro_df: CVM cadastro DataFrame
        active_only: If True, return only active funds

    Returns:
        DataFrame with all funds
    """
    selector = FundSelector(cadastro_df)
    result = selector.select_all()

    if active_only:
        result = selector.select_active_only(result)

    return result


def get_fund_selection_summary(
    cadastro_df: pd.DataFrame,
    selected_funds: pd.DataFrame
) -> Dict[str, Any]:
    """Get summary statistics about fund selection.

    Args:
        cadastro_df: Full CVM cadastro DataFrame
        selected_funds: DataFrame with selected funds

    Returns:
        Dictionary with selection statistics
    """
    selector = FundSelector(cadastro_df)
    summary = selector.get_selection_summary(selected_funds)
    summary['selection_percentage'] = (len(selected_funds) / len(cadastro_df) * 100) if len(cadastro_df) > 0 else 0
    return summary
