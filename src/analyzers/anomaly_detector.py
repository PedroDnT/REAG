import logging

import pandas as pd
import numpy as np
from scipy import stats
from typing import Optional, Tuple
from config.settings import Config

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detector de anomalias em dados de fundos"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def calculate_z_scores(self, series: pd.Series) -> pd.Series:
        """Calcula Z-scores para uma série"""
        return (series - series.mean()) / series.std()

    def detect_flow_anomalies(self, df: pd.DataFrame,
                             threshold: float = 3.0,
                             flow_col: str = 'FLUXO_LIQ_DIA') -> pd.DataFrame:
        """
        Detecta anomalias de fluxo usando Z-score

        Retorna DataFrame com apenas registros anômalos
        """
        if flow_col not in df.columns:
            logger.warning(f"Coluna {flow_col} nao encontrada")
            return pd.DataFrame()

        df = df.copy()

        # Calcular Z-score por fundo
        if 'CNPJ_FUNDO' in df.columns:
            df['Z_SCORE_FLOW'] = df.groupby('CNPJ_FUNDO')[flow_col].transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
            )
        else:
            df['Z_SCORE_FLOW'] = self.calculate_z_scores(df[flow_col])

        # Identificar anomalias
        df['IS_ANOMALY_FLOW'] = df['Z_SCORE_FLOW'].abs() > threshold

        # Retornar apenas anomalias
        anomalies = df[df['IS_ANOMALY_FLOW']].copy()

        return anomalies.sort_values('Z_SCORE_FLOW', key=abs, ascending=False)

    def detect_pl_drops(self, df: pd.DataFrame,
                       threshold_pct: float = 20.0,
                       pl_col: str = 'VL_PATRIM_LIQ') -> pd.DataFrame:
        """
        Detecta quedas bruscas de patrimônio líquido

        threshold_pct: porcentagem de queda para considerar anomalia
        """
        if pl_col not in df.columns or 'DT_COMPTC' not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Calcular variação percentual diária
        df['PL_VAR_PCT'] = df.groupby('CNPJ_FUNDO')[pl_col].pct_change() * 100

        # Identificar quedas significativas
        df['IS_PL_DROP'] = df['PL_VAR_PCT'] < -threshold_pct

        drops = df[df['IS_PL_DROP']].copy()

        return drops.sort_values('PL_VAR_PCT')

    def detect_runs(self, df: pd.DataFrame,
                   consecutive_days: int = 5,
                   flow_col: str = 'FLUXO_LIQ_DIA') -> pd.DataFrame:
        """
        Detecta "runs" - sequências consecutivas de resgates líquidos

        consecutive_days: número mínimo de dias consecutivos de resgate
        """
        if flow_col not in df.columns or 'DT_COMPTC' not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Identificar dias de resgate líquido negativo
        df['IS_NEGATIVE_FLOW'] = df[flow_col] < 0

        # Contar sequências consecutivas
        df['RUN_ID'] = (df.groupby('CNPJ_FUNDO')['IS_NEGATIVE_FLOW']
                       .transform(lambda x: (x != x.shift()).cumsum()))

        df['RUN_LENGTH'] = df.groupby(['CNPJ_FUNDO', 'RUN_ID']).cumcount() + 1

        # Filtrar apenas runs significativas
        runs = df[(df['IS_NEGATIVE_FLOW']) & (df['RUN_LENGTH'] >= consecutive_days)].copy()

        return runs.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

    def detect_concentration_spikes(self, cda_df: pd.DataFrame,
                                   threshold_pct: float = 50.0) -> pd.DataFrame:
        """
        Detecta aumento brusco de concentração em poucos ativos

        Requer dados de CDA
        """
        if 'CNPJ_FUNDO' not in cda_df.columns or 'VL_MERC_POS_FINAL' not in cda_df.columns:
            return pd.DataFrame()

        df = cda_df.copy()

        # Calcular total por fundo e data
        total_by_fund = df.groupby(['CNPJ_FUNDO', 'DT_COMPTC'])['VL_MERC_POS_FINAL'].sum().reset_index()
        total_by_fund.rename(columns={'VL_MERC_POS_FINAL': 'TOTAL_CARTEIRA'}, inplace=True)

        # Merge para ter percentual de cada ativo
        df = df.merge(total_by_fund, on=['CNPJ_FUNDO', 'DT_COMPTC'])
        df['PCT_CARTEIRA'] = (df['VL_MERC_POS_FINAL'] / df['TOTAL_CARTEIRA']) * 100

        # Identificar ativos com concentração alta
        high_concentration = df[df['PCT_CARTEIRA'] > threshold_pct].copy()

        return high_concentration.sort_values('PCT_CARTEIRA', ascending=False)

    def detect_divergence_flow_performance(self, df: pd.DataFrame,
                                          threshold_z: float = 2.0) -> pd.DataFrame:
        """
        Detecta divergência entre fluxo e performance

        Ex: entradas grandes em dias de performance ruim
        """
        required_cols = ['VL_QUOTA', 'FLUXO_LIQ_DIA', 'CNPJ_FUNDO', 'DT_COMPTC']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Calcular retorno diário da cota
        df['RETORNO_DIA'] = df.groupby('CNPJ_FUNDO')['VL_QUOTA'].pct_change() * 100

        # Calcular Z-score de fluxo e retorno
        df['Z_FLOW'] = df.groupby('CNPJ_FUNDO')['FLUXO_LIQ_DIA'].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )
        df['Z_RETORNO'] = df.groupby('CNPJ_FUNDO')['RETORNO_DIA'].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )

        # Divergência: fluxo e retorno em direções opostas com magnitudes altas
        df['DIVERGENCE_SCORE'] = -(df['Z_FLOW'] * df['Z_RETORNO'])  # negativo de produto = direções opostas

        # Filtrar apenas divergências significativas
        divergences = df[df['DIVERGENCE_SCORE'] > threshold_z].copy()

        return divergences.sort_values('DIVERGENCE_SCORE', ascending=False)

    def generate_anomaly_report(self, df: pd.DataFrame,
                               cda_df: Optional[pd.DataFrame] = None) -> dict:
        """
        Gera relatório completo de anomalias

        Retorna dict com diferentes tipos de anomalia
        """
        report = {}

        # 1. Anomalias de fluxo
        report['flow_anomalies'] = self.detect_flow_anomalies(
            df,
            threshold=self.config.ANOMALY_Z_SCORE_THRESHOLD
        )

        # 2. Quedas de PL
        report['pl_drops'] = self.detect_pl_drops(df, threshold_pct=20.0)

        # 3. Runs (resgates consecutivos)
        report['runs'] = self.detect_runs(df, consecutive_days=self.config.FLOW_WINDOW_DAYS)

        # 4. Divergência flow vs performance
        report['divergences'] = self.detect_divergence_flow_performance(df)

        # 5. Concentração (se CDA disponível)
        if cda_df is not None:
            report['concentration_spikes'] = self.detect_concentration_spikes(cda_df)

        return report
