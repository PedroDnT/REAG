"""Tests for the data validation utilities module."""

import pytest
import pandas as pd
from datetime import datetime
from src.utils.validation import (
    validate_dataframe,
    validate_cnpj,
    validate_date,
    validate_numeric,
    validate_percentage,
)


# ---------------------------------------------------------------------------
# validate_dataframe
# ---------------------------------------------------------------------------

class TestValidateDataframe:
    def test_valid_dataframe_passes(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        validate_dataframe(df, ["A", "B"])  # Should not raise

    def test_empty_dataframe_raises(self):
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="is empty"):
            validate_dataframe(df, ["A"])

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ValueError, match="missing required columns"):
            validate_dataframe(df, ["A", "B", "C"])

    def test_custom_name_in_error(self):
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ValueError, match="MyData"):
            validate_dataframe(df, ["X"], name="MyData")

    def test_all_columns_present(self):
        df = pd.DataFrame({"X": [1], "Y": [2], "Z": [3]})
        validate_dataframe(df, ["X", "Z"])  # Should not raise


# ---------------------------------------------------------------------------
# validate_cnpj
# ---------------------------------------------------------------------------

class TestValidateCnpj:
    @pytest.mark.parametrize("cnpj,expected", [
        ("12.345.678/0001-90", True),
        ("12345678000190", True),
        ("11.111.111/1111-11", False),  # All same digits after stripping
        ("00000000000000", False),  # All zeros
        ("11111111111111", False),  # All same digits
        ("123", False),            # Too short
        ("", False),               # Empty string
    ])
    def test_valid_cnpj_formats(self, cnpj, expected):
        assert validate_cnpj(cnpj) is expected

    def test_none_returns_false(self):
        assert validate_cnpj(None) is False

    def test_non_string_returns_false(self):
        assert validate_cnpj(12345678000190) is False


# ---------------------------------------------------------------------------
# validate_date
# ---------------------------------------------------------------------------

class TestValidateDate:
    def test_valid_datetime(self):
        assert validate_date(datetime(2024, 1, 1)) is True

    def test_valid_string(self):
        assert validate_date("2024-01-01") is True

    def test_invalid_string(self):
        assert validate_date("not-a-date") is False

    def test_none_returns_false(self):
        assert validate_date(None) is False

    def test_min_date_boundary(self):
        assert validate_date(
            datetime(2024, 1, 1),
            min_date=datetime(2024, 6, 1),
        ) is False

    def test_max_date_boundary(self):
        assert validate_date(
            datetime(2024, 12, 1),
            max_date=datetime(2024, 6, 1),
        ) is False

    def test_date_within_range(self):
        assert validate_date(
            datetime(2024, 6, 1),
            min_date=datetime(2024, 1, 1),
            max_date=datetime(2024, 12, 31),
        ) is True

    def test_pd_timestamp(self):
        assert validate_date(pd.Timestamp("2024-01-01")) is True


# ---------------------------------------------------------------------------
# validate_numeric
# ---------------------------------------------------------------------------

class TestValidateNumeric:
    @pytest.mark.parametrize("value,kwargs,expected", [
        (42, {}, True),
        (0, {}, True),
        (-5, {}, True),
        ("42.5", {}, True),
        ("abc", {}, False),
        (None, {}, False),
        (-5, {"allow_negative": False}, False),
        (5, {"min_value": 10}, False),
        (5, {"max_value": 3}, False),
        (float("nan"), {}, False),
        (float("inf"), {}, True),  # inf is numeric, just extreme
    ])
    def test_validate_numeric(self, value, kwargs, expected):
        assert validate_numeric(value, **kwargs) is expected


# ---------------------------------------------------------------------------
# validate_percentage
# ---------------------------------------------------------------------------

class TestValidatePercentage:
    @pytest.mark.parametrize("value,expected", [
        (50, True),
        (0, True),
        (100, True),
        (-1, False),
        (101, False),
        ("abc", False),
        (None, False),
    ])
    def test_validate_percentage(self, value, expected):
        assert validate_percentage(value) is expected
