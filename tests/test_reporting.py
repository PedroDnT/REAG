"""Tests for the ReportGenerator module."""

import pytest
import pandas as pd
from pathlib import Path
from src.utils.reporting import ReportGenerator


@pytest.fixture
def generator(tmp_path):
    return ReportGenerator(output_dir=tmp_path)


class TestReportGenerator:
    def test_init_creates_directory(self, tmp_path):
        out = tmp_path / "new_reports"
        ReportGenerator(output_dir=out)
        assert out.exists()

    def test_save_dataframe_csv(self, generator, tmp_path):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        path = generator.save_dataframe(df, "test.csv", format="csv")
        assert path.exists()
        loaded = pd.read_csv(path)
        assert len(loaded) == 2

    def test_save_dataframe_json(self, generator):
        df = pd.DataFrame({"X": [10]})
        path = generator.save_dataframe(df, "test.json", format="json")
        assert path.exists()

    def test_save_dataframe_html(self, generator):
        df = pd.DataFrame({"X": [10]})
        path = generator.save_dataframe(df, "test.html", format="html")
        assert path.exists()
        content = path.read_text()
        assert "<table" in content

    def test_save_dataframe_unsupported_format(self, generator):
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ValueError, match="Unsupported format"):
            generator.save_dataframe(df, "test.xyz", format="xyz")

    def test_create_summary_report(self, generator, tmp_path):
        results = {
            "Analysis A": pd.DataFrame({"val": [1, 2, 3]}),
            "Analysis B": pd.DataFrame({"cat": ["x", "y", "x"]}),
        }
        path = generator.create_summary_report(results, title="Test Summary")
        assert path.exists()
        content = path.read_text()
        assert "Test Summary" in content
        assert "Analysis A" in content
        assert "Total records: 3" in content

    def test_create_summary_report_empty_df(self, generator):
        results = {"Empty": pd.DataFrame()}
        path = generator.create_summary_report(results, title="Empty Report")
        assert path.exists()
        content = path.read_text()
        assert "Total records: 0" in content

    def test_create_markdown_report(self, generator):
        sections = [
            {"title": "Section 1", "content": "Some text"},
            {"title": "Section 2", "data": pd.DataFrame({"col": [1, 2]})},
        ]
        path = generator.create_markdown_report(sections, title="MD Report")
        assert path.exists()
        content = path.read_text()
        assert "# MD Report" in content
        assert "## Section 1" in content
        assert "Some text" in content

    def test_create_markdown_report_with_metrics(self, generator):
        sections = [
            {
                "title": "Metrics Section",
                "metrics": {"Total": 100, "Anomalies": 5},
            },
        ]
        path = generator.create_markdown_report(sections, title="Metrics")
        content = path.read_text()
        assert "**Total:**" in content
        assert "**Anomalies:**" in content

    def test_create_executive_summary(self, generator):
        path = generator.create_executive_summary(
            metrics={"Total Funds": 100, "Anomalies": 5},
            highlights=["Finding 1", "Finding 2"],
            recommendations=["Action 1"],
        )
        assert path.exists()
        content = path.read_text()
        assert "Executive Summary" in content
        assert "Finding 1" in content
        assert "Action 1" in content
        assert "Total Funds" in content
