"""Unit tests for _build_report_data method."""
import pytest
import pandas as pd
from datetime import datetime

from scripts.generate_public_report import (
    PublicReportGenerator,
    ReportData,
    ReportMetadata,
    ExecutiveSummary,
    DetailedFindings,
    SeverityDistribution,
    AnonymizedDatasets,
)
from config.settings import Config


@pytest.fixture
def generator():
    """Create a PublicReportGenerator instance."""
    return PublicReportGenerator()


@pytest.fixture
def sample_summary():
    """Create sample summary statistics."""
    return {
        "generation_date": "2024-01-15T10:30:00",
        "total_anomalies": 100,
        "unique_funds_affected": 25,
        "flow_anomalies_count": 30,
        "pl_drops_count": 20,
        "runs_count": 15,
        "divergences_count": 35,
        "severity_distribution": {
            "high": 10,
            "medium": 25,
            "low": 65
        }
    }


@pytest.fixture
def sample_reports():
    """Create sample report DataFrames."""
    return {
        "flow_anomalies": pd.DataFrame({
            "CNPJ_FUNDO": ["12.345.678/0001-90", "98.765.432/0001-10"],
            "DENOM_SOCIAL": ["Fund A", "Fund B"],
            "VALUE": [100, 200]
        }),
        "pl_drops": pd.DataFrame({
            "CNPJ_FUNDO": ["11.111.111/0001-11"],
            "DENOM_SOCIAL": ["Fund C"],
            "VALUE": [300]
        }),
        "runs": pd.DataFrame({
            "CNPJ_FUNDO": ["22.222.222/0001-22"],
            "VALUE": [400]
        }),
        "divergences": pd.DataFrame({
            "CNPJ_FUNDO": ["33.333.333/0001-33"],
            "VALUE": [500]
        })
    }


class TestBuildReportData:
    """Tests for _build_report_data method."""
    
    def test_returns_report_data_instance(self, generator, sample_summary, sample_reports):
        """Test that method returns a ReportData instance."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert isinstance(result, ReportData)
    
    def test_all_nested_dataclasses_initialized(self, generator, sample_summary, sample_reports):
        """Test that all nested dataclasses are properly initialized."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert isinstance(result.metadata, ReportMetadata)
        assert isinstance(result.executive_summary, ExecutiveSummary)
        assert isinstance(result.detailed_findings, DetailedFindings)
        assert isinstance(result.severity_distribution, SeverityDistribution)
        assert isinstance(result.datasets, AnonymizedDatasets)
    
    def test_metadata_populated_correctly(self, generator, sample_summary, sample_reports):
        """Test that metadata is populated correctly."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert result.metadata.title == "REAG Fraud Investigation - Public Report"
        assert result.metadata.generation_date == "2024-01-15T10:30:00"
    
    def test_executive_summary_populated_correctly(self, generator, sample_summary, sample_reports):
        """Test that executive summary is populated correctly."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert result.executive_summary.total_anomalies == 100
        assert result.executive_summary.unique_funds_affected == 25
    
    def test_detailed_findings_populated_correctly(self, generator, sample_summary, sample_reports):
        """Test that detailed findings are populated correctly."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert result.detailed_findings.flow_anomalies_count == 30
        assert result.detailed_findings.pl_drops_count == 20
        assert result.detailed_findings.runs_count == 15
        assert result.detailed_findings.divergences_count == 35
    
    def test_severity_distribution_populated_correctly(self, generator, sample_summary, sample_reports):
        """Test that severity distribution is populated correctly."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert result.severity_distribution.high == 10
        assert result.severity_distribution.medium == 25
        assert result.severity_distribution.low == 65
    
    def test_all_datasets_anonymized(self, generator, sample_summary, sample_reports):
        """Test that all datasets are anonymized (no CNPJ_FUNDO or DENOM_SOCIAL)."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        # Check flow_anomalies
        assert "CNPJ_FUNDO" not in result.datasets.flow_anomalies.columns
        assert "DENOM_SOCIAL" not in result.datasets.flow_anomalies.columns
        assert "FUND_ID" in result.datasets.flow_anomalies.columns
        
        # Check pl_drops
        assert "CNPJ_FUNDO" not in result.datasets.pl_drops.columns
        assert "DENOM_SOCIAL" not in result.datasets.pl_drops.columns
        assert "FUND_ID" in result.datasets.pl_drops.columns
        
        # Check runs
        assert "CNPJ_FUNDO" not in result.datasets.runs.columns
        assert "FUND_ID" in result.datasets.runs.columns
        
        # Check divergences
        assert "CNPJ_FUNDO" not in result.datasets.divergences.columns
        assert "FUND_ID" in result.datasets.divergences.columns
    
    def test_with_empty_dataframes(self, generator):
        """Test with empty DataFrames."""
        summary = {
            "generation_date": "2024-01-15T10:30:00",
            "total_anomalies": 0,
            "unique_funds_affected": 0,
            "flow_anomalies_count": 0,
            "pl_drops_count": 0,
            "runs_count": 0,
            "divergences_count": 0,
            "severity_distribution": {"high": 0, "medium": 0, "low": 0}
        }
        
        reports = {
            "flow_anomalies": pd.DataFrame(),
            "pl_drops": pd.DataFrame(),
            "runs": pd.DataFrame(),
            "divergences": pd.DataFrame()
        }
        
        result = generator._build_report_data(summary, reports)
        
        assert isinstance(result, ReportData)
        assert result.executive_summary.total_anomalies == 0
        assert result.datasets.flow_anomalies.empty
        assert result.datasets.pl_drops.empty
        assert result.datasets.runs.empty
        assert result.datasets.divergences.empty
    
    def test_methodology_text_present(self, generator, sample_summary, sample_reports):
        """Test that methodology text is present."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert isinstance(result.methodology_text, str)
        assert len(result.methodology_text) > 0
        assert "investigation pipeline" in result.methodology_text.lower()
    
    def test_disclaimer_text_present(self, generator, sample_summary, sample_reports):
        """Test that disclaimer text is present."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        assert isinstance(result.disclaimer_text, str)
        assert len(result.disclaimer_text) > 0
        assert "automated" in result.disclaimer_text.lower()
    
    def test_result_is_immutable(self, generator, sample_summary, sample_reports):
        """Test that result is immutable (frozen=True)."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        with pytest.raises(AttributeError):
            result.methodology_text = "New text"
    
    def test_preserves_data_values(self, generator, sample_summary, sample_reports):
        """Test that data values are preserved correctly."""
        result = generator._build_report_data(sample_summary, sample_reports)
        
        # Check that VALUE columns are preserved
        assert "VALUE" in result.datasets.flow_anomalies.columns
        assert "VALUE" in result.datasets.pl_drops.columns
        assert "VALUE" in result.datasets.runs.columns
        assert "VALUE" in result.datasets.divergences.columns
        
        # Check that values match (after anonymization)
        assert len(result.datasets.flow_anomalies) == 2
        assert len(result.datasets.pl_drops) == 1
        assert len(result.datasets.runs) == 1
        assert len(result.datasets.divergences) == 1
