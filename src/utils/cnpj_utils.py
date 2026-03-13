"""
CNPJ normalization and validation utilities.

Centralizes CNPJ handling logic used across multiple modules.
"""
from typing import Any, List
import pandas as pd


def normalize_cnpj(cnpj: Any) -> str:
    """
    Normalize CNPJ to 14-digit string format.
    
    Args:
        cnpj: CNPJ in any format (string, int, with/without formatting)
        
    Returns:
        14-digit CNPJ string, or empty string if invalid
        
    Examples:
        >>> normalize_cnpj("12.345.678/0001-90")
        "12345678000190"
        >>> normalize_cnpj(12345678000190)
        "12345678000190"
    """
    if pd.isna(cnpj):
        return ""
    
    # Extract only digits
    digits = "".join(ch for ch in str(cnpj) if ch.isdigit())
    
    # Pad with zeros if needed
    if len(digits) < 14:
        digits = digits.zfill(14)
    
    return digits[:14]


def normalize_cnpj_series(series: pd.Series) -> pd.Series:
    """
    Normalize a pandas Series of CNPJs.
    
    Args:
        series: Series containing CNPJs in various formats
        
    Returns:
        Series with normalized 14-digit CNPJ strings
    """
    return series.apply(normalize_cnpj)


def normalize_cnpj_list(cnpj_list: List[str]) -> List[str]:
    """
    Normalize a list of CNPJs.
    
    Args:
        cnpj_list: List of CNPJs in various formats
        
    Returns:
        List of normalized 14-digit CNPJ strings
    """
    return [normalize_cnpj(cnpj) for cnpj in cnpj_list]


def is_valid_cnpj(cnpj: str) -> bool:
    """
    Check if CNPJ has valid format (14 digits).
    
    Note: Does not validate check digits.
    
    Args:
        cnpj: CNPJ string
        
    Returns:
        True if format is valid
    """
    normalized = normalize_cnpj(cnpj)
    return len(normalized) == 14 and normalized.isdigit()


def format_cnpj(cnpj: str) -> str:
    """
    Format CNPJ with standard punctuation: XX.XXX.XXX/XXXX-XX
    
    Args:
        cnpj: CNPJ string (normalized or not)
        
    Returns:
        Formatted CNPJ string
    """
    normalized = normalize_cnpj(cnpj)
    if len(normalized) != 14:
        return cnpj  # Return original if invalid
    
    return f"{normalized[:2]}.{normalized[2:5]}.{normalized[5:8]}/{normalized[8:12]}-{normalized[12:]}"
