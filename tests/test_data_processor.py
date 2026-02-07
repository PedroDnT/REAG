"""Tests for the DataProcessor module."""

import pytest
import pandas as pd
from src.processors.data_processor import DataProcessor


@pytest.fixture
def processor():
    return DataProcessor()


def test_processor_initialization(processor):
    assert processor is not None
    assert processor.config is not None


def test_normalize_columns(processor):
    """_normalize_columns should uppercase and strip columns, remove BOM."""
    df = pd.DataFrame({" cnpj_fundo ": [1], "\ufeffVL_TOTAL": [2]})
    result = processor._normalize_columns(df)
    assert "CNPJ_FUNDO" in result.columns
    assert "VL_TOTAL" in result.columns


def test_apply_column_aliases(processor):
    """_apply_column_aliases should map known alternative column names."""
    df = pd.DataFrame({"CNPJ_FUNDO_CLASSE": ["123"], "VL_TOTAL": [100]})
    result = processor._apply_column_aliases(df)
    assert "CNPJ_FUNDO" in result.columns


def test_normalize_cnpj_series_formatted(processor):
    """_normalize_cnpj_series should strip formatting to 14 digits."""
    series = pd.Series(["12.345.678/0001-90", "98765432000110"])
    result = processor._normalize_cnpj_series(series)
    assert result.iloc[0] == "12345678000190"
    assert result.iloc[1] == "98765432000110"


def test_normalize_cnpj_series_preserves_na(processor):
    """_normalize_cnpj_series should preserve NaN values."""
    series = pd.Series(["12345678000190", None])
    result = processor._normalize_cnpj_series(series)
    assert result.iloc[0] == "12345678000190"
    assert pd.isna(result.iloc[1])


def test_normalize_cnpj_list(processor):
    """_normalize_cnpj_list should normalize a list of CNPJs."""
    result = processor._normalize_cnpj_list(["12.345.678/0001-90", "98765432000110"])
    assert result == ["12345678000190", "98765432000110"]


def test_normalize_cnpj_list_empty():
    """_normalize_cnpj_list should handle empty list."""
    result = DataProcessor._normalize_cnpj_list([])
    assert result == []


def test_coerce_numeric(processor):
    """_coerce_numeric should convert Brazilian number format."""
    df = pd.DataFrame({"VL_TOTAL": ["1.234,56", "789,01"]})
    result = processor._coerce_numeric(df, ["VL_TOTAL"])
    assert abs(result["VL_TOTAL"].iloc[0] - 1234.56) < 0.01
    assert abs(result["VL_TOTAL"].iloc[1] - 789.01) < 0.01


def test_coerce_numeric_already_numeric(processor):
    """_coerce_numeric should handle already-numeric columns."""
    df = pd.DataFrame({"VL_TOTAL": [1234.56, 789.01]})
    result = processor._coerce_numeric(df, ["VL_TOTAL"])
    assert abs(result["VL_TOTAL"].iloc[0] - 1234.56) < 0.01


def test_coerce_numeric_missing_column(processor):
    """_coerce_numeric should skip missing columns."""
    df = pd.DataFrame({"OTHER": [1, 2]})
    result = processor._coerce_numeric(df, ["VL_TOTAL"])
    assert "OTHER" in result.columns


def test_read_informe_diario_returns_dataframe(processor, tmp_path):
    """read_informe_diario should parse a CSV and return a DataFrame."""
    csv_content = "CNPJ_FUNDO;DT_COMPTC;VL_QUOTA;VL_PATRIM_LIQ\n"
    csv_content += "12.345.678/0001-90;2024-01-01;1,05;1000000\n"
    csv_content += "12.345.678/0001-90;2024-01-02;1,06;1010000\n"
    csv_file = tmp_path / "test_informe.csv"
    csv_file.write_text(csv_content, encoding="latin1")

    result = processor.read_informe_diario(csv_file)
    assert not result.empty
    assert len(result) == 2
    assert "CNPJ_FUNDO" in result.columns
    assert pd.api.types.is_datetime64_any_dtype(result["DT_COMPTC"])


def test_read_informe_diario_bad_path_returns_empty(processor, tmp_path):
    """read_informe_diario should return empty DataFrame for non-existent file."""
    result = processor.read_informe_diario(tmp_path / "nonexistent.csv")
    assert result.empty


def test_filter_by_cnpj(processor):
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["12.345.678/0001-90", "98.765.432/0001-10"],
        "VL_TOTAL": [1000, 2000],
    })
    result = processor.filter_by_cnpj(df, ["12.345.678/0001-90"])
    assert len(result) == 1


def test_filter_by_cnpj_normalized_match(processor):
    """Filtering should match regardless of CNPJ formatting."""
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["12345678000190"],
        "VL_TOTAL": [1000],
    })
    result = processor.filter_by_cnpj(df, ["12.345.678/0001-90"])
    assert len(result) == 1


def test_filter_by_cnpj_missing_column(processor):
    """Should return empty DataFrame if CNPJ_FUNDO column missing."""
    df = pd.DataFrame({"OTHER": [1, 2]})
    result = processor.filter_by_cnpj(df, ["12345678000190"])
    assert result.empty


def test_filter_by_administrador(processor):
    df = pd.DataFrame({
        "CNPJ_ADMIN": ["12345678000190", "98765432000110"],
        "VL_TOTAL": [1000, 2000],
    })
    result = processor.filter_by_administrador(df, ["12345678000190"])
    assert len(result) == 1


def test_filter_by_gestor(processor):
    df = pd.DataFrame({
        "CNPJ_GESTOR": ["12345678000190", "98765432000110"],
        "VL_TOTAL": [1000, 2000],
    })
    result = processor.filter_by_gestor(df, ["12345678000190"])
    assert len(result) == 1


def test_calculate_net_flow(processor):
    df = pd.DataFrame({"CAPTC_DIA": [100, 200], "RESG_DIA": [50, 300]})
    result = processor.calculate_net_flow(df)
    assert "FLUXO_LIQ_DIA" in result.columns
    assert result["FLUXO_LIQ_DIA"].iloc[0] == 50
    assert result["FLUXO_LIQ_DIA"].iloc[1] == -100


def test_calculate_net_flow_missing_columns(processor):
    """Should return DataFrame unchanged if columns are missing."""
    df = pd.DataFrame({"OTHER": [1, 2]})
    result = processor.calculate_net_flow(df)
    assert "FLUXO_LIQ_DIA" not in result.columns


def test_filter_by_date_range(processor):
    df = pd.DataFrame({
        "DT_COMPTC": pd.to_datetime(["2024-01-01", "2024-06-01", "2024-12-01"]),
        "VL_TOTAL": [1, 2, 3],
    })
    result = processor.filter_by_date_range(df, "2024-01-01", "2024-06-30")
    assert len(result) == 2


def test_aggregate_by_fund(processor):
    df = pd.DataFrame({
        "CNPJ_FUNDO": ["F1", "F1", "F2"],
        "VL_TOTAL": [100, 200, 300],
        "VL_PATRIM_LIQ": [1000, 1100, 2000],
    })
    result = processor.aggregate_by_fund(df)
    assert len(result) == 2
