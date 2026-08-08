"""Extended tests for CVM collector to improve coverage."""
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
from datetime import datetime
from src.collectors.cvm_collector import CVMCollector
from config.settings import Config


class TestCVMCollectorExtended:
    """Extended tests for CVMCollector."""

    @pytest.fixture
    def collector(self, tmp_path):
        """Create a CVMCollector with temporary directories."""
        config = Config()
        config.RAW_DATA_DIR = tmp_path / "raw"
        config.PROCESSED_DATA_DIR = tmp_path / "processed"
        return CVMCollector(config=config)

    def test_init_creates_directories(self, tmp_path):
        """Test that initialization creates necessary directories."""
        config = Config()
        config.RAW_DATA_DIR = tmp_path / "raw"
        config.PROCESSED_DATA_DIR = tmp_path / "processed"

        collector = CVMCollector(config=config)

        assert config.RAW_DATA_DIR.exists()
        assert config.PROCESSED_DATA_DIR.exists()

    def test_init_with_no_config(self, tmp_path):
        """Test initialization without providing config."""
        collector = CVMCollector()
        assert collector.config is not None

    @patch('requests.Session.head')
    def test_check_file_exists_success(self, mock_head, collector):
        """Test successful file existence check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        result = collector.check_file_exists("http://example.com/file.zip")
        assert result is True
        mock_head.assert_called_once()

    @patch('requests.Session.head')
    def test_check_file_exists_not_found(self, mock_head, collector):
        """Test file existence check when file not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        result = collector.check_file_exists("http://example.com/file.zip")
        assert result is False

    @patch('requests.Session.head')
    def test_check_file_exists_exception(self, mock_head, collector):
        """Test file existence check with network exception."""
        mock_head.side_effect = Exception("Network error")

        result = collector.check_file_exists("http://example.com/file.zip")
        assert result is False

    def test_get_informe_diario_url(self, collector):
        """Test generating informe diario URL."""
        url = collector.get_informe_diario_url(2023, 5)
        assert "inf_diario_fi_202305.zip" in url

    def test_get_cda_url(self, collector):
        """Test generating CDA URL."""
        url = collector.get_cda_url(2023, 5)
        assert "cda_fi_202305.zip" in url

    def test_get_cadastro_url(self, collector):
        """Test generating cadastro URL."""
        url = collector.get_cadastro_url(2023, 5)
        assert "cad_fi_202305.csv" in url

    def test_get_available_months_invalid_range(self, collector):
        """Test get_available_months with invalid year range."""
        with pytest.raises(ValueError, match="start_year.*must be <= end_year"):
            collector.get_available_months(start_year=2025, end_year=2020)

    @patch.object(CVMCollector, 'check_file_exists')
    def test_get_available_months_informe_diario(self, mock_check, collector):
        """Test getting available months for informe diario."""
        # Mock that only January 2023 exists
        def check_file_side_effect(url):
            return "202301" in url

        mock_check.side_effect = check_file_side_effect

        result = collector.get_available_months(
            data_type='informe_diario',
            start_year=2023,
            end_year=2023
        )

        # Should find January 2023
        assert (2023, 1) in result

    @patch.object(CVMCollector, 'check_file_exists')
    def test_get_available_months_cda(self, mock_check, collector):
        """Test getting available months for CDA."""
        mock_check.return_value = True

        result = collector.get_available_months(
            data_type='cda',
            start_year=2023,
            end_year=2023
        )

        # Should check CDA URLs
        assert len(result) > 0

    @patch.object(CVMCollector, 'check_file_exists')
    def test_get_available_months_unknown_type(self, mock_check, collector):
        """Test getting available months with unknown data type."""
        mock_check.return_value = True

        result = collector.get_available_months(
            data_type='unknown',
            start_year=2023,
            end_year=2023
        )

        # Should return empty list for unknown type
        assert result == []

    @patch.object(CVMCollector, 'check_file_exists')
    def test_get_available_months_skips_future(self, mock_check, collector):
        """Test that get_available_months skips future months."""
        mock_check.return_value = True

        current_year = datetime.now().year
        future_year = current_year + 2

        result = collector.get_available_months(
            data_type='informe_diario',
            start_year=future_year,
            end_year=future_year
        )

        # Should be empty since all months are in the future
        assert result == []

    @patch('requests.Session.get')
    def test_download_file_success(self, mock_get, collector, tmp_path):
        """Test successful file download."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content = Mock(return_value=[b'test data'])
        mock_get.return_value = mock_response

        output_path = tmp_path / "test.zip"
        result = collector.download_file("http://example.com/file.zip", output_path)

        assert result is True
        assert output_path.exists()

    @patch('requests.Session.get')
    def test_download_file_http_404(self, mock_get, collector, tmp_path):
        """Test download with HTTP 404 error (no retry)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = Mock(side_effect=Exception("404 Not Found"))
        import requests
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)

        output_path = tmp_path / "test.zip"
        result = collector.download_file("http://example.com/file.zip", output_path, max_retries=2)

        assert result is False
        # Should not retry for 4xx errors
        assert mock_get.call_count == 1

    @patch('requests.Session.get')
    @patch('src.collectors.cvm_collector.time.sleep')
    def test_download_file_http_500_retry(self, mock_sleep, mock_get, collector, tmp_path):
        """Test download with HTTP 500 error (with retry)."""
        mock_response = Mock()
        mock_response.status_code = 500
        import requests
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)

        output_path = tmp_path / "test.zip"
        result = collector.download_file("http://example.com/file.zip", output_path, max_retries=3)

        assert result is False
        # Should retry for 5xx errors
        assert mock_get.call_count == 3
        # Should have exponential backoff
        assert mock_sleep.call_count >= 2

    @patch('requests.Session.get')
    @patch('src.collectors.cvm_collector.time.sleep')
    def test_download_file_generic_exception_retry(self, mock_sleep, mock_get, collector, tmp_path):
        """Test download with generic exception (with retry)."""
        mock_get.side_effect = Exception("Network timeout")

        output_path = tmp_path / "test.zip"
        result = collector.download_file("http://example.com/file.zip", output_path, max_retries=2)

        assert result is False
        assert mock_get.call_count == 2
        assert mock_sleep.call_count >= 1

    def test_extract_zip_success(self, collector, tmp_path):
        """Test successful ZIP extraction."""
        import zipfile

        # Create a test ZIP file
        zip_path = tmp_path / "test.zip"
        csv_content = "col1,col2\n1,2\n3,4"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.csv", csv_content)

        # Extract
        extract_path = tmp_path / "extracted"
        result = collector.extract_zip(zip_path, extract_to=extract_path)

        assert result is not None
        assert result.exists()
        assert result.suffix == '.csv'

    def test_extract_zip_no_csv(self, collector, tmp_path):
        """Test ZIP extraction with no CSV file."""
        import zipfile

        # Create a ZIP with no CSV
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.txt", "not a csv")

        result = collector.extract_zip(zip_path)

        # Should return None if no CSV found
        assert result is None

    def test_extract_zip_invalid_file(self, collector, tmp_path):
        """Test ZIP extraction with invalid file."""
        # Create a non-ZIP file
        invalid_zip = tmp_path / "not_a_zip.zip"
        invalid_zip.write_text("This is not a ZIP file")

        result = collector.extract_zip(invalid_zip)

        # Should handle the error gracefully
        assert result is None


class TestPartialDownloadCleanup:
    """A failed download must not leave a truncated file at the destination.

    _download_and_extract_monthly_zip skips the download when the ZIP already
    exists, so a truncated leftover poisoned that path permanently: every later
    run would skip the download and then fail to extract.
    """

    @patch('requests.Session.get')
    @patch('src.collectors.cvm_collector.time.sleep')
    def test_stream_failure_leaves_no_destination_file(self, mock_sleep, mock_get, tmp_path):
        collector = CVMCollector()

        def exploding_chunks(chunk_size=8192):
            yield b'partial data'
            raise ConnectionError("connection reset mid-stream")

        response = Mock()
        response.raise_for_status = Mock()
        response.headers = {'content-length': '999999'}
        response.iter_content = exploding_chunks
        mock_get.return_value = response

        output = tmp_path / 'inf_diario_fi_202401.zip'
        assert collector.download_file('http://example.com/f.zip', output) is False
        assert not output.exists(), "truncated download must not be left in place"
        assert not output.with_name(output.name + '.part').exists()

    @patch('requests.Session.get')
    def test_successful_download_writes_destination(self, mock_get, tmp_path):
        collector = CVMCollector()
        response = Mock()
        response.raise_for_status = Mock()
        response.headers = {'content-length': '4'}
        response.iter_content = Mock(return_value=[b'data'])
        mock_get.return_value = response

        output = tmp_path / 'ok.zip'
        assert collector.download_file('http://example.com/f.zip', output) is True
        assert output.read_bytes() == b'data'
        assert not output.with_name(output.name + '.part').exists()

    @patch('requests.Session.get')
    @patch('src.collectors.cvm_collector.time.sleep')
    def test_http_error_leaves_no_destination_file(self, mock_sleep, mock_get, tmp_path):
        collector = CVMCollector()
        error_response = Mock()
        error_response.status_code = 404
        response = Mock()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=error_response
        )
        mock_get.return_value = response

        output = tmp_path / 'missing.zip'
        assert collector.download_file('http://example.com/f.zip', output) is False
        assert not output.exists()


class TestDownloadPeriodDefaults:
    """download_period used a mutable list as its default argument."""

    def test_default_data_types_is_immutable(self):
        import inspect

        default = inspect.signature(CVMCollector.download_period).parameters['data_types'].default
        assert default is None
        assert isinstance(CVMCollector.DEFAULT_DATA_TYPES, tuple)

    @patch.object(CVMCollector, 'download_cadastro')
    @patch.object(CVMCollector, 'check_file_exists', return_value=False)
    def test_omitting_data_types_downloads_the_defaults(self, mock_exists, mock_cadastro):
        mock_cadastro.return_value = None
        collector = CVMCollector()
        collector.download_period(2024, 1, 2024, 1)
        mock_cadastro.assert_called_once()
