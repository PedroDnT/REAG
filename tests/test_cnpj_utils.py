"""Tests for CNPJ utilities."""
import pandas as pd
import pytest
from src.utils.cnpj_utils import (
    normalize_cnpj,
    normalize_cnpj_series,
    normalize_cnpj_list,
    is_valid_cnpj,
    format_cnpj,
)


class TestNormalizeCNPJ:
    """Test CNPJ normalization functions."""

    def test_normalize_formatted_cnpj(self):
        """Test normalizing a formatted CNPJ string."""
        result = normalize_cnpj("12.345.678/0001-90")
        assert result == "12345678000190"

    def test_normalize_unformatted_cnpj(self):
        """Test normalizing an unformatted CNPJ string."""
        result = normalize_cnpj("12345678000190")
        assert result == "12345678000190"

    def test_normalize_integer_cnpj(self):
        """Test normalizing a CNPJ as integer."""
        result = normalize_cnpj(12345678000190)
        assert result == "12345678000190"

    def test_normalize_short_cnpj_with_padding(self):
        """Test normalizing a short CNPJ with zero padding."""
        result = normalize_cnpj("123456780001")
        assert result == "00123456780001"

    def test_normalize_cnpj_with_extra_characters(self):
        """Test normalizing a CNPJ with extra non-digit characters."""
        result = normalize_cnpj("12.345.678/0001-90-XX")
        assert result == "12345678000190"

    def test_normalize_na_value(self):
        """Missing values are rejected, not coerced to a sentinel."""
        assert normalize_cnpj(None) is None
        assert normalize_cnpj(pd.NA) is None

    def test_normalize_empty_string(self):
        """An empty string is not a fund.

        This used to return "00000000000000", so every blank cell in a CVM
        export collapsed into one synthetic fund that joins would then group
        together.
        """
        assert normalize_cnpj("") is None
        assert normalize_cnpj("   ") is None

    def test_normalize_rejects_long_cnpj_instead_of_truncating(self):
        """Over-length input is rejected, never cut down to 14 digits.

        Truncating turned a malformed value into a different, valid-looking
        CNPJ -- silently reattributing findings to another fund.
        """
        assert normalize_cnpj("123456780001901234") is None

    def test_normalize_rejects_digit_free_input(self):
        assert normalize_cnpj("ABCDEFGHIJKLMN") is None


class TestNormalizeCNPJSeries:
    """Test CNPJ series normalization."""

    def test_normalize_series_of_cnpjs(self):
        """Test normalizing a pandas Series of CNPJs."""
        series = pd.Series([
            "12.345.678/0001-90",
            "98.765.432/0001-10",
            12345678000190
        ])
        result = normalize_cnpj_series(series)
        expected = pd.Series([
            "12345678000190",
            "98765432000110",
            "12345678000190"
        ], dtype="string")
        pd.testing.assert_series_equal(result, expected)

    def test_normalize_series_with_na_values(self):
        """Missing values stay missing rather than becoming a synthetic CNPJ."""
        series = pd.Series(["12.345.678/0001-90", None, "98.765.432/0001-10"])
        result = normalize_cnpj_series(series)
        assert result[0] == "12345678000190"
        assert pd.isna(result[1])
        assert result[2] == "98765432000110"

    def test_normalize_series_rejects_unusable_values(self):
        """Blank, digit-free and over-length entries become NA, not fake funds."""
        series = pd.Series(["", "ABC", "123456780001901234", "12345678000190"])
        result = normalize_cnpj_series(series)
        assert pd.isna(result[0])
        assert pd.isna(result[1])
        assert pd.isna(result[2])
        assert result[3] == "12345678000190"

    def test_normalize_empty_series(self):
        """Test normalizing an empty Series."""
        series = pd.Series([], dtype=object)
        result = normalize_cnpj_series(series)
        assert len(result) == 0


class TestNormalizeCNPJList:
    """Test CNPJ list normalization."""

    def test_normalize_list_of_cnpjs(self):
        """Test normalizing a list of CNPJs."""
        cnpj_list = [
            "12.345.678/0001-90",
            "98.765.432/0001-10",
            12345678000190
        ]
        result = normalize_cnpj_list(cnpj_list)
        expected = [
            "12345678000190",
            "98765432000110",
            "12345678000190"
        ]
        assert result == expected

    def test_normalize_empty_list(self):
        """Test normalizing an empty list."""
        result = normalize_cnpj_list([])
        assert result == []

    def test_normalize_list_with_mixed_formats(self):
        """Test normalizing a list with mixed CNPJ formats."""
        cnpj_list = [
            "12345678000190",  # Unformatted
            "12.345.678/0001-90",  # Formatted
            123456780001,  # Integer (short)
        ]
        result = normalize_cnpj_list(cnpj_list)
        assert result[0] == "12345678000190"
        assert result[1] == "12345678000190"
        assert result[2] == "00123456780001"


class TestIsValidCNPJ:
    """Test CNPJ validation."""

    def test_valid_cnpj_string(self):
        """Test validation of a valid CNPJ string."""
        assert is_valid_cnpj("12345678000190") is True

    def test_valid_formatted_cnpj(self):
        """Test validation of a formatted valid CNPJ."""
        assert is_valid_cnpj("12.345.678/0001-90") is True

    def test_invalid_short_cnpj(self):
        """Test validation of a short invalid CNPJ."""
        # Short CNPJs get zero-padded to 14 digits, so they're valid format
        # This test is about format, not actual CNPJ validity
        assert is_valid_cnpj("123456") is True  # Gets padded to "00000000123456"

    def test_invalid_long_cnpj(self):
        """Over-length input is invalid; it is not truncated into validity."""
        assert is_valid_cnpj("123456780001901234") is False

    def test_invalid_non_numeric_cnpj(self):
        """Digit-free input is invalid, not "00000000000000"."""
        assert is_valid_cnpj("ABCDEFGHIJKLMN") is False

    def test_invalid_empty_cnpj(self):
        """An empty CNPJ is invalid."""
        assert is_valid_cnpj("") is False

    def test_repeated_digit_cnpj_is_invalid(self):
        """Placeholder registrations are rejected, matching validate_cnpj."""
        assert is_valid_cnpj("00000000000000") is False
        assert is_valid_cnpj("11111111111111") is False

    def test_invalid_none_cnpj(self):
        """Test validation of None."""
        assert is_valid_cnpj(None) is False


class TestFormatCNPJ:
    """Test CNPJ formatting."""

    def test_format_unformatted_cnpj(self):
        """Test formatting an unformatted CNPJ."""
        result = format_cnpj("12345678000190")
        assert result == "12.345.678/0001-90"

    def test_format_already_formatted_cnpj(self):
        """Test formatting an already formatted CNPJ."""
        result = format_cnpj("12.345.678/0001-90")
        assert result == "12.345.678/0001-90"

    def test_format_integer_cnpj(self):
        """Test formatting an integer CNPJ."""
        result = format_cnpj(12345678000190)
        assert result == "12.345.678/0001-90"

    def test_format_short_cnpj(self):
        """Test formatting a short CNPJ (with padding)."""
        result = format_cnpj("123456780001")
        assert result == "00.123.456/7800-01"

    def test_format_invalid_cnpj_returns_original(self):
        """Test that formatting invalid CNPJ returns the normalized value."""
        # Very short CNPJs get padded but the format still applies
        result = format_cnpj("12")
        assert result == "00.000.000/0000-12"

    def test_format_empty_cnpj(self):
        """An unusable value is returned unchanged, not formatted into a fake CNPJ."""
        assert format_cnpj("") == ""
        assert format_cnpj("123456780001901234") == "123456780001901234"


# ---------------------------------------------------------------------------
# Property-based tests
#
# CNPJ is the join key across every CVM dataset, so these properties guard the
# invariants that four divergent normalizers used to violate.
# ---------------------------------------------------------------------------

from hypothesis import given, strategies as st


digit_strings = st.text(alphabet="0123456789", min_size=1, max_size=14)
any_strings = st.text(max_size=30)


class TestNormalizeProperties:

    @given(digit_strings)
    def test_output_is_always_14_digits_or_none(self, value):
        result = normalize_cnpj(value)
        assert result is not None
        assert len(result) == 14
        assert result.isdigit()

    @given(any_strings)
    def test_never_truncates(self, value):
        """More than 14 digits must never yield a 14-digit answer."""
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) > 14:
            assert normalize_cnpj(value) is None

    @given(any_strings)
    def test_idempotent(self, value):
        once = normalize_cnpj(value)
        assert normalize_cnpj(once) == once

    @given(digit_strings)
    def test_format_round_trips(self, value):
        """format_cnpj then normalize_cnpj returns the normalized original."""
        normalized = normalize_cnpj(value)
        assert normalize_cnpj(format_cnpj(normalized)) == normalized

    @given(any_strings)
    def test_punctuation_is_irrelevant(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        assert normalize_cnpj(value) == normalize_cnpj(digits)

    @given(any_strings)
    def test_validity_implies_normalizable(self, value):
        if is_valid_cnpj(value):
            assert normalize_cnpj(value) is not None

    @given(st.lists(any_strings, max_size=20))
    def test_series_matches_scalar(self, values):
        """The vectorized path must agree with the scalar one, element-wise."""
        series_result = normalize_cnpj_series(pd.Series(values, dtype="object"))
        for i, value in enumerate(values):
            scalar = normalize_cnpj(value)
            if scalar is None:
                assert pd.isna(series_result.iloc[i])
            else:
                assert series_result.iloc[i] == scalar

    @given(st.lists(any_strings, max_size=20))
    def test_list_matches_scalar(self, values):
        expected = [normalize_cnpj(v) for v in values]
        assert normalize_cnpj_list(values) == [v for v in expected if v is not None]
