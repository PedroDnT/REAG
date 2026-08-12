"""
CNPJ normalization and validation utilities.

This module is the single source of truth for CNPJ handling. CNPJ is the join
key between every CVM dataset the toolkit reads (informe diário, CDA, cadastro),
so any disagreement between normalizers silently produces mismatched joins:
findings attributed to the wrong fund, or not found at all.

Normalization rules:

- Only digits are considered; punctuation and whitespace are stripped.
- Fewer than 14 digits is left-padded with zeros. CVM exports routinely drop
  leading zeros, and padding recovers the original identifier.
- More than 14 digits is *rejected*, never truncated. Truncating turns a
  malformed value into a different, valid-looking CNPJ.
- Blank, missing, or digit-free input is rejected.

Rejection is represented as ``None`` for scalars and ``pd.NA`` for Series, so
bad input stays distinguishable from a real fund instead of collapsing into a
sentinel like ``"00000000000000"``.
"""
from typing import Any

import pandas as pd

CNPJ_LENGTH = 14

# Only ASCII 0-9 count. str.isdigit() also accepts superscripts and other
# Unicode digit characters ('¹'.isdigit() is True), which would sail through the
# scalar path while the vectorized regex strips them -- exactly the kind of
# silent divergence between code paths this module exists to prevent.
_ASCII_DIGITS = frozenset("0123456789")


def normalize_cnpj(cnpj: Any) -> str | None:
    """
    Normalize a CNPJ to its canonical 14-digit string form.

    Args:
        cnpj: CNPJ in any format (string, int, with or without punctuation)

    Returns:
        14-digit CNPJ string, or None if the value cannot be a CNPJ

    Examples:
        >>> normalize_cnpj("12.345.678/0001-90")
        '12345678000190'
        >>> normalize_cnpj(12345678000190)
        '12345678000190'
        >>> normalize_cnpj("123456780001901234") is None  # too long, not truncated
        True
        >>> normalize_cnpj("") is None
        True
    """
    if cnpj is None:
        return None

    try:
        if pd.isna(cnpj):
            return None
    except (TypeError, ValueError):
        # pd.isna raises on some array-likes; those are not scalars we can use.
        return None

    digits = "".join(ch for ch in str(cnpj) if ch in _ASCII_DIGITS)

    if not digits or len(digits) > CNPJ_LENGTH:
        return None

    return digits.zfill(CNPJ_LENGTH)


def normalize_cnpj_series(series: pd.Series) -> pd.Series:
    """
    Normalize a pandas Series of CNPJs, vectorized.

    Args:
        series: Series containing CNPJs in various formats

    Returns:
        Series of nullable ``string`` dtype holding 14-digit CNPJs, with pd.NA
        wherever the input could not be a CNPJ
    """
    if len(series) == 0:
        return pd.Series([], dtype="string")

    digits = series.astype("string").str.replace(r"[^0-9]", "", regex=True)

    valid = digits.notna() & (digits.str.len() > 0) & (digits.str.len() <= CNPJ_LENGTH)

    return digits.str.zfill(CNPJ_LENGTH).where(valid, pd.NA).astype("string")


def normalize_cnpj_list(cnpj_list: list[Any]) -> list[str]:
    """
    Normalize a list of CNPJs, dropping values that cannot be a CNPJ.

    Args:
        cnpj_list: List of CNPJs in various formats

    Returns:
        List of normalized 14-digit CNPJ strings
    """
    if not cnpj_list:
        return []

    normalized = (normalize_cnpj(value) for value in cnpj_list)
    return [value for value in normalized if value is not None]


def is_valid_cnpj(cnpj: Any) -> bool:
    """
    Check whether a value is a structurally valid CNPJ.

    Validates shape only: 14 digits, not all the same digit. Check digits are
    not verified, so a well-formed but non-existent CNPJ passes.

    Args:
        cnpj: CNPJ in any format

    Returns:
        True if the value normalizes to a structurally valid CNPJ
    """
    normalized = normalize_cnpj(cnpj)

    if normalized is None:
        return False

    # Repeated-digit strings ("00000000000000", "11111111111111") are the
    # canonical placeholder values in CVM exports, never real registrations.
    return normalized != normalized[0] * CNPJ_LENGTH


def format_cnpj(cnpj: Any) -> str:
    """
    Format a CNPJ with standard punctuation: XX.XXX.XXX/XXXX-XX

    Args:
        cnpj: CNPJ in any format

    Returns:
        Formatted CNPJ string, or the input unchanged (as a string) if it
        cannot be normalized
    """
    normalized = normalize_cnpj(cnpj)

    if normalized is None:
        return "" if cnpj is None else str(cnpj)

    return (
        f"{normalized[:2]}.{normalized[2:5]}.{normalized[5:8]}"
        f"/{normalized[8:12]}-{normalized[12:]}"
    )
