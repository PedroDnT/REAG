"""
Market Data Validator - Valida preços declarados com mercado

Este módulo compara preços declarados no CDA com preços reais de mercado,
detectando sobrevalorização e subvalorização de ativos.
"""

import logging

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
import time

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    class _YFinanceStub:
        @staticmethod
        def download(*args, **kwargs):
            raise ImportError("yfinance not installed")

    yf = _YFinanceStub()

logger = logging.getLogger(__name__)


class MarketDataValidator:
    """
    Valida preços de ativos declarados vs preços de mercado

    Fontes de dados (em ordem de prioridade):
    1. Yahoo Finance (ações brasileiras)
    2. Cache local
    3. Estimativas (quando dados não disponíveis)
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Args:
            cache_dir: Diretório para cache de preços
        """
        self.cache_dir = cache_dir or Path('data/cache/market_prices')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.price_cache = {}
        self._load_cache()

    def _load_cache(self):
        """Carrega cache de preços"""
        cache_file = self.cache_dir / 'price_cache.csv'

        if cache_file.exists():
            try:
                df = pd.read_csv(cache_file, parse_dates=['date'])
                # Vectorized conversion: convert date column to date objects and create dict
                df['date'] = pd.to_datetime(df['date']).dt.date
                # Use vectorized set_index + to_dict for much faster dictionary creation
                self.price_cache = {(ticker, date): price 
                                   for ticker, date, price in zip(df['ticker'], df['date'], df['price'])}
                logger.info(f"Cache carregado: {len(self.price_cache):,} precos")
            except Exception as e:
                logger.warning(f"Erro ao carregar cache: {e}")

    def _save_cache(self):
        """Salva cache de preços"""
        cache_file = self.cache_dir / 'price_cache.csv'

        records = [
            {'ticker': k[0], 'date': k[1], 'price': v}
            for k, v in self.price_cache.items()
        ]

        if records:
            df = pd.DataFrame(records)
            df.to_csv(cache_file, index=False)
            logger.info(f"Cache salvo: {len(records):,} precos")

    def get_market_price(self, ticker: str, date: datetime.date) -> Optional[float]:
        """
        Busca preço de mercado para um ativo

        Args:
            ticker: Código do ativo (ex: PETR4)
            date: Data

        Returns:
            Preço de fechamento ou None se não encontrado
        """
        # Verificar cache primeiro
        cache_key = (ticker, date)
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        # Tentar Yahoo Finance
        try:
            price = self._fetch_price_yahoo(ticker, date)
            if price is not None:
                self.price_cache[cache_key] = price
                return price
        except Exception as e:
            logger.warning(f"Erro ao buscar {ticker} em {date}: {e}")

        return None

    def get_price(self, ticker: str, date: datetime.date) -> Optional[float]:
        """Backward-compatible alias for get_market_price."""
        return self.get_market_price(ticker, date)

    def _convert_to_yahoo_ticker(self, ticker: str) -> str:
        """Convert B3 ticker to Yahoo format."""
        return ticker if ticker.endswith(".SA") else f"{ticker}.SA"

    def _fetch_price_yahoo(self, ticker: str, date: datetime.date) -> Optional[float]:
        """Backward-compatible alias for Yahoo fetch method."""
        return self._fetch_yahoo_price(ticker, date)

    def _fetch_yahoo_price(self, ticker: str, date: datetime.date) -> Optional[float]:
        """
        Busca preço no Yahoo Finance

        Args:
            ticker: Código do ativo (ex: PETR4)
            date: Data

        Returns:
            Preço de fechamento ou None
        """
        try:
            yahoo_ticker = self._convert_to_yahoo_ticker(ticker)

            # Buscar histórico
            start_date = date
            end_date = date + timedelta(days=1)
            hist = yf.download(yahoo_ticker, start=start_date, end=end_date, progress=False)

            if not hist.empty:
                return float(hist['Close'].iloc[0])

            # Tentar dia anterior (caso mercado fechado)
            start_date = date - timedelta(days=3)
            hist = yf.download(yahoo_ticker, start=start_date, end=end_date, progress=False)

            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            if isinstance(e, ImportError):
                logger.warning("yfinance not installed. Run: pip install yfinance")
                return None
            logger.debug("Could not fetch price for %s on %s: %s", ticker, date, e)

        return None

    def validate(self, portfolio_df: pd.DataFrame) -> pd.DataFrame:
        """Backward-compatible portfolio validation API used by tests."""
        required_cols = ['ticker', 'declared_price', 'quantity', 'date']
        missing = [col for col in required_cols if col not in portfolio_df.columns]
        if missing:
            raise ValueError(f"Colunas faltando: {missing}")

        if portfolio_df.empty:
            return portfolio_df.copy()

        result = portfolio_df.copy()
        result['date'] = pd.to_datetime(result['date']).dt.date
        result['market_price'] = [
            self.get_price(row.ticker, row.date) for row in result.itertuples(index=False)
        ]
        result['price_deviation_pct'] = np.where(
            result['market_price'].notna() & (result['market_price'] != 0),
            ((result['declared_price'] - result['market_price']) / result['market_price']) * 100,
            np.nan,
        )
        return result

    def detect_anomalies(self, validated_df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
        """Backward-compatible anomaly detection API used by tests."""
        if validated_df.empty:
            return validated_df.copy()
        return validated_df[validated_df['price_deviation_pct'].abs() > threshold].copy()

    def generate_report(self, validated_df: pd.DataFrame) -> Dict[str, object]:
        """Backward-compatible reporting API used by tests."""
        anomalies = self.detect_anomalies(validated_df)
        return {
            'summary': {
                'total_assets': int(len(validated_df)),
                'anomalies': int(len(anomalies)),
            },
            'total_assets': int(len(validated_df)),
        }

    def validate_portfolio_prices(self, cda_df: pd.DataFrame,
                                  sample_size: Optional[int] = None) -> pd.DataFrame:
        """
        Valida preços de um portfolio

        Args:
            cda_df: DataFrame do CDA
            sample_size: Limitar análise a N ativos (None = todos)

        Returns:
            DataFrame com validação de preços
        """
        logger.info("Validando precos com mercado...")

        required_cols = ['CD_ATIVO', 'VL_MERCADO', 'QT_POS', 'DT_COMPTC']
        missing = [col for col in required_cols if col not in cda_df.columns]

        if missing:
            raise ValueError(f"Colunas faltando: {missing}")

        # Sample first to reduce memory and processing (if needed)
        if sample_size and len(cda_df) > sample_size:
            logger.info(f"Amostrando {sample_size} de {len(cda_df):,} registros")
            cda_analysis = cda_df.sample(n=sample_size, random_state=42).copy()
        else:
            cda_analysis = cda_df.copy()

        # Converter data se necessário
        if not pd.api.types.is_datetime64_any_dtype(cda_analysis['DT_COMPTC']):
            cda_analysis['DT_COMPTC'] = pd.to_datetime(cda_analysis['DT_COMPTC'])

        # Calcular preço declarado por unidade (vectorized - much faster than apply with lambda)
        cda_analysis['DECLARED_PRICE'] = np.where(
            cda_analysis['QT_POS'] > 0,
            cda_analysis['VL_MERCADO'] / cda_analysis['QT_POS'],
            0
        )

        # Buscar preços de mercado
        validations = []
        total = len(cda_analysis)

        logger.info(f"Buscando precos para {total:,} posicoes...")

        # Use itertuples instead of iterrows - much faster (10-100x)
        for idx, row in enumerate(cda_analysis.itertuples(), 1):
            ticker = row.CD_ATIVO
            date = row.DT_COMPTC.date()
            declared_price = row.DECLARED_PRICE

            # Progress
            if idx % 100 == 0:
                logger.debug(f"   Progresso: {idx}/{total} ({idx/total*100:.1f}%)")

            # Buscar preço de mercado
            market_price = self.get_market_price(ticker, date)

            if market_price is not None:
                # Calcular divergência
                divergence_pct = ((declared_price - market_price) / market_price * 100)

                validations.append({
                    'CNPJ_FUNDO': getattr(row, 'CNPJ_FUNDO', None),
                    'CD_ATIVO': ticker,
                    'DT_COMPTC': date,
                    'DECLARED_PRICE': declared_price,
                    'MARKET_PRICE': market_price,
                    'DIVERGENCE_PCT': divergence_pct,
                    'DIVERGENCE_ABS': declared_price - market_price,
                    'POSITION_VALUE': row.VL_MERCADO,
                    'has_market_price': True
                })

                # Delay para evitar rate limiting
                if idx % 50 == 0:
                    time.sleep(0.5)
            else:
                validations.append({
                    'CNPJ_FUNDO': getattr(row, 'CNPJ_FUNDO', None),
                    'CD_ATIVO': ticker,
                    'DT_COMPTC': date,
                    'DECLARED_PRICE': declared_price,
                    'MARKET_PRICE': None,
                    'DIVERGENCE_PCT': None,
                    'DIVERGENCE_ABS': None,
                    'POSITION_VALUE': row.VL_MERCADO,
                    'has_market_price': False
                })

        result_df = pd.DataFrame(validations)

        # Salvar cache
        self._save_cache()

        logger.info(f"Validacao concluida:")
        logger.info(f"   Precos encontrados: {result_df['has_market_price'].sum():,}")
        logger.info(f"   Precos nao encontrados: {(~result_df['has_market_price']).sum():,}")

        return result_df

    def detect_price_manipulation(self, validation_df: pd.DataFrame,
                                  threshold_pct: float = 10.0) -> pd.DataFrame:
        """
        Detecta manipulação de preços

        Args:
            validation_df: DataFrame de validação (output de validate_portfolio_prices)
            threshold_pct: Threshold de divergência para considerar suspeito

        Returns:
            DataFrame com casos suspeitos
        """
        logger.info(f"Detectando manipulacao (threshold: {threshold_pct}%)...")

        # Filtrar apenas com preço de mercado
        with_prices = validation_df[validation_df['has_market_price']].copy()

        if with_prices.empty:
            logger.warning("Nenhum preco de mercado disponivel para validacao")
            return pd.DataFrame()

        # Suspeitos: divergência > threshold
        suspicious = with_prices[abs(with_prices['DIVERGENCE_PCT']) > threshold_pct].copy()

        if suspicious.empty:
            logger.info("Nenhuma manipulacao detectada")
            return pd.DataFrame()

        # Classificar tipo de manipulação
        suspicious['FRAUD_FLAG'] = suspicious['DIVERGENCE_PCT'].apply(
            lambda x: 'OVERVALUATION' if x > 0 else 'UNDERVALUATION'
        )

        # Severity
        suspicious['SEVERITY'] = suspicious['DIVERGENCE_PCT'].abs().apply(
            lambda x: 'CRITICAL' if x > 30 else ('HIGH' if x > 20 else 'MEDIUM')
        )

        # Ordenar por divergência
        suspicious = suspicious.sort_values('DIVERGENCE_PCT', ascending=False, key=abs)

        logger.warning(f"{len(suspicious)} casos suspeitos detectados!")

        return suspicious

    def generate_price_report(self, cda_df: pd.DataFrame,
                             sample_size: Optional[int] = 1000,
                             output_path: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
        """
        Gera relatório completo de validação de preços

        Args:
            cda_df: DataFrame do CDA
            sample_size: Tamanho da amostra (None = todos os ativos)
            output_path: Diretório para salvar relatórios

        Returns:
            Dict com DataFrames de análises
        """
        logger.info("=" * 60)
        logger.info("VALIDACAO DE PRECOS DE MERCADO")
        logger.info("=" * 60)

        # Validar preços
        validation = self.validate_portfolio_prices(cda_df, sample_size)

        # Detectar manipulação
        manipulation = self.detect_price_manipulation(validation)

        # Salvar relatórios
        if output_path:
            output_path = Path(output_path)
            output_path.mkdir(parents=True, exist_ok=True)

            if not validation.empty:
                file1 = output_path / 'price_validation.csv'
                validation.to_csv(file1, index=False)
                logger.info(f"Price validation saved: {file1}")

            if not manipulation.empty:
                file2 = output_path / 'price_manipulation.csv'
                manipulation.to_csv(file2, index=False)
                logger.info(f"Price manipulation saved: {file2}")

        # Resumo
        logger.info("=" * 60)
        logger.info("RESUMO")
        logger.info("=" * 60)

        with_prices = validation[validation['has_market_price']]

        logger.info(f"Ativos analisados: {len(validation):,}")
        logger.info(f"Com preco de mercado: {len(with_prices):,}")
        logger.info(f"Sem preco de mercado: {len(validation) - len(with_prices):,}")

        if not with_prices.empty:
            avg_div = with_prices['DIVERGENCE_PCT'].mean()
            logger.info(f"Divergencia media: {avg_div:.2f}%")
            logger.warning(f"Casos suspeitos (>10%): {len(manipulation)}")

            if not manipulation.empty:
                overval = manipulation[manipulation['FRAUD_FLAG'] == 'OVERVALUATION'].head(5)
                logger.info(f"Top 5 sobrevalorizacoes:\n{overval[['CD_ATIVO', 'DIVERGENCE_PCT', 'POSITION_VALUE']].to_string(index=False)}")

                underval = manipulation[manipulation['FRAUD_FLAG'] == 'UNDERVALUATION'].head(5)
                logger.info(f"Top 5 subvalorizacoes:\n{underval[['CD_ATIVO', 'DIVERGENCE_PCT', 'POSITION_VALUE']].to_string(index=False)}")

        return {
            'validation': validation,
            'manipulation': manipulation
        }
