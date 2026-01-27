#!/usr/bin/env python3
"""
Generate Public Report - REAG Fraud Investigation

This script generates a public-facing report from the fraud investigation analysis,
aggregating anomaly detection results and presenting them in a readable format.

The report includes:
- Executive summary of anomalies detected
- Statistics on flow anomalies, PL drops, and runs
- Aggregated findings (anonymized for public disclosure)
- Visualizations and charts

Usage:
    python scripts/generate_public_report.py [--output-format html|markdown|json]
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import json
import argparse

from config.settings import Config


class PublicReportGenerator:
    """Generate public-facing reports from fraud investigation data"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.report_data = {}
        
    def load_anomaly_reports(self) -> Dict[str, pd.DataFrame]:
        """Load all anomaly detection reports from the reports directory"""
        reports = {}
        reports_dir = self.config.REPORTS_DIR
        
        # Expected report files
        report_files = {
            'flow_anomalies': 'anomalias_fluxo.csv',
            'pl_drops': 'quedas_pl.csv',
            'runs': 'runs_resgate.csv',
            'divergences': 'divergencias_flow_performance.csv'
        }
        
        for key, filename in report_files.items():
            filepath = reports_dir / filename
            if filepath.exists():
                try:
                    df = pd.read_csv(filepath, sep=';')
                    reports[key] = df
                    print(f"✅ Loaded {key}: {len(df)} records")
                except Exception as e:
                    print(f"⚠️ Error loading {filename}: {e}")
                    reports[key] = pd.DataFrame()
            else:
                print(f"⚠️ Report file not found: {filename}")
                reports[key] = pd.DataFrame()
        
        return reports
    
    def calculate_summary_statistics(self, reports: Dict[str, pd.DataFrame]) -> Dict:
        """Calculate summary statistics from all reports"""
        summary = {
            'generation_date': datetime.now().isoformat(),
            'total_anomalies': 0,
            'flow_anomalies_count': 0,
            'pl_drops_count': 0,
            'runs_count': 0,
            'divergences_count': 0,
            'unique_funds_affected': 0,
            'severity_distribution': {},
            'temporal_distribution': {}
        }
        
        # Count anomalies by type
        summary['flow_anomalies_count'] = len(reports.get('flow_anomalies', pd.DataFrame()))
        summary['pl_drops_count'] = len(reports.get('pl_drops', pd.DataFrame()))
        summary['runs_count'] = len(reports.get('runs', pd.DataFrame()))
        summary['divergences_count'] = len(reports.get('divergences', pd.DataFrame()))
        
        summary['total_anomalies'] = sum([
            summary['flow_anomalies_count'],
            summary['pl_drops_count'],
            summary['runs_count'],
            summary['divergences_count']
        ])
        
        # Count unique funds affected
        all_funds = set()
        for df in reports.values():
            if not df.empty and 'CNPJ_FUNDO' in df.columns:
                all_funds.update(df['CNPJ_FUNDO'].unique())
        summary['unique_funds_affected'] = len(all_funds)
        
        # Severity distribution (based on Z-scores if available)
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        flow_anomalies = reports.get('flow_anomalies', pd.DataFrame())
        if not flow_anomalies.empty and 'Z_SCORE_FLOW' in flow_anomalies.columns:
            z_scores = flow_anomalies['Z_SCORE_FLOW'].abs()
            severity_counts['high'] = int((z_scores > 5).sum())
            severity_counts['medium'] = int(((z_scores > 3) & (z_scores <= 5)).sum())
            severity_counts['low'] = int((z_scores <= 3).sum())
        summary['severity_distribution'] = severity_counts
        
        return summary
    
    def anonymize_fund_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Anonymize sensitive fund information for public disclosure"""
        if df.empty:
            return df
            
        df = df.copy()
        
        # Replace CNPJ with anonymized IDs
        if 'CNPJ_FUNDO' in df.columns:
            unique_cnpjs = df['CNPJ_FUNDO'].unique()
            cnpj_mapping = {cnpj: f"FUND_{i+1:03d}" for i, cnpj in enumerate(unique_cnpjs)}
            df['FUND_ID'] = df['CNPJ_FUNDO'].map(cnpj_mapping)
            df = df.drop(columns=['CNPJ_FUNDO'])
        
        # Remove or generalize specific fund names if present
        if 'DENOM_SOCIAL' in df.columns:
            df = df.drop(columns=['DENOM_SOCIAL'])
        
        return df
    
    def generate_markdown_report(self, summary: Dict, reports: Dict[str, pd.DataFrame]) -> str:
        """Generate a Markdown formatted public report"""
        lines = []
        
        # Header
        lines.append("# REAG Fraud Investigation - Public Report")
        lines.append("")
        lines.append(f"**Generated:** {summary['generation_date']}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(f"- **Total Anomalies Detected:** {summary['total_anomalies']}")
        lines.append(f"- **Unique Funds Affected:** {summary['unique_funds_affected']}")
        lines.append("")
        
        # Anomaly Breakdown
        lines.append("### Anomaly Breakdown")
        lines.append("")
        lines.append(f"- **Flow Anomalies:** {summary['flow_anomalies_count']}")
        lines.append(f"- **PL Drops (>20%):** {summary['pl_drops_count']}")
        lines.append(f"- **Redemption Runs (5+ days):** {summary['runs_count']}")
        lines.append(f"- **Flow-Performance Divergences:** {summary['divergences_count']}")
        lines.append("")
        
        # Severity Distribution
        if summary['severity_distribution']:
            lines.append("### Severity Distribution")
            lines.append("")
            for level, count in summary['severity_distribution'].items():
                lines.append(f"- **{level.capitalize()}:** {count}")
            lines.append("")
        
        # Detailed Findings
        lines.append("## Detailed Findings")
        lines.append("")
        
        # Flow Anomalies
        flow_anomalies = reports.get('flow_anomalies', pd.DataFrame())
        if not flow_anomalies.empty:
            lines.append("### Flow Anomalies")
            lines.append("")
            lines.append(f"Detected {len(flow_anomalies)} instances of unusual cash flow patterns.")
            lines.append("")
            
            # Top anomalies (anonymized)
            df = self.anonymize_fund_data(flow_anomalies.head(10))
            lines.append("#### Top 10 Anomalies")
            lines.append("")
            lines.append(df.to_markdown(index=False))
            lines.append("")
        
        # PL Drops
        pl_drops = reports.get('pl_drops', pd.DataFrame())
        if not pl_drops.empty:
            lines.append("### Significant PL Drops")
            lines.append("")
            lines.append(f"Detected {len(pl_drops)} instances of portfolio value drops exceeding 20%.")
            lines.append("")
        
        # Runs
        runs = reports.get('runs', pd.DataFrame())
        if not runs.empty:
            lines.append("### Redemption Runs")
            lines.append("")
            lines.append(f"Detected {len(runs)} instances of sustained redemption periods (5+ consecutive days).")
            lines.append("")
        
        # Divergences
        divergences = reports.get('divergences', pd.DataFrame())
        if not divergences.empty:
            lines.append("### Flow-Performance Divergences")
            lines.append("")
            lines.append(f"Detected {len(divergences)} instances where cash flows diverged significantly from fund performance.")
            lines.append("")
        
        # Methodology
        lines.append("## Methodology")
        lines.append("")
        lines.append("This report is based on analysis of publicly available CVM (Brazilian Securities Commission) data.")
        lines.append("")
        lines.append("**Detection Methods:**")
        lines.append("")
        lines.append("1. **Flow Anomalies:** Z-score analysis with threshold > 3.0")
        lines.append("2. **PL Drops:** Daily percentage change < -20%")
        lines.append("3. **Runs:** 5+ consecutive days of net negative redemptions")
        lines.append("4. **Divergences:** Negative correlation between flow and performance Z-scores")
        lines.append("")
        
        # Disclaimer
        lines.append("---")
        lines.append("")
        lines.append("## Disclaimer")
        lines.append("")
        lines.append("This report is for informational and educational purposes only. "
                    "It does not constitute financial, legal, or investment advice. "
                    "All data is derived from publicly available sources.")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_json_report(self, summary: Dict, reports: Dict[str, pd.DataFrame]) -> str:
        """Generate a JSON formatted public report"""
        report = {
            'metadata': {
                'title': 'REAG Fraud Investigation - Public Report',
                'generation_date': summary['generation_date'],
                'version': '1.0'
            },
            'summary': summary,
            'findings': {}
        }
        
        # Add anonymized data for each report type
        for key, df in reports.items():
            if not df.empty:
                anonymized = self.anonymize_fund_data(df)
                # Convert to dict and limit to top 100 records for each type
                report['findings'][key] = anonymized.head(100).to_dict(orient='records')
        
        return json.dumps(report, indent=2, default=str)
    
    def generate_html_report(self, summary: Dict, reports: Dict[str, pd.DataFrame]) -> str:
        """Generate an HTML formatted public report"""
        # Convert markdown to HTML-friendly format
        markdown_content = self.generate_markdown_report(summary, reports)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>REAG Fraud Investigation - Public Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }}
        h3 {{
            color: #7f8c8d;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .summary-box {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .disclaimer {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 5px;
            margin-top: 30px;
        }}
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        ul li {{
            padding: 5px 0;
        }}
        ul li::before {{
            content: "• ";
            color: #3498db;
            font-weight: bold;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>REAG Fraud Investigation - Public Report</h1>
        <p><strong>Generated:</strong> {summary['generation_date']}</p>
        
        <div class="summary-box">
            <h2>Executive Summary</h2>
            <ul>
                <li><strong>Total Anomalies Detected:</strong> {summary['total_anomalies']}</li>
                <li><strong>Unique Funds Affected:</strong> {summary['unique_funds_affected']}</li>
            </ul>
            
            <h3>Anomaly Breakdown</h3>
            <ul>
                <li><strong>Flow Anomalies:</strong> {summary['flow_anomalies_count']}</li>
                <li><strong>PL Drops (>20%):</strong> {summary['pl_drops_count']}</li>
                <li><strong>Redemption Runs (5+ days):</strong> {summary['runs_count']}</li>
                <li><strong>Flow-Performance Divergences:</strong> {summary['divergences_count']}</li>
            </ul>
        </div>
        
        <h2>Detailed Findings</h2>
        """
        
        # Add flow anomalies table if present
        flow_anomalies = reports.get('flow_anomalies', pd.DataFrame())
        if not flow_anomalies.empty:
            df = self.anonymize_fund_data(flow_anomalies.head(10))
            html += f"""
        <h3>Flow Anomalies (Top 10)</h3>
        <p>Detected {len(flow_anomalies)} instances of unusual cash flow patterns.</p>
        {df.to_html(index=False, classes='data-table')}
        """
        
        html += """
        <h2>Methodology</h2>
        <p>This report is based on analysis of publicly available CVM (Brazilian Securities Commission) data.</p>
        
        <h3>Detection Methods:</h3>
        <ul>
            <li><strong>Flow Anomalies:</strong> Z-score analysis with threshold > 3.0</li>
            <li><strong>PL Drops:</strong> Daily percentage change < -20%</li>
            <li><strong>Runs:</strong> 5+ consecutive days of net negative redemptions</li>
            <li><strong>Divergences:</strong> Negative correlation between flow and performance Z-scores</li>
        </ul>
        
        <div class="disclaimer">
            <h2>Disclaimer</h2>
            <p>This report is for informational and educational purposes only. 
            It does not constitute financial, legal, or investment advice. 
            All data is derived from publicly available sources.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def generate_report(self, output_format: str = 'markdown', output_file: Optional[str] = None) -> str:
        """
        Generate a public report in the specified format
        
        Args:
            output_format: 'markdown', 'html', or 'json'
            output_file: Optional path to save the report
            
        Returns:
            The generated report as a string
        """
        print(f"📊 Generating public report in {output_format} format...")
        
        # Load anomaly reports
        reports = self.load_anomaly_reports()
        
        # Calculate summary statistics
        summary = self.calculate_summary_statistics(reports)
        
        # Generate report based on format
        if output_format == 'markdown':
            content = self.generate_markdown_report(summary, reports)
            default_filename = 'public_report.md'
        elif output_format == 'html':
            content = self.generate_html_report(summary, reports)
            default_filename = 'public_report.html'
        elif output_format == 'json':
            content = self.generate_json_report(summary, reports)
            default_filename = 'public_report.json'
        else:
            raise ValueError(f"Unsupported format: {output_format}")
        
        # Save to file if requested
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = self.config.REPORTS_DIR / default_filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Report generated successfully: {output_path}")
        return content


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Generate public-facing report from REAG fraud investigation'
    )
    parser.add_argument(
        '--format',
        choices=['markdown', 'html', 'json'],
        default='markdown',
        help='Output format (default: markdown)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: reports/public_report.<format>)'
    )
    
    args = parser.parse_args()
    
    try:
        generator = PublicReportGenerator()
        generator.generate_report(
            output_format=args.format,
            output_file=args.output
        )
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
