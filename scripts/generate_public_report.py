"""Public Report Generator - Refactored Architecture.

This module generates public-facing (anonymized) fraud investigation reports
in multiple formats (Markdown, HTML, JSON). The refactored architecture
separates data preparation from presentation using a unified ReportData
dataclass and format-specific renderers.

The generator is now flexible and works with any fund investigation, not just
REAG-specific cases. The investigation name is configurable via settings.

Architecture:
    1. Data Model: Immutable ReportData dataclass captures all report content
    2. Renderers: Format-specific classes (MarkdownRenderer, HtmlRenderer,
       JsonRenderer) transform ReportData into target formats
    3. Generator: PublicReportGenerator orchestrates the workflow

Usage Examples:
    Generate Markdown report to stdout:
        >>> generator = PublicReportGenerator()
        >>> content = generator.generate_report(output_format="markdown")
        >>> print(content)

    Generate HTML report to file:
        >>> generator = PublicReportGenerator()
        >>> content = generator.generate_report(
        ...     output_format="html",
        ...     output_file="reports/public_report.html"
        ... )

    Generate JSON report with custom config:
        >>> from config.settings import Config
        >>> config = Config()
        >>> config.REPORTS_DIR = "custom/reports/path"
        >>> config.INVESTIGATION_NAME = "MyFund"
        >>> generator = PublicReportGenerator(config=config)
        >>> content = generator.generate_report(output_format="json")

Benefits:
    - Eliminates ~200 lines of duplicate logic
    - Single data structure built once, rendered multiple ways
    - Adding new formats requires only ~50 lines per renderer
    - Improved testability (data separate from presentation)
    - Type-safe with explicit annotations
    - Flexible for any fund investigation, not just REAG
"""
from __future__ import annotations

import argparse
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import Config

# Configure logging
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportPaths:
    flow_anomalies: str = "anomalias_fluxo.csv"
    pl_drops: str = "quedas_pl.csv"
    runs: str = "runs_resgate.csv"
    divergences: str = "divergencias_flow_performance.csv"


# Data Model Dataclasses
@dataclass(frozen=True)
class ReportMetadata:
    """Report metadata section.
    
    Attributes:
        title: Report title string
        generation_date: ISO 8601 formatted datetime string
    """
    title: str
    generation_date: str


@dataclass(frozen=True)
class ExecutiveSummary:
    """Executive summary metrics.
    
    Attributes:
        total_anomalies: Total count of all anomalies
        unique_funds_affected: Count of unique funds with anomalies
    """
    total_anomalies: int
    unique_funds_affected: int


@dataclass(frozen=True)
class DetailedFindings:
    """Detailed anomaly counts by category.
    
    Attributes:
        flow_anomalies_count: Count of flow anomalies detected
        pl_drops_count: Count of PL drop events
        runs_count: Count of redemption run events
        divergences_count: Count of flow/performance divergences
    """
    flow_anomalies_count: int
    pl_drops_count: int
    runs_count: int
    divergences_count: int


@dataclass(frozen=True)
class SeverityDistribution:
    """Severity breakdown of anomalies.
    
    Attributes:
        high: Count of high severity anomalies (z-score > 5)
        medium: Count of medium severity anomalies (3 < z-score <= 5)
        low: Count of low severity anomalies (z-score <= 3)
    """
    high: int
    medium: int
    low: int


@dataclass(frozen=True)
class AnonymizedDatasets:
    """Anonymized dataframes for each anomaly type.
    
    All DataFrames must not contain CNPJ_FUNDO or DENOM_SOCIAL columns.
    Non-empty DataFrames must have FUND_ID column with pattern "FUND_XXXX".
    
    Attributes:
        flow_anomalies: Anonymized flow anomaly records
        pl_drops: Anonymized PL drop records
        runs: Anonymized redemption run records
        divergences: Anonymized divergence records
    """
    flow_anomalies: pd.DataFrame
    pl_drops: pd.DataFrame
    runs: pd.DataFrame
    divergences: pd.DataFrame


@dataclass(frozen=True)
class ReportData:
    """Complete report data structure.
    
    Immutable container for all report content. Single source of truth
    for report data that can be rendered in multiple formats.
    
    Attributes:
        metadata: Report metadata (title, date)
        executive_summary: High-level metrics
        detailed_findings: Category-specific counts
        severity_distribution: Severity breakdown
        datasets: Anonymized dataframes
        methodology_text: Methodology description
        disclaimer_text: Legal disclaimer text
    """
    metadata: ReportMetadata
    executive_summary: ExecutiveSummary
    detailed_findings: DetailedFindings
    severity_distribution: SeverityDistribution
    datasets: AnonymizedDatasets
    methodology_text: str
    disclaimer_text: str


# Renderer Abstract Base Class and Implementations
class ReportRenderer(ABC):
    """Abstract base class for report renderers.
    
    Defines the interface contract for all format-specific renderers.
    Subclasses must implement the render method to transform ReportData
    into their target format (Markdown, HTML, JSON, etc.).
    """
    
    @abstractmethod
    def render(self, data: ReportData) -> str:
        """Render report data to format-specific string.
        
        Args:
            data: Complete report data structure
            
        Returns:
            Formatted report string ready for output
        """
        pass


class MarkdownRenderer(ReportRenderer):
    """Render report data as Markdown."""
    
    def render(self, data: ReportData) -> str:
        """Render report to Markdown format."""
        lines: list[str] = []
        
        # Header section
        lines.append(f"# {data.metadata.title}")
        lines.append("")
        lines.append(f"Generated: {data.metadata.generation_date}")
        lines.append("")
        
        # Executive summary section
        lines.append("## Executive Summary")
        lines.append(f"- Total anomalies: {data.executive_summary.total_anomalies}")
        lines.append(f"- Unique funds affected: {data.executive_summary.unique_funds_affected}")
        lines.append("")
        
        # Detailed findings section
        lines.append("## Detailed Findings")
        lines.append(f"- Flow anomalies: {data.detailed_findings.flow_anomalies_count}")
        lines.append(f"- PL drops: {data.detailed_findings.pl_drops_count}")
        lines.append(f"- Redemption runs: {data.detailed_findings.runs_count}")
        lines.append(f"- Flow/performance divergences: {data.detailed_findings.divergences_count}")
        lines.append("")
        
        # Methodology section
        lines.append("## Methodology")
        lines.append(data.methodology_text)
        lines.append("")
        
        # Disclaimer section
        lines.append("## Disclaimer")
        lines.append(data.disclaimer_text)
        
        return "\n".join(lines) + "\n"


class HtmlRenderer(ReportRenderer):
    """Render report data as HTML."""
    
    def render(self, data: ReportData) -> str:
        """Render report to HTML format."""
        title = data.metadata.title
        total = data.executive_summary.total_anomalies
        funds = data.executive_summary.unique_funds_affected
        
        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; line-height: 1.5; }}
      h1, h2 {{ margin-bottom: 0.5rem; }}
      .muted {{ color: #666; }}
      .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
      .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 1rem; }}
      .metric {{ font-size: 1.5rem; font-weight: 700; }}
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    <p class="muted">Generated: {data.metadata.generation_date}</p>

    <h2>Results Obtained</h2>
    <div class="cards">
      <div class="card"><div class="metric">{total}</div><div>Total anomalies</div></div>
      <div class="card"><div class="metric">{funds}</div><div>Unique funds affected</div></div>
    </div>
    <ul>
      <li>Flow anomalies: {data.detailed_findings.flow_anomalies_count}</li>
      <li>PL drops: {data.detailed_findings.pl_drops_count}</li>
      <li>Redemption runs: {data.detailed_findings.runs_count}</li>
      <li>Flow/performance divergences: {data.detailed_findings.divergences_count}</li>
    </ul>

    <h2>Methods</h2>
    <p>
      {data.methodology_text}
    </p>
  </body>
</html>
"""


class JsonRenderer(ReportRenderer):
    """Render report data as JSON."""
    
    def render(self, data: ReportData) -> str:
        """Render report to JSON format."""
        structure = self._build_json_structure(data)
        return json.dumps(structure, ensure_ascii=False, indent=2)
    
    def _dataframe_to_records(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Convert DataFrame to JSON-serializable records."""
        if df is None or df.empty:
            return []
        return json.loads(df.to_json(orient="records", date_format="iso"))
    
    def _build_json_structure(self, data: ReportData) -> dict[str, Any]:
        """Build nested JSON structure from ReportData."""
        return {
            "metadata": {
                "title": data.metadata.title,
                "generation_date": data.metadata.generation_date,
            },
            "summary": {
                "total_anomalies": data.executive_summary.total_anomalies,
                "unique_funds_affected": data.executive_summary.unique_funds_affected,
                "flow_anomalies_count": data.detailed_findings.flow_anomalies_count,
                "pl_drops_count": data.detailed_findings.pl_drops_count,
                "runs_count": data.detailed_findings.runs_count,
                "divergences_count": data.detailed_findings.divergences_count,
                "severity_distribution": {
                    "high": data.severity_distribution.high,
                    "medium": data.severity_distribution.medium,
                    "low": data.severity_distribution.low,
                },
            },
            "findings": {
                "flow_anomalies": self._dataframe_to_records(data.datasets.flow_anomalies),
                "pl_drops": self._dataframe_to_records(data.datasets.pl_drops),
                "runs": self._dataframe_to_records(data.datasets.runs),
                "divergences": self._dataframe_to_records(data.datasets.divergences),
            },
        }


class PublicReportGenerator:
    """Generate public-facing (anonymized) fraud investigation reports.

    This generator creates anonymized reports for any fund investigation,
    not just REAG-specific cases. The investigation name is configurable
    via config.INVESTIGATION_NAME.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.paths = ReportPaths()

    def load_anomaly_reports(self) -> dict[str, pd.DataFrame]:
        """Load expected anomaly CSVs from `config.REPORTS_DIR`."""
        reports_dir = Path(self.config.REPORTS_DIR)

        def load_csv(filename: str) -> pd.DataFrame:
            path = reports_dir / filename
            if not path.exists():
                LOGGER.warning(f"Missing anomaly CSV file: {path}")
                return pd.DataFrame()
            try:
                return pd.read_csv(path, sep=";")
            except Exception as e:
                LOGGER.error(f"Failed to parse CSV file {path}: {e}")
                return pd.DataFrame()

        return {
            "flow_anomalies": load_csv(self.paths.flow_anomalies),
            "pl_drops": load_csv(self.paths.pl_drops),
            "runs": load_csv(self.paths.runs),
            "divergences": load_csv(self.paths.divergences),
        }

    @staticmethod
    def _collect_cnpj_values(reports: dict[str, pd.DataFrame]) -> list[str]:
        values: list[str] = []
        for df in reports.values():
            if df is None or df.empty or "CNPJ_FUNDO" not in df.columns:
                continue
            series = df["CNPJ_FUNDO"].dropna().astype(str)
            values.extend(series.tolist())
        return values

    @staticmethod
    def _collect_z_scores(reports: dict[str, pd.DataFrame]) -> pd.Series:
        z_values: list[pd.Series] = []
        for df in reports.values():
            if df is None or df.empty:
                continue
            z_cols = [
                col
                for col in df.columns
                if col.upper().startswith("Z_") or "Z_SCORE" in col.upper()
            ]
            for col in z_cols:
                z_values.append(pd.to_numeric(df[col], errors="coerce"))
        if not z_values:
            return pd.Series(dtype="float64")
        return pd.concat(z_values, ignore_index=True).dropna()

    def calculate_summary_statistics(self, reports: dict[str, pd.DataFrame]) -> dict[str, Any]:
        """Build summary stats used by all report formats."""
        flow_count = int(len(reports.get("flow_anomalies", pd.DataFrame())))
        pl_count = int(len(reports.get("pl_drops", pd.DataFrame())))
        runs_count = int(len(reports.get("runs", pd.DataFrame())))
        div_count = int(len(reports.get("divergences", pd.DataFrame())))

        cnpjs = self._collect_cnpj_values(reports)
        unique_funds = len(set(cnpjs))

        z = self._collect_z_scores(reports).abs()
        high = int((z > 5).sum())
        medium = int(((z > 3) & (z <= 5)).sum())
        low = int((z <= 3).sum())

        return {
            "generation_date": datetime.now().isoformat(timespec="seconds"),
            "flow_anomalies_count": flow_count,
            "pl_drops_count": pl_count,
            "runs_count": runs_count,
            "divergences_count": div_count,
            "total_anomalies": flow_count + pl_count + runs_count + div_count,
            "unique_funds_affected": unique_funds,
            "severity_distribution": {"high": high, "medium": medium, "low": low},
        }

    def anonymize_fund_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace `CNPJ_FUNDO` with stable anonymized `FUND_ID` values.
        
        Args:
            df: DataFrame potentially containing CNPJ_FUNDO column
            
        Returns:
            New DataFrame with FUND_ID column, CNPJ_FUNDO removed
        """
        if df is None or df.empty:
            return df.copy()
        if "CNPJ_FUNDO" not in df.columns:
            return df.copy()

        df = df.copy()
        cnpjs = df["CNPJ_FUNDO"].astype(str)
        unique = list(pd.unique(cnpjs))
        mapping = {cnpj: f"FUND_{i + 1:04d}" for i, cnpj in enumerate(unique)}

        df["FUND_ID"] = cnpjs.map(mapping)
        df = df.drop(columns=[c for c in ["CNPJ_FUNDO", "DENOM_SOCIAL"] if c in df.columns])
        return df

    def _build_report_data(
        self,
        summary: dict[str, Any],
        reports: dict[str, pd.DataFrame],
    ) -> ReportData:
        """Build unified ReportData structure from summary statistics and raw reports.
        
        Args:
            summary: Dictionary containing calculated summary statistics
            reports: Dictionary mapping report names to raw DataFrames
            
        Returns:
            Immutable ReportData instance with all sections populated
            
        Raises:
            KeyError: If summary dictionary is missing required keys
        """
        # Validate summary completeness
        required_keys = [
            "generation_date",
            "total_anomalies",
            "unique_funds_affected",
            "flow_anomalies_count",
            "pl_drops_count",
            "runs_count",
            "divergences_count",
            "severity_distribution",
        ]
        
        for key in required_keys:
            if key not in summary:
                raise KeyError(f"Summary statistics missing required key: {key}")
        
        # Validate severity_distribution nested keys
        severity_dist = summary["severity_distribution"]
        for key in ["high", "medium", "low"]:
            if key not in severity_dist:
                raise KeyError(f"Severity distribution missing required key: {key}")
        
        # Extract metadata
        investigation_name = getattr(self.config, 'INVESTIGATION_NAME', 'REAG')
        metadata = ReportMetadata(
            title=f"{investigation_name} Fraud Investigation - Public Report",
            generation_date=summary["generation_date"],
        )
        
        # Build executive summary
        executive_summary = ExecutiveSummary(
            total_anomalies=summary["total_anomalies"],
            unique_funds_affected=summary["unique_funds_affected"],
        )
        
        # Build detailed findings
        detailed_findings = DetailedFindings(
            flow_anomalies_count=summary["flow_anomalies_count"],
            pl_drops_count=summary["pl_drops_count"],
            runs_count=summary["runs_count"],
            divergences_count=summary["divergences_count"],
        )
        
        # Extract severity distribution
        severity = SeverityDistribution(
            high=severity_dist["high"],
            medium=severity_dist["medium"],
            low=severity_dist["low"],
        )
        
        # Anonymize all datasets
        anonymized_datasets = AnonymizedDatasets(
            flow_anomalies=self.anonymize_fund_data(reports["flow_anomalies"]),
            pl_drops=self.anonymize_fund_data(reports["pl_drops"]),
            runs=self.anonymize_fund_data(reports["runs"]),
            divergences=self.anonymize_fund_data(reports["divergences"]),
        )
        
        # Define static text sections
        methodology = (
            "This report aggregates anomaly CSVs generated by the investigation "
            "pipeline and anonymizes fund identifiers before publication."
        )
        
        disclaimer = (
            "This is an automated, anonymized summary intended for transparency "
            "and reproducibility. It does not constitute legal, accounting, or "
            "investment advice."
        )
        
        # Assemble complete structure
        return ReportData(
            metadata=metadata,
            executive_summary=executive_summary,
            detailed_findings=detailed_findings,
            severity_distribution=severity,
            datasets=anonymized_datasets,
            methodology_text=methodology,
            disclaimer_text=disclaimer,
        )

    def _get_renderer(self, output_format: str) -> ReportRenderer:
        """Factory method to get format-specific renderer.
        
        Args:
            output_format: Target format string (markdown, html, json)
            
        Returns:
            Appropriate ReportRenderer instance
            
        Raises:
            ValueError: If output_format is not supported
        """
        normalized = output_format.strip().lower()
        
        if normalized in {"markdown", "md"}:
            return MarkdownRenderer()
        elif normalized in {"html", "htm"}:
            return HtmlRenderer()
        elif normalized in {"json"}:
            return JsonRenderer()
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def generate_report(self, output_format: str, output_file: str | None = None) -> str:
        """Generate a report in the given format and optionally save it.
        
        Args:
            output_format: Target format (markdown, html, json)
            output_file: Optional file path for output
            
        Returns:
            Generated report content as string
            
        Raises:
            ValueError: If output_format is unsupported
            IOError: If file writing fails
        """
        reports = self.load_anomaly_reports()
        summary = self.calculate_summary_statistics(reports)
        
        # Build unified data structure
        report_data = self._build_report_data(summary, reports)
        
        # Get appropriate renderer
        renderer = self._get_renderer(output_format)
        
        # Render to target format
        content = renderer.render(report_data)

        if output_file:
            try:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")
            except (OSError, PermissionError, IOError) as e:
                raise IOError(f"Failed to write report to {output_file}: {e}") from e

        return content


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate REAG public investigation report.")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["markdown", "html", "json"],
        required=True,
        help="Output report format.",
    )
    parser.add_argument(
        "--output",
        dest="output_file",
        default=None,
        help="Optional output file path. If omitted, prints to stdout.",
    )
    args = parser.parse_args()

    generator = PublicReportGenerator()
    content = generator.generate_report(
        output_format=args.output_format,
        output_file=args.output_file,
    )
    if args.output_file is None:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
