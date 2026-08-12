"""Unit tests for report generation dataclasses and core components."""
import pytest
import pandas as pd
from datetime import datetime

from scripts.generate_public_report import (
    ReportMetadata,
    ExecutiveSummary,
    DetailedFindings,
    SeverityDistribution,
    AnonymizedDatasets,
    ReportData,
)


class TestReportMetadata:
    """Tests for ReportMetadata dataclass."""

    def test_valid_construction(self):
        """Test valid construction with all fields."""
        metadata = ReportMetadata(
            title="Test Report",
            generation_date="2024-01-15T10:30:00"
        )
        assert metadata.title == "Test Report"
        assert metadata.generation_date == "2024-01-15T10:30:00"

    def test_immutability(self):
        """Test immutability (frozen=True enforcement)."""
        metadata = ReportMetadata(
            title="Test Report",
            generation_date="2024-01-15T10:30:00"
        )
        with pytest.raises(AttributeError):
            metadata.title = "New Title"


class TestExecutiveSummary:
    """Tests for ExecutiveSummary dataclass."""

    def test_valid_construction(self):
        """Test valid construction with all fields."""
        summary = ExecutiveSummary(
            total_anomalies=100,
            unique_funds_affected=25
        )
        assert summary.total_anomalies == 100
        assert summary.unique_funds_affected == 25

    def test_immutability(self):
        """Test immutability (frozen=True enforcement)."""
        summary = ExecutiveSummary(
            total_anomalies=100,
            unique_funds_affected=25
        )
        with pytest.raises(AttributeError):
            summary.total_anomalies = 200

    def test_zero_values(self):
        """Test with zero values."""
        summary = ExecutiveSummary(
            total_anomalies=0,
            unique_funds_affected=0
        )
        assert summary.total_anomalies == 0
        assert summary.unique_funds_affected == 0


class TestDetailedFindings:
    """Tests for DetailedFindings dataclass."""

    def test_valid_construction(self):
        """Test valid construction with all fields."""
        findings = DetailedFindings(
            flow_anomalies_count=30,
            pl_drops_count=20,
            runs_count=15,
            divergences_count=35
        )
        assert findings.flow_anomalies_count == 30
        assert findings.pl_drops_count == 20
        assert findings.runs_count == 15
        assert findings.divergences_count == 35

    def test_immutability(self):
        """Test immutability (frozen=True enforcement)."""
        findings = DetailedFindings(
            flow_anomalies_count=30,
            pl_drops_count=20,
            runs_count=15,
            divergences_count=35
        )
        with pytest.raises(AttributeError):
            findings.flow_anomalies_count = 50

    def test_all_zeros(self):
        """Test with all zero counts."""
        findings = DetailedFindings(
            flow_anomalies_count=0,
            pl_drops_count=0,
            runs_count=0,
            divergences_count=0
        )
        assert findings.flow_anomalies_count == 0
        assert findings.pl_drops_count == 0


class TestSeverityDistribution:
    """Tests for SeverityDistribution dataclass."""

    def test_valid_construction(self):
        """Test valid construction with all fields."""
        severity = SeverityDistribution(
            high=10,
            medium=25,
            low=65
        )
        assert severity.high == 10
        assert severity.medium == 25
        assert severity.low == 65

    def test_immutability(self):
        """Test immutability (frozen=True enforcement)."""
        severity = SeverityDistribution(
            high=10,
            medium=25,
            low=65
        )
        with pytest.raises(AttributeError):
            severity.high = 20


class TestAnonymizedDatasets:
    """Tests for AnonymizedDatasets dataclass."""

    def test_valid_construction_with_dataframes(self):
        """Test valid construction with all DataFrame fields."""
        df1 = pd.DataFrame({"FUND_ID": ["FUND_0001"], "VALUE": [100]})
        df2 = pd.DataFrame({"FUND_ID": ["FUND_0002"], "VALUE": [200]})
        df3 = pd.DataFrame({"FUND_ID": ["FUND_0003"], "VALUE": [300]})
        df4 = pd.DataFrame({"FUND_ID": ["FUND_0004"], "VALUE": [400]})

        datasets = AnonymizedDatasets(
            flow_anomalies=df1,
            pl_drops=df2,
            runs=df3,
            divergences=df4
        )

        assert len(datasets.flow_anomalies) == 1
        assert len(datasets.pl_drops) == 1
        assert len(datasets.runs) == 1
        assert len(datasets.divergences) == 1

    def test_with_empty_dataframes(self):
        """Test with empty DataFrames."""
        datasets = AnonymizedDatasets(
            flow_anomalies=pd.DataFrame(),
            pl_drops=pd.DataFrame(),
            runs=pd.DataFrame(),
            divergences=pd.DataFrame()
        )

        assert datasets.flow_anomalies.empty
        assert datasets.pl_drops.empty
        assert datasets.runs.empty
        assert datasets.divergences.empty

    def test_immutability(self):
        """Test immutability (frozen=True enforcement)."""
        datasets = AnonymizedDatasets(
            flow_anomalies=pd.DataFrame(),
            pl_drops=pd.DataFrame(),
            runs=pd.DataFrame(),
            divergences=pd.DataFrame()
        )

        with pytest.raises(AttributeError):
            datasets.flow_anomalies = pd.DataFrame({"NEW": [1]})


class TestReportData:
    """Tests for complete ReportData dataclass."""

    @pytest.fixture
    def sample_report_data(self):
        """Create a sample ReportData instance."""
        metadata = ReportMetadata(
            title="Test Report",
            generation_date="2024-01-15T10:30:00"
        )

        executive_summary = ExecutiveSummary(
            total_anomalies=100,
            unique_funds_affected=25
        )

        detailed_findings = DetailedFindings(
            flow_anomalies_count=30,
            pl_drops_count=20,
            runs_count=15,
            divergences_count=35
        )

        severity = SeverityDistribution(
            high=10,
            medium=25,
            low=65
        )

        datasets = AnonymizedDatasets(
            flow_anomalies=pd.DataFrame({"FUND_ID": ["FUND_0001"], "VALUE": [100]}),
            pl_drops=pd.DataFrame({"FUND_ID": ["FUND_0002"], "VALUE": [200]}),
            runs=pd.DataFrame({"FUND_ID": ["FUND_0003"], "VALUE": [300]}),
            divergences=pd.DataFrame({"FUND_ID": ["FUND_0004"], "VALUE": [400]})
        )

        return ReportData(
            metadata=metadata,
            executive_summary=executive_summary,
            detailed_findings=detailed_findings,
            severity_distribution=severity,
            datasets=datasets,
            methodology_text="Test methodology",
            disclaimer_text="Test disclaimer"
        )

    def test_valid_construction(self, sample_report_data):
        """Test valid construction with all fields."""
        data = sample_report_data

        assert data.metadata.title == "Test Report"
        assert data.executive_summary.total_anomalies == 100
        assert data.detailed_findings.flow_anomalies_count == 30
        assert data.severity_distribution.high == 10
        assert len(data.datasets.flow_anomalies) == 1
        assert data.methodology_text == "Test methodology"
        assert data.disclaimer_text == "Test disclaimer"

    def test_immutability(self, sample_report_data):
        """Test immutability (frozen=True enforcement)."""
        data = sample_report_data

        with pytest.raises(AttributeError):
            data.methodology_text = "New methodology"

    def test_nested_dataclass_types(self, sample_report_data):
        """Test that all nested dataclasses are properly initialized."""
        data = sample_report_data

        assert isinstance(data.metadata, ReportMetadata)
        assert isinstance(data.executive_summary, ExecutiveSummary)
        assert isinstance(data.detailed_findings, DetailedFindings)
        assert isinstance(data.severity_distribution, SeverityDistribution)
        assert isinstance(data.datasets, AnonymizedDatasets)

    def test_with_empty_datasets(self):
        """Test ReportData with empty DataFrames."""
        metadata = ReportMetadata(
            title="Empty Report",
            generation_date="2024-01-15T10:30:00"
        )

        executive_summary = ExecutiveSummary(
            total_anomalies=0,
            unique_funds_affected=0
        )

        detailed_findings = DetailedFindings(
            flow_anomalies_count=0,
            pl_drops_count=0,
            runs_count=0,
            divergences_count=0
        )

        severity = SeverityDistribution(high=0, medium=0, low=0)

        datasets = AnonymizedDatasets(
            flow_anomalies=pd.DataFrame(),
            pl_drops=pd.DataFrame(),
            runs=pd.DataFrame(),
            divergences=pd.DataFrame()
        )

        data = ReportData(
            metadata=metadata,
            executive_summary=executive_summary,
            detailed_findings=detailed_findings,
            severity_distribution=severity,
            datasets=datasets,
            methodology_text="Test methodology",
            disclaimer_text="Test disclaimer"
        )

        assert data.executive_summary.total_anomalies == 0
        assert data.datasets.flow_anomalies.empty
