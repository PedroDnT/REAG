"""
Peer Comparison Analyzer - Compara fundos com peers

Detecta fundos com performance anormalmente diferente de fundos similares,
indicando possível manipulação ou fraude.
"""

import logging

import pandas as pd
from pathlib import Path
from config.constants import (
    MIN_OBSERVATIONS,
    PONZI_LOW_VOLATILITY_PCT,
    PONZI_MIN_RETURN,
    PONZI_POSITIVE_DAYS_PCT,
    PONZI_SHARPE_THRESHOLD,
    ZSCORE_THRESHOLD,
)

logger = logging.getLogger(__name__)


class PeerComparisonAnalyzer:
    """
    Compara fundos REAG com fundos similares (peers) do mercado

    Analisa:
    - Retornos vs peers
    - Volatilidade vs peers
    - Sharpe ratio vs peers
    - Fluxos vs peers
    """

    def __init__(self):
        """Inicializa o analisador de peers"""
        self.fund_categories = {}
        self.all_funds_data = None

    def load_fund_categories(self, cadastro_df: pd.DataFrame):
        """
        Carrega categorias de fundos do cadastro

        Args:
            cadastro_df: DataFrame do cadastro CVM
        """
        logger.info("Carregando categorias de fundos...")

        if 'CNPJ_FUNDO' not in cadastro_df.columns:
            logger.warning("Coluna CNPJ_FUNDO nao encontrada")
            return

        # Mapear classe para categoria
        class_mapping = {
            'Fundo de Ações': 'EQUITY',
            'Fundo de Renda Fixa': 'FIXED_INCOME',
            'Fundo Multimercado': 'MULTI_MARKET',
            'Fundo Cambial': 'FX',
            'Fundo de Investimento Imobiliário': 'REAL_ESTATE'
        }

        # Vectorized mapping - much faster than iterrows
        # Handle missing CLASSE column properly
        if 'CLASSE' in cadastro_df.columns:
            mapped_categories = cadastro_df['CLASSE'].fillna('UNKNOWN').map(class_mapping).fillna('OTHER')
        else:
            # If CLASSE doesn't exist, map all to 'OTHER' with proper index alignment
            mapped_categories = pd.Series('OTHER', index=cadastro_df.index)

        self.fund_categories = dict(zip(cadastro_df['CNPJ_FUNDO'], mapped_categories, strict=True))

        logger.info(f"{len(self.fund_categories):,} fundos categorizados")

        # Mostrar distribuição
        categories_dist = pd.Series(self.fund_categories).value_counts()
        logger.info(f"Distribuicao por categoria:\n{categories_dist}")

    def calculate_fund_metrics(self, informe_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula métricas de performance para cada fundo

        Args:
            informe_df: DataFrame do informe diário

        Returns:
            DataFrame com métricas por fundo
        """
        logger.info("Calculando metricas de fundos...")

        # Verificar colunas necessárias
        required_cols = ['CNPJ_FUNDO', 'DT_COMPTC', 'VL_QUOTA']
        missing = [col for col in required_cols if col not in informe_df.columns]

        if missing:
            raise ValueError(f"Colunas faltando: {missing}")

        # Calcular retorno diário
        informe_df = informe_df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])
        informe_df['RETORNO_DIA'] = informe_df.groupby('CNPJ_FUNDO')['VL_QUOTA'].pct_change() * 100

        # Agregar por fundo
        metrics = []

        for cnpj in informe_df['CNPJ_FUNDO'].unique():
            fund_data = informe_df[informe_df['CNPJ_FUNDO'] == cnpj]
            returns = fund_data['RETORNO_DIA'].dropna()

            if len(returns) < MIN_OBSERVATIONS:  # Mínimo de dados
                continue

            # Calcular métricas
            avg_return = returns.mean()
            volatility = returns.std()
            sharpe = avg_return / volatility if volatility > 0 else 0

            # % de dias positivos
            positive_days_pct = (returns > 0).sum() / len(returns) * 100

            # Patrimônio médio
            avg_pl = fund_data['VL_PATRIM_LIQ'].mean() if 'VL_PATRIM_LIQ' in fund_data.columns else 0

            # Categoria
            category = self.fund_categories.get(cnpj, 'UNKNOWN')

            metrics.append({
                'CNPJ_FUNDO': cnpj,
                'category': category,
                'avg_return': avg_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe,
                'positive_days_pct': positive_days_pct,
                'num_observations': len(returns),
                'avg_pl': avg_pl
            })

        metrics_df = pd.DataFrame(metrics)
        logger.info(f"Metricas calculadas para {len(metrics_df):,} fundos")

        return metrics_df

    def compare_with_peers(self, target_funds: list[str],
                          all_metrics_df: pd.DataFrame) -> pd.DataFrame:
        """
        Compara fundos alvo com seus peers

        Args:
            target_funds: Lista de CNPJs dos fundos a analisar (ex: REAG)
            all_metrics_df: DataFrame com métricas de todos os fundos

        Returns:
            DataFrame com comparação e outliers
        """
        logger.info(f"Comparando {len(target_funds)} fundos com peers...")

        comparisons = []

        for cnpj in target_funds:
            if cnpj not in all_metrics_df['CNPJ_FUNDO'].values:
                logger.warning(f"Fundo {cnpj} nao encontrado nas metricas")
                continue

            # Métricas do fundo alvo
            fund_metrics = all_metrics_df[all_metrics_df['CNPJ_FUNDO'] == cnpj].iloc[0]
            category = fund_metrics['category']

            # Peers (mesma categoria, excluindo o próprio fundo)
            peers = all_metrics_df[
                (all_metrics_df['category'] == category) &
                (all_metrics_df['CNPJ_FUNDO'] != cnpj)
            ]

            if len(peers) < 5:
                logger.warning(f"Poucos peers para {cnpj} (categoria: {category})")
                continue

            # Calcular Z-scores vs peers
            return_zscore = self._calculate_zscore(
                fund_metrics['avg_return'],
                peers['avg_return']
            )

            vol_zscore = self._calculate_zscore(
                fund_metrics['volatility'],
                peers['volatility']
            )

            sharpe_zscore = self._calculate_zscore(
                fund_metrics['sharpe_ratio'],
                peers['sharpe_ratio']
            )

            # Determinar se é outlier (|Z| > ZSCORE_THRESHOLD)
            is_outlier = (
                abs(return_zscore) > ZSCORE_THRESHOLD or
                abs(sharpe_zscore) > ZSCORE_THRESHOLD
            )

            # Classificar tipo de anomalia
            fraud_flag = None
            if return_zscore > ZSCORE_THRESHOLD:
                fraud_flag = 'RETURNS_TOO_HIGH'
            elif return_zscore < -ZSCORE_THRESHOLD:
                fraud_flag = 'HIDDEN_LOSSES'
            elif sharpe_zscore > ZSCORE_THRESHOLD:
                fraud_flag = 'RISK_ADJUSTED_TOO_GOOD'

            comparisons.append({
                'CNPJ_FUNDO': cnpj,
                'category': category,
                'num_peers': len(peers),

                # Métricas do fundo
                'fund_return': fund_metrics['avg_return'],
                'fund_volatility': fund_metrics['volatility'],
                'fund_sharpe': fund_metrics['sharpe_ratio'],

                # Métricas dos peers
                'peer_avg_return': peers['avg_return'].mean(),
                'peer_avg_volatility': peers['volatility'].mean(),
                'peer_avg_sharpe': peers['sharpe_ratio'].mean(),

                # Z-scores
                'return_zscore': return_zscore,
                'volatility_zscore': vol_zscore,
                'sharpe_zscore': sharpe_zscore,

                # Flags
                'is_outlier': is_outlier,
                'fraud_flag': fraud_flag
            })

        result_df = pd.DataFrame(comparisons)

        if not result_df.empty:
            result_df = result_df.sort_values('return_zscore', ascending=False)
            logger.info(f"Comparacao concluida: {len(result_df)} fundos analisados")
            logger.warning(f"Outliers detectados: {result_df['is_outlier'].sum()}")
        else:
            logger.info(f"Comparacao concluida: {len(result_df)} fundos analisados")
            logger.info("Nenhum fundo com peers suficientes para comparacao")

        return result_df

    def _calculate_zscore(self, value: float, peer_values: pd.Series) -> float:
        """
        Calcula Z-score de um valor vs distribuição de peers

        Args:
            value: Valor do fundo
            peer_values: Série com valores dos peers

        Returns:
            Z-score
        """
        peer_mean = peer_values.mean()
        peer_std = peer_values.std()

        if peer_std == 0:
            return 0

        return (value - peer_mean) / peer_std

    def detect_smoothed_returns(self, informe_df: pd.DataFrame,
                                target_funds: list[str]) -> pd.DataFrame:
        """
        Detecta retornos "suavizados" artificialmente

        Ponzi schemes frequentemente mostram:
        - Retornos muito estáveis (baixa volatilidade)
        - % alta de dias positivos
        - Sem correlação com mercado

        Args:
            informe_df: DataFrame do informe diário
            target_funds: Lista de fundos a analisar

        Returns:
            DataFrame com fundos suspeitos
        """
        logger.info("Detectando retornos suavizados (Ponzi-like)...")

        suspicious = []

        for cnpj in target_funds:
            fund_data = informe_df[informe_df['CNPJ_FUNDO'] == cnpj].copy()

            if len(fund_data) < 60:  # Mínimo 60 dias
                continue

            # Calcular retorno
            fund_data = fund_data.sort_values('DT_COMPTC')
            fund_data['RETORNO_DIA'] = fund_data['VL_QUOTA'].pct_change() * 100
            returns = fund_data['RETORNO_DIA'].dropna()

            if len(returns) < 50:
                continue

            # Métricas de suavização
            volatility = returns.std()
            positive_days_pct = (returns > 0).sum() / len(returns) * 100
            avg_return = returns.mean()
            sharpe = avg_return / volatility if volatility > 0 else 0

            # Calcular "smoothness" (retornos muito consistentes)
            # Usar coeficiente de variação invertido
            cv = volatility / abs(avg_return) if avg_return != 0 else 999
            smoothness_score = 1 / cv if cv > 0 else 0

            # Red flags
            is_suspicious = (
                (volatility < PONZI_LOW_VOLATILITY_PCT and avg_return > PONZI_MIN_RETURN) or  # Vol muito baixa com retorno positivo
                (positive_days_pct > PONZI_POSITIVE_DAYS_PCT) or  # >90% dias positivos
                (sharpe > PONZI_SHARPE_THRESHOLD)  # Sharpe muito alto
            )

            if is_suspicious:
                suspicious.append({
                    'CNPJ_FUNDO': cnpj,
                    'avg_return': avg_return,
                    'volatility': volatility,
                    'sharpe_ratio': sharpe,
                    'positive_days_pct': positive_days_pct,
                    'smoothness_score': smoothness_score,
                    'num_days': len(returns),
                    'fraud_flag': 'SMOOTHED_RETURNS_PONZI'
                })

        result_df = pd.DataFrame(suspicious)

        if not result_df.empty:
            result_df = result_df.sort_values('sharpe_ratio', ascending=False)
            logger.warning(f"{len(result_df)} fundos com retornos suspeitos!")
        else:
            logger.info("Nenhum padrao de suavizacao detectado")

        return result_df

    def generate_peer_report(self, target_funds: list[str],
                            informe_df: pd.DataFrame,
                            output_path: Path | None = None) -> dict[str, pd.DataFrame]:
        """
        Gera relatório completo de comparação com peers

        Args:
            target_funds: Lista de CNPJs dos fundos a analisar
            informe_df: DataFrame do informe diário
            output_path: Diretório para salvar relatórios (opcional)

        Returns:
            Dict com DataFrames de análises
        """
        logger.info("=" * 60)
        logger.info("ANALISE DE COMPARACAO COM PEERS")
        logger.info("=" * 60)

        # Calcular métricas de todos os fundos
        all_metrics = self.calculate_fund_metrics(informe_df)

        # Comparar com peers
        peer_comparison = self.compare_with_peers(target_funds, all_metrics)

        # Detectar suavização
        smoothed_returns = self.detect_smoothed_returns(informe_df, target_funds)

        # Salvar relatórios
        if output_path:
            output_path = Path(output_path)
            output_path.mkdir(parents=True, exist_ok=True)

            if not peer_comparison.empty:
                file1 = output_path / 'peer_comparison.csv'
                peer_comparison.to_csv(file1, index=False)
                logger.info(f"Peer comparison saved: {file1}")

            if not smoothed_returns.empty:
                file2 = output_path / 'smoothed_returns.csv'
                smoothed_returns.to_csv(file2, index=False)
                logger.info(f"Smoothed returns saved: {file2}")

        # Resumo
        logger.info("=" * 60)
        logger.info("RESUMO")
        logger.info("=" * 60)

        logger.info(f"Fundos analisados: {len(target_funds)}")
        logger.warning(f"Outliers (|Z| > 3): {peer_comparison['is_outlier'].sum() if not peer_comparison.empty else 0}")
        logger.warning(f"Retornos suavizados: {len(smoothed_returns)}")

        if not peer_comparison.empty and peer_comparison['is_outlier'].any():
            outliers = peer_comparison[peer_comparison['is_outlier']]
            logger.info(f"Top outliers:\n{outliers[['CNPJ_FUNDO', 'fraud_flag', 'return_zscore', 'sharpe_zscore']].head()}")

        return {
            'all_metrics': all_metrics,
            'peer_comparison': peer_comparison,
            'smoothed_returns': smoothed_returns
        }
