"""
Peer Comparison Analyzer - Compara fundos com peers

Detecta fundos com performance anormalmente diferente de fundos similares,
indicando possível manipulação ou fraude.
"""

import logging

import numpy as np
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
        informe_df = informe_df.sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).copy()
        informe_df["RETORNO_DIA"] = (
            informe_df.groupby("CNPJ_FUNDO")["VL_QUOTA"].pct_change() * 100
        )

        returns = informe_df.dropna(subset=["RETORNO_DIA"])
        if returns.empty:
            return pd.DataFrame()

        # Aggregate once per fund -- filtering the full informe per CNPJ is
        # O(funds x rows) and dominates a full-universe peer pass.
        grouped = returns.groupby("CNPJ_FUNDO", sort=False)
        stats = grouped["RETORNO_DIA"].agg(
            avg_return="mean",
            volatility="std",
            num_observations="count",
        )
        positive_days = grouped["RETORNO_DIA"].apply(lambda s: float((s > 0).sum()))
        stats = stats.join(positive_days.rename("positive_days"), how="left")
        stats = stats[stats["num_observations"] >= MIN_OBSERVATIONS]
        if stats.empty:
            return pd.DataFrame()

        stats["positive_days_pct"] = (
            stats["positive_days"] / stats["num_observations"] * 100.0
        )
        stats["sharpe_ratio"] = stats["avg_return"] / stats["volatility"].replace(0, pd.NA)
        stats["sharpe_ratio"] = stats["sharpe_ratio"].fillna(0.0)

        if "VL_PATRIM_LIQ" in informe_df.columns:
            avg_pl = informe_df.groupby("CNPJ_FUNDO", sort=False)["VL_PATRIM_LIQ"].mean()
            stats = stats.join(avg_pl.rename("avg_pl"), how="left")
        else:
            stats["avg_pl"] = 0.0

        stats = stats.reset_index()
        stats["category"] = stats["CNPJ_FUNDO"].map(self.fund_categories).fillna("UNKNOWN")
        metrics_df = stats[
            [
                "CNPJ_FUNDO",
                "category",
                "avg_return",
                "volatility",
                "sharpe_ratio",
                "positive_days_pct",
                "num_observations",
                "avg_pl",
            ]
        ]
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

        if all_metrics_df.empty or not target_funds:
            return pd.DataFrame()

        metrics = all_metrics_df.drop_duplicates("CNPJ_FUNDO").copy()
        target_set = set(target_funds)
        targets = metrics[metrics["CNPJ_FUNDO"].isin(target_set)].copy()
        if targets.empty:
            logger.info("Nenhum fundo alvo encontrado nas metricas")
            return pd.DataFrame()

        value_columns = ("avg_return", "volatility", "sharpe_ratio")
        grouped = metrics.groupby("category", dropna=False)
        stats = grouped[list(value_columns)].agg(["count", "sum"])
        for column in value_columns:
            stats[(column, "sum_sq")] = grouped[column].apply(
                lambda values: float(np.square(values.astype(float)).sum())
            )
        stats.columns = [f"{column}_{stat}" for column, stat in stats.columns]
        targets = targets.merge(stats, left_on="category", right_index=True, how="left")

        # Exact leave-one-out peer means/stds without rebuilding a peer frame
        # for every target fund. This changes O(targets x funds) to O(funds).
        for column in value_columns:
            peer_count = targets[f"{column}_count"] - 1
            peer_sum = targets[f"{column}_sum"] - targets[column]
            peer_sum_sq = targets[f"{column}_sum_sq"] - np.square(targets[column])
            peer_mean = peer_sum / peer_count
            peer_variance = (
                peer_sum_sq - np.square(peer_sum) / peer_count
            ) / (peer_count - 1)
            peer_std = np.sqrt(peer_variance.clip(lower=0))

            targets[f"peer_avg_{column}"] = peer_mean
            targets[f"{column}_zscore"] = (
                (targets[column] - peer_mean) / peer_std.replace(0, np.nan)
            ).fillna(0.0)
            targets[f"{column}_peer_count"] = peer_count

        targets = targets[targets["avg_return_peer_count"] >= 5].copy()
        if targets.empty:
            logger.info("Nenhum fundo com peers suficientes para comparacao")
            return pd.DataFrame()

        targets["is_outlier"] = (
            targets["avg_return_zscore"].abs() > ZSCORE_THRESHOLD
        ) | (targets["sharpe_ratio_zscore"].abs() > ZSCORE_THRESHOLD)
        outliers = targets[targets["is_outlier"]].copy()
        if outliers.empty:
            logger.info("Comparacao concluida: nenhum outlier detectado")
            return pd.DataFrame()

        conditions = [
            outliers["avg_return_zscore"] > ZSCORE_THRESHOLD,
            outliers["avg_return_zscore"] < -ZSCORE_THRESHOLD,
            outliers["sharpe_ratio_zscore"] > ZSCORE_THRESHOLD,
        ]
        outliers["anomaly_type"] = np.select(
            conditions,
            ["RETURNS_TOO_HIGH", "HIDDEN_LOSSES", "RISK_ADJUSTED_TOO_GOOD"],
            default="UNUSUAL_PEER_PROFILE",
        )

        result_df = pd.DataFrame({
            "CNPJ_FUNDO": outliers["CNPJ_FUNDO"],
            "category": outliers["category"],
            "num_peers": outliers["avg_return_peer_count"].astype(int),
            "fund_return": outliers["avg_return"],
            "fund_volatility": outliers["volatility"],
            "fund_sharpe": outliers["sharpe_ratio"],
            "peer_avg_return": outliers["peer_avg_avg_return"],
            "peer_avg_volatility": outliers["peer_avg_volatility"],
            "peer_avg_sharpe": outliers["peer_avg_sharpe_ratio"],
            "return_zscore": outliers["avg_return_zscore"],
            "volatility_zscore": outliers["volatility_zscore"],
            "sharpe_zscore": outliers["sharpe_ratio_zscore"],
            "is_outlier": True,
            "anomaly_type": outliers["anomaly_type"],
        }).sort_values("return_zscore", ascending=False)

        logger.info(
            "Comparacao concluida: %d fundos analisados, %d outliers",
            len(targets),
            len(result_df),
        )
        return result_df.reset_index(drop=True)

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
