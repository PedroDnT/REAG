"""Unit tests for report renderers."""
import json
import pytest
import pandas as pd
from dataclasses import replace
from html.parser import HTMLParser

from scripts.generate_public_report import (
    ReportMetadata,
    ExecutiveSummary,
    DetailedFindings,
    SeverityDistribution,
    AnonymizedDatasets,
    ReportData,
    MarkdownRenderer,
    HtmlRenderer,
    JsonRenderer,
)


@pytest.fixture
def sample_report_data():
    """Create a sample ReportData instance for testing."""
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
        flow_anomalies=pd.DataFrame({"FUND_ID": ["FUND_0001", "FUND_0002"], "VALUE": [100, 200]}),
        pl_drops=pd.DataFrame({"FUND_ID": ["FUND_0003"], "VALUE": [300]}),
        runs=pd.DataFrame({"FUND_ID": ["FUND_0004"], "VALUE": [400]}),
        divergences=pd.DataFrame({"FUND_ID": ["FUND_0005"], "VALUE": [500]})
    )

    return ReportData(
        metadata=metadata,
        executive_summary=executive_summary,
        detailed_findings=detailed_findings,
        severity_distribution=severity,
        datasets=datasets,
        methodology_text="Test methodology text",
        disclaimer_text="Test disclaimer text"
    )


@pytest.fixture
def empty_report_data():
    """Create a ReportData instance with empty datasets."""
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

    return ReportData(
        metadata=metadata,
        executive_summary=executive_summary,
        detailed_findings=detailed_findings,
        severity_distribution=severity,
        datasets=datasets,
        methodology_text="Test methodology",
        disclaimer_text="Test disclaimer"
    )


class TestMarkdownRenderer:
    """Tests for MarkdownRenderer."""

    def test_render_returns_string(self, sample_report_data):
        """Test that render returns a non-empty string."""
        renderer = MarkdownRenderer()
        output = renderer.render(sample_report_data)

        assert isinstance(output, str)
        assert len(output) > 0

    def test_output_has_valid_markdown_syntax(self, sample_report_data):
        """Test that output has valid Markdown syntax."""
        renderer = MarkdownRenderer()
        output = renderer.render(sample_report_data)

        # Check for markdown headers
        assert "# Test Report" in output
        assert "## Executive Summary" in output
        assert "## Detailed Findings" in output
        assert "## Methodology" in output
        assert "## Disclaimer" in output

    def test_all_sections_present(self, sample_report_data):
        """Test that all sections are present in output."""
        renderer = MarkdownRenderer()
        output = renderer.render(sample_report_data)

        # Check metadata
        assert "Test Report" in output
        assert "2024-01-15T10:30:00" in output

        # Check executive summary
        assert "100" in output  # total_anomalies
        assert "25" in output   # unique_funds_affected

        # Check detailed findings
        assert "30" in output  # flow_anomalies_count
        assert "20" in output  # pl_drops_count
        assert "15" in output  # runs_count
        assert "35" in output  # divergences_count

        # Check text sections
        assert "Test methodology text" in output
        assert "Test disclaimer text" in output

    def test_with_empty_datasets(self, empty_report_data):
        """Test rendering with empty datasets."""
        renderer = MarkdownRenderer()
        output = renderer.render(empty_report_data)

        assert isinstance(output, str)
        assert len(output) > 0
        assert "Empty Report" in output
        assert "0" in output  # Should show zero counts


class TestHtmlRenderer:
    """Tests for HtmlRenderer."""

    def test_render_returns_string(self, sample_report_data):
        """Test that render returns a non-empty string."""
        renderer = HtmlRenderer()
        output = renderer.render(sample_report_data)

        assert isinstance(output, str)
        assert len(output) > 0

    def test_output_is_valid_html5(self, sample_report_data):
        """Test that output is valid HTML5."""
        renderer = HtmlRenderer()
        output = renderer.render(sample_report_data)

        # Check for HTML5 doctype and structure
        assert "<!DOCTYPE html>" in output
        assert "<html lang=\"en\">" in output
        assert "<head>" in output
        assert "<body>" in output
        assert "</html>" in output

        # Check for proper meta tags
        assert '<meta charset="utf-8"' in output
        assert '<meta name="viewport"' in output

    def test_html_can_be_parsed(self, sample_report_data):
        """Test that HTML can be parsed without errors."""
        renderer = HtmlRenderer()
        output = renderer.render(sample_report_data)

        # Try to parse HTML - will raise exception if invalid
        parser = HTMLParser()
        parser.feed(output)

    def test_all_sections_present(self, sample_report_data):
        """Test that all sections are present in output."""
        renderer = HtmlRenderer()
        output = renderer.render(sample_report_data)

        # Check title
        assert "<title>Test Report</title>" in output
        assert "<h1>Test Report</h1>" in output

        # Check sections
        assert "Executive Summary" in output
        assert "Detailed Findings" in output
        assert "Methodology" in output
        assert "Disclaimer" in output

        # Check data
        assert "100" in output  # total_anomalies
        assert "25" in output   # unique_funds_affected
        assert "Test methodology text" in output
        assert "Test disclaimer text" in output

    def test_with_empty_datasets(self, empty_report_data):
        """Test rendering with empty datasets."""
        renderer = HtmlRenderer()
        output = renderer.render(empty_report_data)

        assert isinstance(output, str)
        assert len(output) > 0
        assert "Empty Report" in output
        assert "<!DOCTYPE html>" in output


class TestJsonRenderer:
    """Tests for JsonRenderer."""

    def test_render_returns_string(self, sample_report_data):
        """Test that render returns a non-empty string."""
        renderer = JsonRenderer()
        output = renderer.render(sample_report_data)

        assert isinstance(output, str)
        assert len(output) > 0

    def test_output_is_valid_json(self, sample_report_data):
        """Test that output is valid JSON that can be parsed."""
        renderer = JsonRenderer()
        output = renderer.render(sample_report_data)

        # Should not raise exception
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_all_sections_present(self, sample_report_data):
        """Test that all sections are present in JSON output."""
        renderer = JsonRenderer()
        output = renderer.render(sample_report_data)

        data = json.loads(output)

        # Check top-level keys
        assert "metadata" in data
        assert "summary" in data
        assert "findings" in data

        # Check metadata
        assert data["metadata"]["title"] == "Test Report"
        assert data["metadata"]["generation_date"] == "2024-01-15T10:30:00"

        # Check summary
        assert data["summary"]["total_anomalies"] == 100
        assert data["summary"]["unique_funds_affected"] == 25
        assert data["summary"]["flow_anomalies_count"] == 30
        assert data["summary"]["pl_drops_count"] == 20
        assert data["summary"]["runs_count"] == 15
        assert data["summary"]["divergences_count"] == 35

        # Check severity distribution
        assert data["summary"]["severity_distribution"]["high"] == 10
        assert data["summary"]["severity_distribution"]["medium"] == 25
        assert data["summary"]["severity_distribution"]["low"] == 65

        # Check findings structure
        assert "flow_anomalies" in data["findings"]
        assert "pl_drops" in data["findings"]
        assert "runs" in data["findings"]
        assert "divergences" in data["findings"]

    def test_dataframes_converted_to_records(self, sample_report_data):
        """Test that DataFrames are converted to JSON records."""
        renderer = JsonRenderer()
        output = renderer.render(sample_report_data)

        data = json.loads(output)

        # Check that findings contain lists of records
        assert isinstance(data["findings"]["flow_anomalies"], list)
        assert len(data["findings"]["flow_anomalies"]) == 2

        # Check record structure
        record = data["findings"]["flow_anomalies"][0]
        assert "FUND_ID" in record
        assert "VALUE" in record

    def test_with_empty_datasets(self, empty_report_data):
        """Test rendering with empty datasets."""
        renderer = JsonRenderer()
        output = renderer.render(empty_report_data)

        data = json.loads(output)

        # Empty datasets should result in empty arrays
        assert data["findings"]["flow_anomalies"] == []
        assert data["findings"]["pl_drops"] == []
        assert data["findings"]["runs"] == []
        assert data["findings"]["divergences"] == []

        # But structure should still be valid
        assert data["summary"]["total_anomalies"] == 0


# Property-based tests using hypothesis
from hypothesis import given, strategies as st, settings
from hypothesis.extra.pandas import data_frames, column


def report_metadata_strategy():
    """Strategy for generating ReportMetadata instances."""
    return st.builds(
        ReportMetadata,
        title=st.text(min_size=1, max_size=100),
        generation_date=st.datetimes().map(lambda dt: dt.isoformat())
    )


def executive_summary_strategy():
    """Strategy for generating ExecutiveSummary instances."""
    return st.builds(
        ExecutiveSummary,
        total_anomalies=st.integers(min_value=0, max_value=10000),
        unique_funds_affected=st.integers(min_value=0, max_value=1000)
    )


def detailed_findings_strategy():
    """Strategy for generating DetailedFindings instances."""
    return st.builds(
        DetailedFindings,
        flow_anomalies_count=st.integers(min_value=0, max_value=5000),
        pl_drops_count=st.integers(min_value=0, max_value=5000),
        runs_count=st.integers(min_value=0, max_value=5000),
        divergences_count=st.integers(min_value=0, max_value=5000)
    )


def severity_distribution_strategy():
    """Strategy for generating SeverityDistribution instances."""
    return st.builds(
        SeverityDistribution,
        high=st.integers(min_value=0, max_value=1000),
        medium=st.integers(min_value=0, max_value=1000),
        low=st.integers(min_value=0, max_value=1000)
    )


def anonymized_datasets_strategy():
    """Strategy for generating AnonymizedDatasets instances."""
    # Generate simple DataFrames with FUND_ID and VALUE columns
    fund_id_column = column("FUND_ID", dtype="object", elements=st.text(
        alphabet="FUND_0123456789",
        min_size=9,
        max_size=9
    ))
    value_column = column("VALUE", dtype="int64", elements=st.integers(min_value=0, max_value=1000000))

    df_strategy = st.one_of(
        st.just(pd.DataFrame()),  # Empty DataFrame
        data_frames(columns=[fund_id_column, value_column], rows=st.tuples(
            st.text(alphabet="FUND_0123456789", min_size=9, max_size=9),
            st.integers(min_value=0, max_value=1000000)
        ))
    )

    return st.builds(
        AnonymizedDatasets,
        flow_anomalies=df_strategy,
        pl_drops=df_strategy,
        runs=df_strategy,
        divergences=df_strategy
    )


def report_data_strategy():
    """Strategy for generating ReportData instances."""
    return st.builds(
        ReportData,
        metadata=report_metadata_strategy(),
        executive_summary=executive_summary_strategy(),
        detailed_findings=detailed_findings_strategy(),
        severity_distribution=severity_distribution_strategy(),
        datasets=anonymized_datasets_strategy(),
        methodology_text=st.text(min_size=1, max_size=500),
        disclaimer_text=st.text(min_size=1, max_size=500)
    )


class TestRendererDeterminism:
    """Property-based tests for renderer determinism.

    **Validates: Requirements 4.5, 9.2**
    """

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_markdown_renderer_determinism(self, data):
        """Test that MarkdownRenderer produces identical output for same input.

        Property 3: Renderer Determinism
        FOR ALL renderers, calling render with the same ReportData SHALL produce
        identical output (determinism).
        """
        renderer = MarkdownRenderer()
        output1 = renderer.render(data)
        output2 = renderer.render(data)

        assert output1 == output2, "MarkdownRenderer should produce identical output for same input"

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_html_renderer_determinism(self, data):
        """Test that HtmlRenderer produces identical output for same input.

        Property 3: Renderer Determinism
        FOR ALL renderers, calling render with the same ReportData SHALL produce
        identical output (determinism).
        """
        renderer = HtmlRenderer()
        output1 = renderer.render(data)
        output2 = renderer.render(data)

        assert output1 == output2, "HtmlRenderer should produce identical output for same input"

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_json_renderer_determinism(self, data):
        """Test that JsonRenderer produces identical output for same input.

        Property 3: Renderer Determinism
        FOR ALL renderers, calling render with the same ReportData SHALL produce
        identical output (determinism).
        """
        renderer = JsonRenderer()
        output1 = renderer.render(data)
        output2 = renderer.render(data)

        assert output1 == output2, "JsonRenderer should produce identical output for same input"


class TestRendererImmutability:
    """Property-based tests for renderer immutability (no side effects).

    **Validates: Requirements 9.1, 9.5**
    """

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_markdown_renderer_no_side_effects(self, data):
        """Test that MarkdownRenderer does not modify input ReportData.

        Property 6: No Side Effects
        WHEN a Renderer processes ReportData, THE Renderer SHALL not modify
        the input data. WHEN rendering completes, THE original ReportData
        instance SHALL be unchanged.
        """
        renderer = MarkdownRenderer()

        # Create a deep copy to compare against
        import copy
        data_before = copy.deepcopy(data)

        # Render the report
        _ = renderer.render(data)

        # Verify data is unchanged
        assert data.metadata == data_before.metadata, "Metadata should not be modified"
        assert data.executive_summary == data_before.executive_summary, "Executive summary should not be modified"
        assert data.detailed_findings == data_before.detailed_findings, "Detailed findings should not be modified"
        assert data.severity_distribution == data_before.severity_distribution, "Severity distribution should not be modified"
        assert data.methodology_text == data_before.methodology_text, "Methodology text should not be modified"
        assert data.disclaimer_text == data_before.disclaimer_text, "Disclaimer text should not be modified"

        # Verify DataFrames are unchanged
        assert data.datasets.flow_anomalies.equals(data_before.datasets.flow_anomalies), "Flow anomalies DataFrame should not be modified"
        assert data.datasets.pl_drops.equals(data_before.datasets.pl_drops), "PL drops DataFrame should not be modified"
        assert data.datasets.runs.equals(data_before.datasets.runs), "Runs DataFrame should not be modified"
        assert data.datasets.divergences.equals(data_before.datasets.divergences), "Divergences DataFrame should not be modified"

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_html_renderer_no_side_effects(self, data):
        """Test that HtmlRenderer does not modify input ReportData.

        Property 6: No Side Effects
        WHEN a Renderer processes ReportData, THE Renderer SHALL not modify
        the input data. WHEN rendering completes, THE original ReportData
        instance SHALL be unchanged.
        """
        renderer = HtmlRenderer()

        # Create a deep copy to compare against
        import copy
        data_before = copy.deepcopy(data)

        # Render the report
        _ = renderer.render(data)

        # Verify data is unchanged
        assert data.metadata == data_before.metadata, "Metadata should not be modified"
        assert data.executive_summary == data_before.executive_summary, "Executive summary should not be modified"
        assert data.detailed_findings == data_before.detailed_findings, "Detailed findings should not be modified"
        assert data.severity_distribution == data_before.severity_distribution, "Severity distribution should not be modified"
        assert data.methodology_text == data_before.methodology_text, "Methodology text should not be modified"
        assert data.disclaimer_text == data_before.disclaimer_text, "Disclaimer text should not be modified"

        # Verify DataFrames are unchanged
        assert data.datasets.flow_anomalies.equals(data_before.datasets.flow_anomalies), "Flow anomalies DataFrame should not be modified"
        assert data.datasets.pl_drops.equals(data_before.datasets.pl_drops), "PL drops DataFrame should not be modified"
        assert data.datasets.runs.equals(data_before.datasets.runs), "Runs DataFrame should not be modified"
        assert data.datasets.divergences.equals(data_before.datasets.divergences), "Divergences DataFrame should not be modified"

    @given(data=report_data_strategy())
    @settings(max_examples=10)
    def test_json_renderer_no_side_effects(self, data):
        """Test that JsonRenderer does not modify input ReportData.

        Property 6: No Side Effects
        WHEN a Renderer processes ReportData, THE Renderer SHALL not modify
        the input data. WHEN rendering completes, THE original ReportData
        instance SHALL be unchanged.
        """
        renderer = JsonRenderer()

        # Create a deep copy to compare against
        import copy
        data_before = copy.deepcopy(data)

        # Render the report
        _ = renderer.render(data)

        # Verify data is unchanged
        assert data.metadata == data_before.metadata, "Metadata should not be modified"
        assert data.executive_summary == data_before.executive_summary, "Executive summary should not be modified"
        assert data.detailed_findings == data_before.detailed_findings, "Detailed findings should not be modified"
        assert data.severity_distribution == data_before.severity_distribution, "Severity distribution should not be modified"
        assert data.methodology_text == data_before.methodology_text, "Methodology text should not be modified"
        assert data.disclaimer_text == data_before.disclaimer_text, "Disclaimer text should not be modified"

        # Verify DataFrames are unchanged
        assert data.datasets.flow_anomalies.equals(data_before.datasets.flow_anomalies), "Flow anomalies DataFrame should not be modified"
        assert data.datasets.pl_drops.equals(data_before.datasets.pl_drops), "PL drops DataFrame should not be modified"
        assert data.datasets.runs.equals(data_before.datasets.runs), "Runs DataFrame should not be modified"
        assert data.datasets.divergences.equals(data_before.datasets.divergences), "Divergences DataFrame should not be modified"


class TestHtmlRendererEscaping:
    """HtmlRenderer interpolated text straight into an f-string template.

    Title and methodology/disclaimer text come from configuration and from CSV
    inputs, neither of which is guaranteed to be markup-safe.
    """

    @staticmethod
    def _render(sample_report_data, **overrides):
        """Render sample data with selected text fields overridden."""
        data = replace(sample_report_data, **{
            k: v for k, v in overrides.items()
            if k in {"methodology_text", "disclaimer_text"}
        })
        if "title" in overrides:
            data = replace(data, metadata=replace(data.metadata, title=overrides["title"]))
        return HtmlRenderer().render(data)

    def test_script_tag_in_title_is_escaped(self, sample_report_data):
        html_out = self._render(sample_report_data, title="<script>alert('x')</script>")
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out

    def test_angle_brackets_in_methodology_are_escaped(self, sample_report_data):
        html_out = self._render(sample_report_data, methodology_text="a < b and c > d")
        assert "a &lt; b and c &gt; d" in html_out

    def test_quotes_in_disclaimer_are_escaped(self, sample_report_data):
        html_out = self._render(sample_report_data, disclaimer_text='he said "hi" & left')
        assert "&amp;" in html_out
        assert '"hi"' not in html_out

    def test_document_structure_survives_escaping(self, sample_report_data):
        html_out = self._render(sample_report_data, title="Plain Title")
        assert html_out.startswith("<!DOCTYPE html>")
        assert "<h1>Plain Title</h1>" in html_out
        assert html_out.rstrip().endswith("</html>")
