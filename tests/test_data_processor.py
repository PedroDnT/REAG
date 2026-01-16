import pytest
import pandas as pd
from src.processors.data_processor import DataProcessor


def test_processor_initialization():
    processor = DataProcessor()
    assert processor is not None


def test_read_informe_diario_csv():
    processor = DataProcessor()
    # Mock test - verificar se método existe
    assert hasattr(processor, 'read_informe_diario')


def test_filter_by_cnpj():
    processor = DataProcessor()
    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'VL_TOTAL': [1000, 2000]
    })

    result = processor.filter_by_cnpj(df, ['12.345.678/0001-90'])
    assert len(result) == 1
    assert result.iloc[0]['CNPJ_FUNDO'] == '12.345.678/0001-90'
