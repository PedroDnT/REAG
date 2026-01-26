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


def test_normalization_is_idempotent():
    """Testa que normalização pode ser chamada múltiplas vezes sem efeito colateral"""
    processor = DataProcessor()
    
    # DataFrame com colunas não normalizadas
    df = pd.DataFrame({
        ' cnpj_fundo ': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'VL_TOTAL': [1000, 2000]
    })
    
    # Aplicar normalização múltiplas vezes
    df1 = processor._normalize_columns(df)
    df2 = processor._normalize_columns(df1)
    df3 = processor._normalize_columns(df2)
    
    # Todas devem ter as mesmas colunas normalizadas
    assert list(df1.columns) == list(df2.columns) == list(df3.columns)
    assert 'CNPJ_FUNDO' in df1.columns
    assert ' cnpj_fundo ' not in df1.columns


def test_chained_filters_work_correctly():
    """Testa que filtros podem ser encadeados sem problemas de performance/correção"""
    processor = DataProcessor()
    
    # DataFrame com múltiplas colunas CNPJ
    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10', '11.111.111/0001-11'],
        'CNPJ_ADMIN': ['22.222.222/0001-22', '22.222.222/0001-22', '33.333.333/0001-33'],
        'VL_TOTAL': [1000, 2000, 3000]
    })
    
    # Filtrar por administrador primeiro
    result1 = processor.filter_by_administrador(df, ['22.222.222/0001-22'])
    assert len(result1) == 2
    
    # Depois filtrar por CNPJ específico
    result2 = processor.filter_by_cnpj(result1, ['12.345.678/0001-90'])
    assert len(result2) == 1
    # Verificar que o filtro funcionou corretamente
    assert result2.iloc[0]['VL_TOTAL'] == 1000


def test_filter_handles_unnormalized_dataframes():
    """Testa que filtros funcionam com DataFrames não normalizados"""
    processor = DataProcessor()
    
    # DataFrame com espaços e BOM nas colunas
    df = pd.DataFrame({
        ' CNPJ_FUNDO ': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'VL_TOTAL': [1000, 2000]
    })
    
    result = processor.filter_by_cnpj(df, ['12.345.678/0001-90'])
    assert len(result) == 1
    # Verifica que a coluna foi normalizada no resultado
    assert 'CNPJ_FUNDO' in result.columns

