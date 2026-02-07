"""
Data validation utilities.
"""

import pandas as pd
import re
from typing import List, Optional
from datetime import datetime


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: List[str],
    name: str = "DataFrame"
) -> None:
    """
    Validate that a DataFrame has required columns.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        name: Name of the DataFrame for error messages

    Raises:
        ValueError: If DataFrame is empty or missing required columns
    """
    if df.empty:
        raise ValueError(f"{name} is empty")

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            f"{name} is missing required columns: {missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


def validate_cnpj(cnpj: str) -> bool:
    """
    Validate Brazilian CNPJ format.

    Args:
        cnpj: CNPJ string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not cnpj or not isinstance(cnpj, str):
        return False

    # Remove formatting
    cnpj_clean = re.sub(r'[^\d]', '', cnpj)

    # Must have 14 digits
    if len(cnpj_clean) != 14:
        return False

    # Check if all digits are the same (invalid)
    if cnpj_clean == cnpj_clean[0] * 14:
        return False

    return True


def validate_date(
    date_value: 'Union[str, datetime, pd.Timestamp]',
    min_date: Optional[datetime] = None,
    max_date: Optional[datetime] = None
) -> bool:
    """
    Validate a date value.

    Args:
        date_value: Date to validate (datetime, str, or pd.Timestamp)
        min_date: Minimum allowed date (optional)
        max_date: Maximum allowed date (optional)

    Returns:
        True if valid, False otherwise
    """
    try:
        # Convert to datetime if needed
        if isinstance(date_value, str):
            dt = pd.to_datetime(date_value)
        elif isinstance(date_value, pd.Timestamp):
            dt = date_value.to_pydatetime()
        elif isinstance(date_value, datetime):
            dt = date_value
        else:
            return False

        # Check bounds
        if min_date and dt < min_date:
            return False
        if max_date and dt > max_date:
            return False

        return True

    except (ValueError, TypeError):
        return False


def validate_numeric(
    value,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_negative: bool = True
) -> bool:
    """
    Validate a numeric value.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        allow_negative: Whether to allow negative values

    Returns:
        True if valid, False otherwise
    """
    try:
        num = float(value)

        if pd.isna(num):
            return False

        if not allow_negative and num < 0:
            return False

        if min_value is not None and num < min_value:
            return False

        if max_value is not None and num > max_value:
            return False

        return True

    except (ValueError, TypeError):
        return False


def validate_percentage(value) -> bool:
    """
    Validate that a value is a valid percentage (0-100).

    Args:
        value: Value to validate

    Returns:
        True if valid percentage, False otherwise
    """
    return validate_numeric(value, min_value=0, max_value=100, allow_negative=False)
