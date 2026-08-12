"""
Market Data Validator - Valida preços declarados com mercado

Este módulo compara preços declarados no CDA com preços reais de mercado,
detectando sobrevalorização e subvalorização de ativos.
"""

import logging
import re

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except Exception:  # pragma: no cover
    class _YFinanceStub:
        @staticmethod
        def download(*args, **kwargs):
            raise ImportError("yfinance not installed")

    yf = _YFinanceStub()
    YFINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)

# B3 ticker shape: four letters then 1-2 digits (PETR4, BOVA11, ITUB3).
#
# CDA holdings are dominated by unlisted credit -- CRI_ABC_2024,
# DEB_PETROBRAS_2025, cotas identified by CNPJ. Appending ".SA" to those and
# querying Yahoo produces nothing but latency and rate-limit pressure, so
# anything that is not shaped like a listed ticker is never sent.
_B3_TICKER_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")


class MarketDataValidator:
    """
    Valida preços de ativos declarados vs preços de mercado

    Fontes de dados (em ordem de prioridade):
    1. Yahoo Finance (ações brasileiras)
    2. Cache local
    3. Estimativas (quando dados não disponíveis)
    """

    def __init__(self, cache_dir: Path | None = None):
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
                                   for ticker, date, price in zip(
                                       df['ticker'], df['date'], df['price'], strict=True
                                   )}
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

    def get_market_price(self, ticker: str, date: datetime.date) -> float | None:
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

    def get_price(self, ticker: str, date: datetime.date) -> float | None:
        """Backward-compatible alias for get_market_price."""
        return self.get_market_price(ticker, date)

    def _convert_to_yahoo_ticker(self, ticker: str) -> str | None:
        """Convert a B3 ticker to Yahoo format, or None if it is not one.

        Returns None for anything that does not look like a listed B3 ticker,
        so unlisted CDA asset codes never become HTTP requests.
        """
        if ticker is None:
            return None

        candidate = str(ticker).strip().upper()
        if candidate.endswith(".SA"):
            candidate = candidate[:-3]

        if not _B3_TICKER_RE.match(candidate):
            return None

        return f"{candidate}.SA"

    @staticmethod
    def _close_series(hist: pd.DataFrame, yahoo_ticker: str) -> pd.Series | None:
        """Extract a Close series from a yfinance frame.

        Recent yfinance returns MultiIndex columns (field, ticker) even for a
        single symbol, so a plain hist['Close'] yields a DataFrame there.
        """
        if hist is None or hist.empty or "Close" not in hist:
            return None

        close = hist["Close"]
        if isinstance(close, pd.DataFrame):
            if yahoo_ticker in close.columns:
                close = close[yahoo_ticker]
            elif close.shape[1] == 1:
                close = close.iloc[:, 0]
            else:
                return None

        close = close.dropna()
        return close if not close.empty else None

    def _fetch_prices_bulk(self, tickers, start: datetime.date, end: datetime.date) -> int:
        """Fetch closes for many tickers in one request and fill the cache.

        Replaces the per-(ticker, date) download the row loop used to perform.
        A 10k-position CDA previously cost ~20k HTTP calls; this costs one per
        batch of distinct tickers.

        Args:
            tickers: Iterable of raw asset codes (filtered to B3 tickers here)
            start: First date to fetch, inclusive
            end: Last date to fetch, inclusive

        Returns:
            Number of (ticker, date) prices added to the cache
        """
        yahoo_by_raw = {}
        for raw in dict.fromkeys(tickers):
            yahoo = self._convert_to_yahoo_ticker(raw)
            if yahoo is not None:
                yahoo_by_raw[raw] = yahoo

        if not yahoo_by_raw:
            logger.info("No B3-listed tickers among the requested assets; skipping fetch")
            return 0

        symbols = sorted(set(yahoo_by_raw.values()))
        logger.info("Fetching %d ticker(s) from %s to %s", len(symbols), start, end)

        try:
            hist = yf.download(
                symbols,
                start=start,
                end=end + timedelta(days=1),
                progress=False,
                group_by="column",
            )
        except ImportError:
            logger.warning(
                "yfinance not installed; price validation unavailable. "
                "Install it with: pip install -r requirements-optional.txt"
            )
            return 0
        except Exception as exc:
            logger.warning("Bulk price fetch failed: %s", exc)
            return 0

        added = 0
        for raw, yahoo in yahoo_by_raw.items():
            close = self._close_series(hist, yahoo)
            if close is None:
                continue
            for timestamp, price in close.items():
                key = (raw, pd.Timestamp(timestamp).date())
                if key not in self.price_cache:
                    self.price_cache[key] = float(price)
                    added += 1

        logger.info("Cached %d price points", added)
        return added

    def _fetch_price_yahoo(self, ticker: str, date: datetime.date) -> float | None:
        """Backward-compatible alias for Yahoo fetch method."""
        return self._fetch_yahoo_price(ticker, date)

    def _fetch_yahoo_price(self, ticker: str, date: datetime.date) -> float | None:
        """
        Busca preço no Yahoo Finance

        Args:
            ticker: Código do ativo (ex: PETR4)
            date: Data

        Returns:
            Preço de fechamento ou None
        """
        yahoo_ticker = self._convert_to_yahoo_ticker(ticker)
        if yahoo_ticker is None:
            # Unlisted asset (CRI, debenture, cota): Yahoo has no such symbol.
            logger.debug("%s is not a B3 ticker; no market price available", ticker)
            return None

        try:
            # Buscar histórico
            end_date = date + timedelta(days=1)
            hist = yf.download(yahoo_ticker, start=date, end=end_date, progress=False)

            close = self._close_series(hist, yahoo_ticker)
            if close is not None:
                return float(close.iloc[0])

            # Tentar dia anterior (caso mercado fechado)
            hist = yf.download(
                yahoo_ticker, start=date - timedelta(days=3), end=end_date, progress=False
            )

            close = self._close_series(hist, yahoo_ticker)
            if close is not None:
                return float(close.iloc[-1])
        except ImportError:
            logger.warning(
                "yfinance not installed; price validation unavailable. "
                "Install it with: pip install -r requirements-optional.txt"
            )
        except Exception as e:
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

    def generate_report(self, validated_df: pd.DataFrame) -> dict[str, object]:
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
                                  sample_size: int | None = None) -> pd.DataFrame:
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

        validations = []

        # Persist whatever was fetched even if this run dies partway. Prices are
        # expensive to obtain and rate-limited; discarding them on a crash means
        # the next run pays for them again.
        try:
            # Prefetch every ticker in one request instead of one per
            # (ticker, date) row. The row loop below only reads the cache.
            dates = cda_analysis['DT_COMPTC'].dt.date
            self._fetch_prices_bulk(
                cda_analysis['CD_ATIVO'].tolist(), dates.min(), dates.max()
            )

            total = len(cda_analysis)
            logger.info(f"Avaliando {total:,} posicoes...")

            # Use itertuples instead of iterrows - much faster (10-100x)
            for row in cda_analysis.itertuples():
                ticker = row.CD_ATIVO
                date = row.DT_COMPTC.date()
                declared_price = row.DECLARED_PRICE

                market_price = self.price_cache.get((ticker, date))

                record = {
                    'CNPJ_FUNDO': getattr(row, 'CNPJ_FUNDO', None),
                    'CD_ATIVO': ticker,
                    'DT_COMPTC': date,
                    'DECLARED_PRICE': declared_price,
                    'MARKET_PRICE': market_price,
                    'DIVERGENCE_PCT': None,
                    'DIVERGENCE_ABS': None,
                    'POSITION_VALUE': row.VL_MERCADO,
                    'has_market_price': market_price is not None,
                }

                if market_price:
                    record['DIVERGENCE_PCT'] = (declared_price - market_price) / market_price * 100
                    record['DIVERGENCE_ABS'] = declared_price - market_price

                validations.append(record)
        finally:
            self._save_cache()

        result_df = pd.DataFrame(validations)

        logger.info("Validacao concluida:")
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
                             sample_size: int | None = 1000,
                             output_path: Path | None = None) -> dict[str, pd.DataFrame]:
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
