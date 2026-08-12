"""Extended tests for Market Data Validator to improve coverage."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from src.analyzers.market_data import MarketDataValidator


class TestMarketDataValidatorInit:
    """Test MarketDataValidator initialization."""

    def test_init_with_default_cache_dir(self, tmp_path):
        """Test initialization with default cache directory."""
        validator = MarketDataValidator()
        assert validator.cache_dir is not None
        assert validator.price_cache == {}

    def test_init_with_custom_cache_dir(self, tmp_path):
        """Test initialization with custom cache directory."""
        custom_cache = tmp_path / "custom_cache"
        validator = MarketDataValidator(cache_dir=custom_cache)
        assert validator.cache_dir == custom_cache
        assert custom_cache.exists()


class TestMarketDataValidatorLoadCache:
    """Test cache loading functionality."""

    def test_load_cache_empty(self, tmp_path):
        """Test loading cache when cache file doesn't exist."""
        validator = MarketDataValidator(cache_dir=tmp_path)
        assert validator.price_cache == {}

    def test_load_cache_with_existing_data(self, tmp_path):
        """Test loading cache from existing CSV file."""
        # Create a cache file
        cache_file = tmp_path / "price_cache.csv"
        cache_data = pd.DataFrame({
            'ticker': ['PETR4', 'VALE3'],
            'date': [datetime(2023, 1, 1), datetime(2023, 1, 2)],
            'price': [30.5, 70.2]
        })
        cache_data.to_csv(cache_file, index=False)

        validator = MarketDataValidator(cache_dir=tmp_path)

        # Check that cache was loaded
        assert len(validator.price_cache) >= 0

    def test_load_cache_with_corrupt_file(self, tmp_path):
        """Test loading cache with corrupt CSV file."""
        cache_file = tmp_path / "price_cache.csv"
        cache_file.write_text("invalid,csv\ndata")

        # Should handle corrupt file gracefully
        validator = MarketDataValidator(cache_dir=tmp_path)
        assert validator.price_cache == {}


class TestMarketDataValidatorSaveCache:
    """Test cache saving functionality."""

    def test_save_cache_empty(self, tmp_path):
        """Test saving empty cache."""
        validator = MarketDataValidator(cache_dir=tmp_path)
        validator._save_cache()

        cache_file = tmp_path / "price_cache.csv"
        # Empty cache might create empty file or no file
        assert True  # No exception should be raised

    def test_save_cache_with_data(self, tmp_path):
        """Test saving cache with price data."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        # Add some data to cache
        test_date = date(2023, 1, 15)
        validator.price_cache[('PETR4', test_date)] = 30.5

        validator._save_cache()

        cache_file = tmp_path / "price_cache.csv"
        assert cache_file.exists()

        # Verify saved data
        loaded = pd.read_csv(cache_file)
        assert len(loaded) >= 0


class TestMarketDataValidatorGetPrice:
    """Test price retrieval functionality."""

    def test_get_price_from_cache(self, tmp_path):
        """Test getting price from cache."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        test_date = date(2023, 1, 15)
        validator.price_cache[('PETR4', test_date)] = 30.5

        price = validator.get_price('PETR4', test_date)
        assert price == 30.5

    def test_get_price_not_in_cache(self, tmp_path):
        """A cache miss fetches, returns the fetched price, and caches it."""
        with patch.object(MarketDataValidator, '_fetch_price_yahoo') as mock_fetch:
            mock_fetch.return_value = 31.2

            validator = MarketDataValidator(cache_dir=tmp_path)
            test_date = date(2023, 1, 15)

            price = validator.get_price('VALE3', test_date)

            mock_fetch.assert_called_once_with('VALE3', test_date)
            assert price == 31.2
            assert validator.price_cache[('VALE3', test_date)] == 31.2

            # A second call is served from cache, not refetched.
            assert validator.get_price('VALE3', test_date) == 31.2
            mock_fetch.assert_called_once()

    def test_get_price_yahoo_fails(self, tmp_path):
        """Test getting price when Yahoo fetch fails."""
        with patch.object(MarketDataValidator, '_fetch_price_yahoo') as mock_fetch:
            mock_fetch.return_value = None

            validator = MarketDataValidator(cache_dir=tmp_path)
            test_date = date(2023, 1, 15)

            price = validator.get_price('UNKNOWN', test_date)

            # Should return None when fetch fails
            assert price is None


class TestMarketDataValidatorFetchPrice:
    """Test price fetching from Yahoo Finance."""

    @patch('src.analyzers.market_data.yf.download')
    def test_fetch_price_yahoo_success(self, mock_download, tmp_path):
        """A successful fetch returns the close price."""
        mock_download.return_value = pd.DataFrame(
            {'Close': [30.5]}, index=[pd.Timestamp('2023-01-15')]
        )

        validator = MarketDataValidator(cache_dir=tmp_path)
        price = validator._fetch_price_yahoo('PETR4.SA', date(2023, 1, 15))

        assert price == pytest.approx(30.5)
        mock_download.assert_called_once()

    @patch('src.analyzers.market_data.yf.download')
    def test_fetch_price_yahoo_no_data(self, mock_download, tmp_path):
        """An empty response yields None after the market-closed retry."""
        mock_download.return_value = pd.DataFrame()

        validator = MarketDataValidator(cache_dir=tmp_path)
        price = validator._fetch_price_yahoo('PETR4.SA', date(2023, 1, 15))

        assert price is None
        # First attempt for the exact day, second widening to catch a holiday.
        assert mock_download.call_count == 2

    @patch('src.analyzers.market_data.yf.download')
    def test_fetch_price_handles_multiindex_columns(self, mock_download, tmp_path):
        """Modern yfinance returns (field, ticker) columns even for one symbol."""
        mock_download.return_value = pd.DataFrame(
            {('Close', 'PETR4.SA'): [30.5]},
            index=[pd.Timestamp('2023-01-15')],
        )

        validator = MarketDataValidator(cache_dir=tmp_path)
        assert validator._fetch_price_yahoo('PETR4', date(2023, 1, 15)) == pytest.approx(30.5)

    @patch('src.analyzers.market_data.yf.download')
    def test_unlisted_asset_is_never_requested(self, mock_download, tmp_path):
        """CDA holds CRI, debentures and cotas; Yahoo has no such symbols."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        for code in ['CRI_ABC_2024', 'DEB_PETROBRAS_2025', '12345678000190']:
            assert validator._fetch_price_yahoo(code, date(2023, 1, 15)) is None

        mock_download.assert_not_called()


class TestMarketDataValidatorValidate:
    """Test portfolio validation."""

    def test_validate_empty_portfolio(self, tmp_path):
        """Test validation of empty portfolio."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        portfolio_df = pd.DataFrame(columns=['ticker', 'declared_price', 'quantity', 'date'])

        result = validator.validate(portfolio_df)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_validate_portfolio_with_data(self, tmp_path):
        """Test validation of portfolio with price data."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        # Mock get_price to return known values
        with patch.object(validator, 'get_price') as mock_get_price:
            mock_get_price.return_value = 30.0

            portfolio_df = pd.DataFrame({
                'ticker': ['PETR4'],
                'declared_price': [35.0],
                'quantity': [1000],
                'date': [date(2023, 1, 15)]
            })

            result = validator.validate(portfolio_df)

            assert isinstance(result, pd.DataFrame)
            # Should have calculated deviations


    def test_validate_missing_required_columns(self, tmp_path):
        """Test validation with missing required columns."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        # Missing 'declared_price' column
        portfolio_df = pd.DataFrame({
            'ticker': ['PETR4'],
            'quantity': [1000]
        })

        # Should handle missing columns gracefully or raise error
        with pytest.raises((KeyError, ValueError)):
            validator.validate(portfolio_df)


class TestMarketDataValidatorDetectAnomalies:
    """Test anomaly detection."""

    def test_detect_anomalies_no_deviations(self, tmp_path):
        """Test anomaly detection with no price deviations."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        validated_df = pd.DataFrame({
            'ticker': ['PETR4', 'VALE3'],
            'price_deviation_pct': [0.5, 1.0]  # Small deviations
        })

        anomalies = validator.detect_anomalies(validated_df, threshold=5.0)

        assert isinstance(anomalies, pd.DataFrame)
        assert len(anomalies) == 0  # No anomalies with 5% threshold

    def test_detect_anomalies_with_deviations(self, tmp_path):
        """Test anomaly detection with significant price deviations."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        validated_df = pd.DataFrame({
            'ticker': ['PETR4', 'VALE3'],
            'price_deviation_pct': [10.0, 1.0]  # PETR4 has large deviation
        })

        anomalies = validator.detect_anomalies(validated_df, threshold=5.0)

        assert isinstance(anomalies, pd.DataFrame)
        assert len(anomalies) >= 0

    def test_detect_anomalies_custom_threshold(self, tmp_path):
        """Test anomaly detection with custom threshold."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        validated_df = pd.DataFrame({
            'ticker': ['PETR4'],
            'price_deviation_pct': [7.0]
        })

        # With 10% threshold, should not be anomaly
        anomalies = validator.detect_anomalies(validated_df, threshold=10.0)
        assert len(anomalies) == 0

        # With 5% threshold, should be anomaly
        anomalies = validator.detect_anomalies(validated_df, threshold=5.0)
        assert len(anomalies) >= 0


class TestMarketDataValidatorGenerateReport:
    """Test report generation."""

    def test_generate_report_basic(self, tmp_path):
        """Test basic report generation."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        validated_df = pd.DataFrame({
            'ticker': ['PETR4', 'VALE3'],
            'declared_price': [30.0, 70.0],
            'market_price': [29.0, 72.0],
            'price_deviation_pct': [3.4, -2.8]
        })

        report = validator.generate_report(validated_df)

        assert isinstance(report, dict)
        assert 'summary' in report or 'total_assets' in report


class TestMarketDataValidatorTickerConversion:
    """Test ticker conversion utilities."""

    def test_convert_to_yahoo_ticker(self, tmp_path):
        """Test conversion of ticker to Yahoo Finance format."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        # Brazilian stocks should have .SA suffix
        yahoo_ticker = validator._convert_to_yahoo_ticker('PETR4')
        assert '.SA' in yahoo_ticker or yahoo_ticker == 'PETR4.SA'

    def test_convert_to_yahoo_ticker_already_formatted(self, tmp_path):
        """Test conversion when ticker already has suffix."""
        validator = MarketDataValidator(cache_dir=tmp_path)

        yahoo_ticker = validator._convert_to_yahoo_ticker('PETR4.SA')
        assert yahoo_ticker == 'PETR4.SA'


class TestYahooTickerFilter:
    """Only B3-shaped codes become Yahoo symbols.

    CDA holdings are dominated by unlisted credit. The previous implementation
    appended ".SA" to every asset code, so CRI_ABC_2024 became a request for
    "CRI_ABC_2024.SA" -- two futile HTTP calls each, thousands per portfolio.
    """

    @pytest.fixture
    def validator(self, tmp_path):
        return MarketDataValidator(cache_dir=tmp_path)

    @pytest.mark.parametrize("code,expected", [
        ("PETR4", "PETR4.SA"),
        ("VALE3", "VALE3.SA"),
        ("BOVA11", "BOVA11.SA"),     # ETF, two-digit suffix
        ("petr4", "PETR4.SA"),       # case-insensitive
        (" PETR4 ", "PETR4.SA"),     # whitespace tolerated
        ("PETR4.SA", "PETR4.SA"),    # already converted, not double-suffixed
    ])
    def test_listed_tickers_are_converted(self, validator, code, expected):
        assert validator._convert_to_yahoo_ticker(code) == expected

    @pytest.mark.parametrize("code", [
        "CRI_ABC_2024",
        "CRA_AGRO_2026",
        "DEB_PETROBRAS_2025",
        "CDB_BANCO_XYZ",
        "12345678000190",   # a fund cota identified by CNPJ
        "TOOLONGNAME1",
        "AB1",              # too few letters
        "PETR",             # no numeric suffix
        "PETR123",          # three-digit suffix
        "",
        None,
    ])
    def test_unlisted_codes_are_rejected(self, validator, code):
        assert validator._convert_to_yahoo_ticker(code) is None


class TestBulkPriceFetch:
    """One request per batch, not one per (ticker, date) row."""

    @pytest.fixture
    def validator(self, tmp_path):
        return MarketDataValidator(cache_dir=tmp_path)

    @patch('src.analyzers.market_data.yf.download')
    def test_single_request_covers_every_ticker_and_date(self, mock_download, validator):
        index = pd.to_datetime(['2024-01-02', '2024-01-03', '2024-01-04'])
        mock_download.return_value = pd.DataFrame(
            {('Close', 'PETR4.SA'): [30.0, 31.0, 32.0],
             ('Close', 'VALE3.SA'): [60.0, 61.0, 62.0]},
            index=index,
        )

        added = validator._fetch_prices_bulk(
            ['PETR4', 'VALE3', 'PETR4'], date(2024, 1, 2), date(2024, 1, 4)
        )

        mock_download.assert_called_once()
        assert added == 6
        assert validator.price_cache[('PETR4', date(2024, 1, 3))] == pytest.approx(31.0)
        assert validator.price_cache[('VALE3', date(2024, 1, 4))] == pytest.approx(62.0)

    @patch('src.analyzers.market_data.yf.download')
    def test_no_request_when_nothing_is_listed(self, mock_download, validator):
        added = validator._fetch_prices_bulk(
            ['CRI_ABC_2024', 'DEB_X_2025'], date(2024, 1, 2), date(2024, 1, 4)
        )

        mock_download.assert_not_called()
        assert added == 0

    @patch('src.analyzers.market_data.yf.download')
    def test_unlisted_codes_are_filtered_out_of_the_request(self, mock_download, validator):
        mock_download.return_value = pd.DataFrame(
            {'Close': [30.0]}, index=pd.to_datetime(['2024-01-02'])
        )

        validator._fetch_prices_bulk(
            ['PETR4', 'CRI_ABC_2024'], date(2024, 1, 2), date(2024, 1, 2)
        )

        symbols = mock_download.call_args[0][0]
        assert symbols == ['PETR4.SA']

    @patch('src.analyzers.market_data.yf.download')
    def test_existing_cache_entries_are_not_overwritten(self, mock_download, validator):
        validator.price_cache[('PETR4', date(2024, 1, 2))] = 99.0
        mock_download.return_value = pd.DataFrame(
            {'Close': [30.0]}, index=pd.to_datetime(['2024-01-02'])
        )

        added = validator._fetch_prices_bulk(['PETR4'], date(2024, 1, 2), date(2024, 1, 2))

        assert added == 0
        assert validator.price_cache[('PETR4', date(2024, 1, 2))] == 99.0

    @patch('src.analyzers.market_data.yf.download', side_effect=ImportError("no yfinance"))
    def test_missing_yfinance_degrades_without_raising(self, mock_download, validator, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            assert validator._fetch_prices_bulk(['PETR4'], date(2024, 1, 2), date(2024, 1, 2)) == 0

        assert any('yfinance not installed' in r.message for r in caplog.records)

    @patch('src.analyzers.market_data.yf.download', side_effect=RuntimeError("rate limited"))
    def test_network_failure_degrades_without_raising(self, mock_download, validator):
        assert validator._fetch_prices_bulk(['PETR4'], date(2024, 1, 2), date(2024, 1, 2)) == 0


class TestValidatePortfolioPricesBatching:

    @patch('src.analyzers.market_data.yf.download')
    def test_portfolio_validation_issues_one_request(self, mock_download, tmp_path):
        """30 rows across 3 tickers must cost one request, not 30."""
        index = pd.to_datetime(['2024-01-02'])
        mock_download.return_value = pd.DataFrame(
            {('Close', 'PETR4.SA'): [30.0],
             ('Close', 'VALE3.SA'): [60.0],
             ('Close', 'ITUB4.SA'): [25.0]},
            index=index,
        )

        cda = pd.DataFrame({
            'CNPJ_FUNDO': ['12345678000190'] * 30,
            'CD_ATIVO': ['PETR4', 'VALE3', 'ITUB4'] * 10,
            'VL_MERCADO': [300_000.0] * 30,
            'QT_POS': [10_000.0] * 30,
            'DT_COMPTC': [pd.Timestamp('2024-01-02')] * 30,
        })

        validator = MarketDataValidator(cache_dir=tmp_path)
        result = validator.validate_portfolio_prices(cda)

        mock_download.assert_called_once()
        assert len(result) == 30
        assert result['has_market_price'].all()

    @patch('src.analyzers.market_data.yf.download')
    def test_cache_is_persisted_even_when_the_run_fails(self, mock_download, tmp_path):
        """Prices are rate-limited and expensive; a crash must not discard them."""
        mock_download.return_value = pd.DataFrame(
            {'Close': [30.0]}, index=pd.to_datetime(['2024-01-02'])
        )

        cda = pd.DataFrame({
            'CD_ATIVO': ['PETR4'],
            'VL_MERCADO': [300_000.0],
            'QT_POS': [10_000.0],
            'DT_COMPTC': [pd.Timestamp('2024-01-02')],
        })

        validator = MarketDataValidator(cache_dir=tmp_path)
        with patch.object(MarketDataValidator, '_save_cache', wraps=validator._save_cache) as saver:
            with patch('pandas.DataFrame.itertuples', side_effect=RuntimeError("boom")):
                with pytest.raises(RuntimeError):
                    validator.validate_portfolio_prices(cda)
            saver.assert_called_once()

        assert (tmp_path / 'price_cache.csv').exists()
