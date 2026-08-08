import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import shutil

from scripts.generate_public_report import PublicReportGenerator
from config.settings import Config


@pytest.fixture
def temp_config():
    """Create a temporary config with test directories"""
    temp_dir = Path(tempfile.mkdtemp())

    config = Config()
    config.REPORTS_DIR = temp_dir / 'reports'
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    yield config

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_flow_anomalies():
    """Create sample flow anomaly data"""
    return pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10', '11.111.111/0001-11'],
        'DT_COMPTC': ['2024-01-15', '2024-01-16', '2024-01-17'],
        'FLUXO_LIQ_DIA': [1000000, -500000, 750000],
        'Z_SCORE_FLOW': [5.2, -4.1, 3.8],
        'IS_ANOMALY_FLOW': [True, True, True]
    })


@pytest.fixture
def sample_pl_drops():
    """Create sample PL drops data"""
    return pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'DT_COMPTC': ['2024-01-20', '2024-01-21'],
        'VL_PATRIM_LIQ': [5000000, 3000000],
        'PL_VAR_PCT': [-25.5, -30.2],
        'IS_PL_DROP': [True, True]
    })


@pytest.fixture
def sample_runs():
    """Create sample runs data"""
    return pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90'] * 6,
        'DT_COMPTC': pd.date_range('2024-01-01', periods=6),
        'FLUXO_LIQ_DIA': [-10000, -20000, -15000, -25000, -18000, -22000],
        'IS_NEGATIVE_FLOW': [True] * 6,
        'RUN_LENGTH': [1, 2, 3, 4, 5, 6]
    })


@pytest.fixture
def sample_divergences():
    """Create sample divergence data"""
    return pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'DT_COMPTC': ['2024-01-10', '2024-01-11'],
        'FLUXO_LIQ_DIA': [500000, -300000],
        'RETORNO_DIA': [-2.5, 3.2],
        'Z_FLOW': [4.5, -3.8],
        'Z_RETORNO': [-3.2, 4.1]
    })


@pytest.fixture
def generator_with_data(temp_config, sample_flow_anomalies, sample_pl_drops, sample_runs, sample_divergences):
    """Create a generator with sample data files"""
    # Save sample data to temp reports directory
    sample_flow_anomalies.to_csv(temp_config.REPORTS_DIR / 'anomalias_fluxo.csv', sep=';', index=False)
    sample_pl_drops.to_csv(temp_config.REPORTS_DIR / 'quedas_pl.csv', sep=';', index=False)
    sample_runs.to_csv(temp_config.REPORTS_DIR / 'runs_resgate.csv', sep=';', index=False)
    sample_divergences.to_csv(temp_config.REPORTS_DIR / 'divergencias_flow_performance.csv', sep=';', index=False)

    generator = PublicReportGenerator(config=temp_config)
    return generator


def test_generator_initialization():
    """Test that generator initializes correctly"""
    generator = PublicReportGenerator()
    assert generator is not None
    assert generator.config is not None


def test_load_anomaly_reports(generator_with_data):
    """Test loading anomaly reports from files"""
    reports = generator_with_data.load_anomaly_reports()

    assert 'flow_anomalies' in reports
    assert 'pl_drops' in reports
    assert 'runs' in reports
    assert 'divergences' in reports

    assert len(reports['flow_anomalies']) == 3
    assert len(reports['pl_drops']) == 2
    assert len(reports['runs']) == 6
    assert len(reports['divergences']) == 2


def test_calculate_summary_statistics(generator_with_data):
    """Test calculation of summary statistics"""
    reports = generator_with_data.load_anomaly_reports()
    summary = generator_with_data.calculate_summary_statistics(reports)

    assert 'generation_date' in summary
    assert summary['flow_anomalies_count'] == 3
    assert summary['pl_drops_count'] == 2
    assert summary['runs_count'] == 6
    assert summary['divergences_count'] == 2
    assert summary['total_anomalies'] == 13
    assert summary['unique_funds_affected'] == 3  # 3 unique CNPJs in sample data


def test_anonymize_fund_data():
    """Test anonymization of fund data"""
    generator = PublicReportGenerator()

    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10', '12.345.678/0001-90'],
        'DENOM_SOCIAL': ['Fund A', 'Fund B', 'Fund A'],
        'VALUE': [100, 200, 150]
    })

    anonymized = generator.anonymize_fund_data(df)

    # CNPJ should be replaced with FUND_ID
    assert 'FUND_ID' in anonymized.columns
    assert 'CNPJ_FUNDO' not in anonymized.columns
    assert 'DENOM_SOCIAL' not in anonymized.columns

    # Check that same CNPJ gets same FUND_ID
    fund_ids = anonymized['FUND_ID'].tolist()
    assert fund_ids[0] == fund_ids[2]  # Same CNPJ
    assert fund_ids[0] != fund_ids[1]  # Different CNPJ


def test_anonymize_empty_dataframe():
    """Test anonymization of empty dataframe"""
    generator = PublicReportGenerator()
    df = pd.DataFrame()

    result = generator.anonymize_fund_data(df)
    assert result.empty


def test_generate_markdown_report(generator_with_data):
    """Test generation of markdown report"""
    markdown = generator_with_data.generate_report(output_format='markdown')

    # Check key sections are present
    assert '# REAG Fraud Investigation - Public Report' in markdown
    assert '## Executive Summary' in markdown
    assert '## Detailed Findings' in markdown
    assert '## Methodology' in markdown
    assert '## Disclaimer' in markdown

    # Check statistics are included (total should be 13 based on sample data)
    assert '13' in markdown  # total_anomalies
    assert '3' in markdown   # unique_funds_affected


def test_generate_json_report(generator_with_data):
    """Test generation of JSON report"""
    json_str = generator_with_data.generate_report(output_format='json')

    # Parse JSON to verify structure
    report = json.loads(json_str)

    assert 'metadata' in report
    assert 'summary' in report
    assert 'findings' in report

    assert report['metadata']['title'] == 'REAG Fraud Investigation - Public Report'
    assert report['summary']['total_anomalies'] == 13

    # Check that findings are anonymized
    if 'flow_anomalies' in report['findings']:
        for record in report['findings']['flow_anomalies']:
            assert 'CNPJ_FUNDO' not in record
            assert 'FUND_ID' in record


def test_generate_html_report(generator_with_data):
    """Test generation of HTML report"""
    html = generator_with_data.generate_report(output_format='html')

    # Check basic HTML structure
    assert '<!DOCTYPE html>' in html
    assert '<html lang="en">' in html
    assert '<title>REAG Fraud Investigation - Public Report</title>' in html

    # Check content is present
    assert 'Results Obtained' in html
    assert '13' in html  # total_anomalies
    assert 'Methods' in html


def test_generate_report_markdown(generator_with_data):
    """Test full report generation in markdown format"""
    output_file = generator_with_data.config.REPORTS_DIR / 'test_report.md'

    content = generator_with_data.generate_report(
        output_format='markdown',
        output_file=str(output_file)
    )

    assert output_file.exists()
    assert len(content) > 0
    assert '# REAG Fraud Investigation' in content


def test_generate_report_html(generator_with_data):
    """Test full report generation in HTML format"""
    output_file = generator_with_data.config.REPORTS_DIR / 'test_report.html'

    content = generator_with_data.generate_report(
        output_format='html',
        output_file=str(output_file)
    )

    assert output_file.exists()
    assert len(content) > 0
    assert '<!DOCTYPE html>' in content


def test_generate_report_json(generator_with_data):
    """Test full report generation in JSON format"""
    output_file = generator_with_data.config.REPORTS_DIR / 'test_report.json'

    content = generator_with_data.generate_report(
        output_format='json',
        output_file=str(output_file)
    )

    assert output_file.exists()
    assert len(content) > 0

    # Verify valid JSON
    report = json.loads(content)
    assert 'metadata' in report
    assert 'summary' in report
    assert 'findings' in report


def test_generate_report_invalid_format(generator_with_data):
    """Test that invalid format raises error"""
    with pytest.raises(ValueError):
        generator_with_data.generate_report(output_format='invalid')


def test_severity_distribution(generator_with_data):
    """Test severity distribution calculation"""
    reports = generator_with_data.load_anomaly_reports()
    summary = generator_with_data.calculate_summary_statistics(reports)

    severity = summary['severity_distribution']

    # We have Z-scores of 5.2, -4.1, 3.8 in sample data
    assert severity['high'] >= 1  # |5.2| > 5
    assert severity['medium'] >= 1  # 3 < |4.1| <= 5
    assert severity['low'] >= 0


def test_empty_reports():
    """Test handling of empty reports"""
    temp_dir = Path(tempfile.mkdtemp())
    config = Config()
    config.REPORTS_DIR = temp_dir
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    generator = PublicReportGenerator(config=config)
    reports = generator.load_anomaly_reports()

    # All reports should be empty DataFrames
    assert all(df.empty for df in reports.values())

    summary = generator.calculate_summary_statistics(reports)
    assert summary['total_anomalies'] == 0
    assert summary['unique_funds_affected'] == 0

    # Should still generate valid report
    markdown = generator.generate_report(output_format='markdown')
    assert len(markdown) > 0
    assert 'REAG Fraud Investigation' in markdown

    # Cleanup
    shutil.rmtree(temp_dir)


# Error Handling Tests

def test_missing_csv_file_warning(temp_config, caplog):
    """Test that missing CSV files log warnings and return empty DataFrames"""
    import logging

    # Create generator with empty reports directory (no CSV files)
    generator = PublicReportGenerator(config=temp_config)

    with caplog.at_level(logging.WARNING):
        reports = generator.load_anomaly_reports()

    # All reports should be empty DataFrames
    assert all(df.empty for df in reports.values())

    # Check that warnings were logged for missing files
    assert any('Missing anomaly CSV file' in record.message for record in caplog.records)


def test_malformed_csv_handling(temp_config, caplog):
    """Test that malformed CSV files log errors and return empty DataFrames"""
    import logging

    # Create a malformed CSV file
    malformed_csv = temp_config.REPORTS_DIR / 'anomalias_fluxo.csv'
    malformed_csv.write_text('invalid;csv;content\nwith;mismatched;columns;extra', encoding='utf-8')

    generator = PublicReportGenerator(config=temp_config)

    with caplog.at_level(logging.ERROR):
        reports = generator.load_anomaly_reports()

    # The malformed file should result in empty DataFrame
    assert reports['flow_anomalies'].empty

    # Check that error was logged
    assert any('Failed to parse CSV file' in record.message for record in caplog.records)


def test_file_write_failure_raises_ioerror(generator_with_data, tmp_path):
    """Test that file write failures raise IOError with descriptive message.

    The write failure is mocked rather than provoked with a real unwritable
    path: the previous version targeted /root/invalid_path, which is writable
    when the suite runs as root (e.g. in a container), so the test silently
    inverted depending on the uid.
    """
    target = str(tmp_path / 'report.md')

    with patch.object(Path, 'write_text', side_effect=OSError("disk on fire")):
        with pytest.raises(IOError) as exc_info:
            generator_with_data.generate_report(
                output_format='markdown',
                output_file=target
            )

    # Check that error message is descriptive
    assert 'Failed to write report' in str(exc_info.value)
    assert target in str(exc_info.value)


def test_incomplete_summary_dict_raises_keyerror(generator_with_data):
    """Test that incomplete summary dict raises KeyError with missing key name"""
    reports = generator_with_data.load_anomaly_reports()

    # Create incomplete summary (missing required keys)
    incomplete_summary = {
        'generation_date': '2024-01-01',
        'total_anomalies': 10,
        # Missing other required keys
    }

    with pytest.raises(KeyError) as exc_info:
        generator_with_data._build_report_data(incomplete_summary, reports)

    # Check that error message includes the missing key name
    assert 'missing required key' in str(exc_info.value).lower()


def test_incomplete_severity_distribution_raises_keyerror(generator_with_data):
    """Test that incomplete severity distribution raises KeyError"""
    reports = generator_with_data.load_anomaly_reports()

    # Create summary with incomplete severity_distribution
    incomplete_summary = {
        'generation_date': '2024-01-01',
        'total_anomalies': 10,
        'unique_funds_affected': 3,
        'flow_anomalies_count': 3,
        'pl_drops_count': 2,
        'runs_count': 3,
        'divergences_count': 2,
        'severity_distribution': {
            'high': 5,
            # Missing 'medium' and 'low'
        }
    }

    with pytest.raises(KeyError) as exc_info:
        generator_with_data._build_report_data(incomplete_summary, reports)

    # Check that error message includes the missing key
    assert 'severity distribution missing required key' in str(exc_info.value).lower()


def test_file_write_permission_error_is_wrapped(temp_config):
    """A PermissionError from the filesystem surfaces as a descriptive IOError.

    Mocked rather than driven by chmod: root ignores the permission bits, so
    the chmod-based version of this test could not fail as intended when the
    suite runs as root.
    """
    output_file = temp_config.REPORTS_DIR / 'readonly' / 'report.md'
    generator = PublicReportGenerator(config=temp_config)

    with patch.object(Path, 'write_text', side_effect=PermissionError("Permission denied")):
        with pytest.raises(IOError) as exc_info:
            generator.generate_report(
                output_format='markdown',
                output_file=str(output_file)
            )

    assert 'Failed to write report' in str(exc_info.value)


def test_empty_csv_files_handled_gracefully(temp_config):
    """Test that empty CSV files are handled without errors"""
    # Create empty CSV files
    (temp_config.REPORTS_DIR / 'anomalias_fluxo.csv').write_text('', encoding='utf-8')
    (temp_config.REPORTS_DIR / 'quedas_pl.csv').write_text('', encoding='utf-8')

    generator = PublicReportGenerator(config=temp_config)
    reports = generator.load_anomaly_reports()

    # Should return empty DataFrames without errors
    assert reports['flow_anomalies'].empty
    assert reports['pl_drops'].empty


def test_csv_with_only_headers(temp_config):
    """Test CSV files with only headers (no data rows)"""
    # Create CSV with only headers
    csv_content = 'CNPJ_FUNDO;DT_COMPTC;FLUXO_LIQ_DIA;Z_SCORE_FLOW\n'
    (temp_config.REPORTS_DIR / 'anomalias_fluxo.csv').write_text(csv_content, encoding='utf-8')

    generator = PublicReportGenerator(config=temp_config)
    reports = generator.load_anomaly_reports()

    # Should return empty DataFrame (no data rows)
    assert reports['flow_anomalies'].empty


def test_all_required_summary_keys_validated():
    """Test that all required summary keys are validated"""
    generator = PublicReportGenerator()
    reports = {
        'flow_anomalies': pd.DataFrame(),
        'pl_drops': pd.DataFrame(),
        'runs': pd.DataFrame(),
        'divergences': pd.DataFrame(),
    }

    required_keys = [
        'generation_date',
        'total_anomalies',
        'unique_funds_affected',
        'flow_anomalies_count',
        'pl_drops_count',
        'runs_count',
        'divergences_count',
        'severity_distribution',
    ]

    # Test each missing key individually
    for missing_key in required_keys:
        summary = {
            'generation_date': '2024-01-01',
            'total_anomalies': 10,
            'unique_funds_affected': 3,
            'flow_anomalies_count': 3,
            'pl_drops_count': 2,
            'runs_count': 3,
            'divergences_count': 2,
            'severity_distribution': {'high': 1, 'medium': 2, 'low': 3},
        }

        # Remove the key we're testing
        del summary[missing_key]

        with pytest.raises(KeyError) as exc_info:
            generator._build_report_data(summary, reports)

        assert missing_key in str(exc_info.value).lower()
