import pytest
import pandas as pd
import sys
from pathlib import Path
import json
import tempfile
import shutil

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

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
    reports = generator_with_data.load_anomaly_reports()
    summary = generator_with_data.calculate_summary_statistics(reports)
    
    markdown = generator_with_data.generate_markdown_report(summary, reports)
    
    # Check key sections are present
    assert '# REAG Fraud Investigation - Public Report' in markdown
    assert '## Executive Summary' in markdown
    assert '## Detailed Findings' in markdown
    assert '## Methodology' in markdown
    assert '## Disclaimer' in markdown
    
    # Check statistics are included
    assert str(summary['total_anomalies']) in markdown
    assert str(summary['unique_funds_affected']) in markdown


def test_generate_json_report(generator_with_data):
    """Test generation of JSON report"""
    reports = generator_with_data.load_anomaly_reports()
    summary = generator_with_data.calculate_summary_statistics(reports)
    
    json_str = generator_with_data.generate_json_report(summary, reports)
    
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
    reports = generator_with_data.load_anomaly_reports()
    summary = generator_with_data.calculate_summary_statistics(reports)
    
    html = generator_with_data.generate_html_report(summary, reports)
    
    # Check basic HTML structure
    assert '<!DOCTYPE html>' in html
    assert '<html lang="en">' in html
    assert '<title>REAG Fraud Investigation - Public Report</title>' in html
    
    # Check content is present
    assert 'Executive Summary' in html
    assert str(summary['total_anomalies']) in html
    assert 'Methodology' in html
    assert 'Disclaimer' in html


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
    markdown = generator.generate_markdown_report(summary, reports)
    assert len(markdown) > 0
    assert 'REAG Fraud Investigation' in markdown
    
    # Cleanup
    shutil.rmtree(temp_dir)
