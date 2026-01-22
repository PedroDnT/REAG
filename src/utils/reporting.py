"""
Report generation utilities.
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class ReportGenerator:
    """
    Generates formatted reports from analysis results.
    """

    def __init__(self, output_dir: Path = Path('reports')):
        """
        Initialize report generator.

        Args:
            output_dir: Directory for output reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_dataframe(
        self,
        df: pd.DataFrame,
        filename: str,
        format: str = 'csv',
        index: bool = False
    ) -> Path:
        """
        Save DataFrame to file.

        Args:
            df: DataFrame to save
            filename: Output filename
            format: Format ('csv', 'excel', 'json', 'html')
            index: Whether to include index

        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename

        if format == 'csv':
            df.to_csv(output_path, index=index)
        elif format == 'excel':
            df.to_excel(output_path, index=index)
        elif format == 'json':
            df.to_json(output_path, orient='records', indent=2)
        elif format == 'html':
            df.to_html(output_path, index=index)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return output_path

    def create_summary_report(
        self,
        results: Dict[str, pd.DataFrame],
        title: str = "Analysis Summary",
        output_filename: str = "summary_report.txt"
    ) -> Path:
        """
        Create a text summary report from multiple result DataFrames.

        Args:
            results: Dictionary mapping analysis name to results DataFrame
            title: Report title
            output_filename: Output filename

        Returns:
            Path to saved report
        """
        output_path = self.output_dir / output_filename

        with open(output_path, 'w') as f:
            # Header
            f.write("="*70 + "\n")
            f.write(f"{title}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*70 + "\n\n")

            # Results for each analysis
            for analysis_name, df in results.items():
                f.write(f"\n{analysis_name}\n")
                f.write("-"*70 + "\n")
                f.write(f"Total records: {len(df)}\n")

                if not df.empty:
                    # Show summary statistics for numeric columns
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        f.write("\nSummary statistics:\n")
                        f.write(df[numeric_cols].describe().to_string())
                        f.write("\n")

                    # Show value counts for categorical columns
                    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
                    for col in categorical_cols[:3]:  # Limit to first 3
                        if len(df[col].unique()) < 20:  # Only if not too many unique values
                            f.write(f"\n{col} distribution:\n")
                            f.write(df[col].value_counts().to_string())
                            f.write("\n")

                f.write("\n")

            # Footer
            f.write("="*70 + "\n")
            f.write("End of Report\n")
            f.write("="*70 + "\n")

        return output_path

    def create_markdown_report(
        self,
        sections: List[Dict[str, Any]],
        title: str = "Analysis Report",
        output_filename: str = "report.md"
    ) -> Path:
        """
        Create a markdown report.

        Args:
            sections: List of section dictionaries with 'title', 'content', 'data'
            title: Report title
            output_filename: Output filename

        Returns:
            Path to saved report
        """
        output_path = self.output_dir / output_filename

        with open(output_path, 'w') as f:
            # Title
            f.write(f"# {title}\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

            # Sections
            for section in sections:
                f.write(f"## {section['title']}\n\n")

                if 'content' in section:
                    f.write(f"{section['content']}\n\n")

                if 'data' in section and isinstance(section['data'], pd.DataFrame):
                    df = section['data']
                    if not df.empty:
                        f.write(df.to_markdown(index=False))
                        f.write("\n\n")

                if 'metrics' in section:
                    f.write("### Metrics\n\n")
                    for key, value in section['metrics'].items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")

        return output_path

    def create_executive_summary(
        self,
        metrics: Dict[str, Any],
        highlights: List[str],
        recommendations: List[str],
        output_filename: str = "executive_summary.md"
    ) -> Path:
        """
        Create an executive summary report.

        Args:
            metrics: Key metrics dictionary
            highlights: List of key findings
            recommendations: List of recommendations
            output_filename: Output filename

        Returns:
            Path to saved report
        """
        output_path = self.output_dir / output_filename

        with open(output_path, 'w') as f:
            f.write("# Executive Summary\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
            f.write("---\n\n")

            # Key Metrics
            f.write("## Key Metrics\n\n")
            for key, value in metrics.items():
                f.write(f"- **{key}:** {value}\n")
            f.write("\n")

            # Key Findings
            f.write("## Key Findings\n\n")
            for i, finding in enumerate(highlights, 1):
                f.write(f"{i}. {finding}\n")
            f.write("\n")

            # Recommendations
            f.write("## Recommendations\n\n")
            for i, rec in enumerate(recommendations, 1):
                f.write(f"{i}. {rec}\n")
            f.write("\n")

        return output_path
