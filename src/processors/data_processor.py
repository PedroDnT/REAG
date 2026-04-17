import logging

import pandas as pd
from pathlib import Path
from typing import Optional, List
from config.settings import Config

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processador de dados da CVM (leitura, limpeza, transformação)"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Padroniza nomes de colunas removendo espaços e BOM."""
        df = df.copy()
        df.columns = (
            df.columns.astype(str)
            .str.replace('\ufeff', '', regex=False)
            .str.replace('ï»¿', '', regex=False)
            .str.replace('\xa0', '', regex=False)
            .str.strip()
            .str.upper()
        )
        return df

    @staticmethod
    def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
        """Aplica aliases conhecidos para nomes de colunas padrão."""
        df = df.copy()
        aliases = {
            'CNPJ_FUNDO': ['CNPJ_FUNDO_CLASSE'],
            'DT_COMPTC': ['DT_COMPTC_CLASSE'],
        }

        for target, alternatives in aliases.items():
            if target in df.columns:
                continue
            for alt in alternatives:
                if alt in df.columns:
                    df[target] = df[alt]
                    break

        return df

    # Translation table for Brazilian number format (created once, reused)
    _BRAZILIAN_NUMBER_TRANS = str.maketrans({'.': '', ',': '.'})
    
    @staticmethod
    def _coerce_numeric(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Converte colunas numéricas tratando separadores brasileiros."""
        df = df.copy()
        for col in columns:
            if col not in df.columns:
                continue
            series = df[col]
            if pd.api.types.is_string_dtype(series) or series.dtype == object:
                # Use str.translate for faster simultaneous replacements
                cleaned = series.astype(str).str.translate(DataProcessor._BRAZILIAN_NUMBER_TRANS)
                df[col] = pd.to_numeric(cleaned, errors='coerce')
            else:
                df[col] = pd.to_numeric(series, errors='coerce')
        return df

    @staticmethod
    def _normalize_cnpj_series(series: pd.Series) -> pd.Series:
        """Normaliza CNPJ removendo pontuação e preservando NAs.

        Converte CNPJs para formato padronizado de 14 dígitos, removendo
        pontuação e preenchendo com zeros à esquerda quando necessário.
        CNPJs já formatados corretamente (14 dígitos numéricos) não são
        reprocessados para melhor performance.

        Args:
            series: Série pandas contendo CNPJs em diversos formatos

        Returns:
            Série pandas com CNPJs normalizados (14 dígitos) ou NAs preservados

        Note:
            Requer pandas >= 1.0.0 para suporte ao dtype 'string'.
            O projeto atualmente requer pandas >= 2.0.0.
        """
        # Convert to string type
        str_series = series.astype('string')

        # Check if values are already properly formatted (14 digits only)
        # to avoid unnecessary reprocessing
        is_already_formatted = (
            str_series.str.match(r'^\d{14}$', na=False)
        )

        # Only process values that need normalization
        needs_processing = ~is_already_formatted & str_series.notna()

        result = str_series.copy()
        if needs_processing.any():
            # Remove non-digit characters and pad with zeros
            to_process = str_series[needs_processing]
            cleaned = to_process.str.replace(r'\D', '', regex=True)
            # Filter out empty strings
            cleaned = cleaned.where(cleaned.str.len() > 0)
            # Pad with zeros to 14 digits
            result[needs_processing] = cleaned.str.zfill(14)

        return result

    @classmethod
    def _normalize_cnpj_list(cls, cnpj_list: List[str]) -> List[str]:
        """Normaliza lista de CNPJs para comparação consistente."""
        if not cnpj_list:
            return []
        series = pd.Series(cnpj_list, dtype='string')
        normalized = cls._normalize_cnpj_series(series).dropna()
        return normalized.tolist()
    def _read_csv_generic(self, 
                         file_path: Path,
                         file_type: str,
                         encoding: str = 'latin1',
                         sep: str = ';',
                         date_cols: Optional[List[str]] = None,
                         cnpj_cols: Optional[List[str]] = None,
                         numeric_cols: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Generic CSV reader with common transformations.
        
        Consolidates duplicate logic from read_informe_diario, read_cda, and read_cadastro.
        
        Args:
            file_path: Path to CSV file
            file_type: Type of file for logging (e.g., "Informe Diario", "CDA", "Cadastro")
            encoding: File encoding
            sep: CSV separator
            date_cols: List of date columns to parse
            cnpj_cols: List of CNPJ columns to normalize
            numeric_cols: List of numeric columns to coerce
            
        Returns:
            Processed DataFrame or empty DataFrame on error
        """
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep)
            
            # Padronizar nomes de colunas
            df = self._normalize_columns(df)
            df = self._apply_column_aliases(df)
            
            # Converter datas
            if date_cols:
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], format='%Y-%m-%d', errors='coerce')
            
            # Normalizar CNPJs
            if cnpj_cols:
                for col in cnpj_cols:
                    if col in df.columns:
                        df[col] = self._normalize_cnpj_series(df[col])
            
            # Converter valores numéricos
            if numeric_cols:
                df = self._coerce_numeric(df, numeric_cols)
            
            return df
        except Exception as e:
            logger.error(f"Erro ao ler {file_type} {file_path}: {e}")
            return pd.DataFrame()
    
    def read_informe_diario(self, file_path: Path,
                           encoding: str = 'latin1',
                           sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de Informe Diário"""
        return self._read_csv_generic(
            file_path=file_path,
            file_type="Informe Diario",
            encoding=encoding,
            sep=sep,
            date_cols=['DT_COMPTC'],
            cnpj_cols=['CNPJ_FUNDO'],
            numeric_cols=['VL_TOTAL', 'VL_QUOTA', 'VL_PATRIM_LIQ', 'CAPTC_DIA', 'RESG_DIA', 'NR_COTST']
        )
    
    def read_cda(self, file_path: Path,
                 encoding: str = 'latin1',
                 sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de CDA (Composição de Carteira)"""
        return self._read_csv_generic(
            file_path=file_path,
            file_type="CDA",
            encoding=encoding,
            sep=sep,
            date_cols=['DT_COMPTC'],
            cnpj_cols=['CNPJ_FUNDO'],
            numeric_cols=['VL_MERC_POS_FINAL', 'QT_POS_FINAL', 'VL_CUSTO_POS_FINAL']
        )
    
    def read_cadastro(self, file_path: Path,
                     encoding: str = 'latin1',
                     sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de Cadastro de Fundos"""
        return self._read_csv_generic(
            file_path=file_path,
            file_type="Cadastro",
            encoding=encoding,
            sep=sep,
            date_cols=['DT_REG', 'DT_CONST', 'DT_CANCEL', 'DT_INI_SIT', 'DT_INI_ATIV', 'DT_INI_EXERC', 'DT_FIM_EXERC'],
            cnpj_cols=['CNPJ_FUNDO', 'CNPJ_ADMIN', 'CNPJ_GESTOR'],
            numeric_cols=None
        )

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepares DataFrame by normalizing columns and applying aliases.
        This is a helper to avoid duplicate normalization in filter methods.
        """
        df = self._normalize_columns(df)
        df = self._apply_column_aliases(df)
        return df

    def filter_by_cnpj(self, df: pd.DataFrame, cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por lista de CNPJs"""
        df = self._prepare_dataframe(df)
        if 'CNPJ_FUNDO' not in df.columns:
            return pd.DataFrame()

        normalized_list = self._normalize_cnpj_list(cnpj_list)
        normalized_series = self._normalize_cnpj_series(df['CNPJ_FUNDO'])
        return df[normalized_series.isin(normalized_list)].copy()

    def filter_by_administrador(self, df: pd.DataFrame, admin_cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por CNPJ do administrador"""
        df = self._prepare_dataframe(df)
        if 'CNPJ_ADMIN' not in df.columns:
            return pd.DataFrame()

        normalized_list = self._normalize_cnpj_list(admin_cnpj_list)
        normalized_series = self._normalize_cnpj_series(df['CNPJ_ADMIN'])
        return df[normalized_series.isin(normalized_list)].copy()

    def filter_by_gestor(self, df: pd.DataFrame, gestor_cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por CNPJ do gestor"""
        df = self._prepare_dataframe(df)
        if 'CNPJ_GESTOR' not in df.columns:
            return pd.DataFrame()

        normalized_list = self._normalize_cnpj_list(gestor_cnpj_list)
        normalized_series = self._normalize_cnpj_series(df['CNPJ_GESTOR'])
        return df[normalized_series.isin(normalized_list)].copy()

    def filter_by_date_range(self, df: pd.DataFrame,
                            start_date: str,
                            end_date: str,
                            date_col: str = 'DT_COMPTC') -> pd.DataFrame:
        """Filtra DataFrame por intervalo de datas"""
        df = self._prepare_dataframe(df)
        if date_col not in df.columns:
            return pd.DataFrame()

        mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
        return df[mask].copy()

    def calculate_net_flow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula fluxo líquido (captação - resgate)"""
        if 'CAPTC_DIA' in df.columns and 'RESG_DIA' in df.columns:
            df = df.copy()
            df['FLUXO_LIQ_DIA'] = df['CAPTC_DIA'] - df['RESG_DIA']
        return df

    def aggregate_by_fund(self, df: pd.DataFrame,
                         agg_dict: Optional[dict] = None) -> pd.DataFrame:
        """Agrega dados por fundo"""
        if agg_dict is None:
            agg_dict = {
                'VL_TOTAL': 'sum',
                'VL_PATRIM_LIQ': 'last',
                'CAPTC_DIA': 'sum',
                'RESG_DIA': 'sum',
                'FLUXO_LIQ_DIA': 'sum',
                'NR_COTST': 'last'
            }

        # Filtrar apenas colunas que existem
        valid_agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

        if 'CNPJ_FUNDO' in df.columns:
            return df.groupby('CNPJ_FUNDO').agg(valid_agg_dict).reset_index()

        return df

    def save_processed(self, df: pd.DataFrame, filename: str):
        """Salva dados processados"""
        output_path = self.config.PROCESSED_DATA_DIR / filename
        df.to_csv(output_path, index=False, encoding='utf-8', sep=';')
        logger.info(f"Dados salvos em: {output_path}")
        return output_path

    def filter_by_fund_list(self, df: pd.DataFrame, cnpj_list: List[str]) -> pd.DataFrame:
        """
        Filter DataFrame by fund CNPJ list.

        Alias for filter_by_cnpj for consistency with new fund selector terminology.

        Args:
            df: DataFrame to filter
            cnpj_list: List of fund CNPJs

        Returns:
            Filtered DataFrame
        """
        return self.filter_by_cnpj(df, cnpj_list)

    def get_fund_metadata(self, cadastro_df: pd.DataFrame, cnpj_list: List[str]) -> pd.DataFrame:
        """
        Extract fund metadata for specified CNPJs.

        Args:
            cadastro_df: Cadastro DataFrame
            cnpj_list: List of fund CNPJs

        Returns:
            DataFrame with fund metadata (name, status, administrator, etc.)
        """
        filtered = self.filter_by_cnpj(cadastro_df, cnpj_list)

        # Select relevant columns if they exist
        metadata_cols = ['CNPJ_FUNDO', 'DENOM_SOCIAL', 'SIT', 'CNPJ_ADMIN', 'ADMIN',
                        'CNPJ_GESTOR', 'GESTOR', 'TP_FUNDO', 'CLASSE']
        available_cols = [col for col in metadata_cols if col in filtered.columns]

        if available_cols:
            return filtered[available_cols].copy()
        return filtered

    def merge_fund_metadata(self, df: pd.DataFrame, cadastro_df: pd.DataFrame,
                           cols_to_merge: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Enrich DataFrame with fund metadata from cadastro.

        Args:
            df: DataFrame to enrich (must have CNPJ_FUNDO column)
            cadastro_df: Cadastro DataFrame with fund metadata
            cols_to_merge: Specific columns to merge. If None, merges common useful columns.

        Returns:
            Enriched DataFrame with metadata
        """
        if 'CNPJ_FUNDO' not in df.columns or 'CNPJ_FUNDO' not in cadastro_df.columns:
            logger.warning("CNPJ_FUNDO column missing, cannot merge metadata")
            return df.copy()

        # Default columns to merge
        if cols_to_merge is None:
            cols_to_merge = ['DENOM_SOCIAL', 'SIT', 'ADMIN', 'GESTOR']

        # Filter to only available columns
        available_cols = ['CNPJ_FUNDO'] + [col for col in cols_to_merge if col in cadastro_df.columns]

        # Prepare cadastro subset
        cadastro_subset = cadastro_df[available_cols].drop_duplicates('CNPJ_FUNDO')

        # Merge
        result = df.merge(cadastro_subset, on='CNPJ_FUNDO', how='left', suffixes=('', '_metadata'))

        return result
