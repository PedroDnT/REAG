from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import Config


@dataclass(frozen=True)
class ReportPaths:
    flow_anomalies: str = "anomalias_fluxo.csv"
    pl_drops: str = "quedas_pl.csv"
    runs: str = "runs_resgate.csv"
    divergences: str = "divergencias_flow_performance.csv"


class PublicReportGenerator:
    """Generate public-facing (anonymized) REAG investigation reports."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.paths = ReportPaths()

    def load_anomaly_reports(self) -> dict[str, pd.DataFrame]:
        """Load expected anomaly CSVs from `config.REPORTS_DIR`."""
        reports_dir = Path(self.config.REPORTS_DIR)

        def load_csv(filename: str) -> pd.DataFrame:
            path = reports_dir / filename
            if not path.exists():
                return pd.DataFrame()
            try:
                return pd.read_csv(path, sep=";")
            except Exception:
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
        """Replace `CNPJ_FUNDO` with stable anonymized `FUND_ID` values."""
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

    @staticmethod
    def _df_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []
        return json.loads(df.to_json(orient="records", date_format="iso"))

    def generate_markdown_report(
        self,
        summary: dict[str, Any],
        reports: dict[str, pd.DataFrame],
    ) -> str:
        """Render a markdown public report string."""
        lines: list[str] = []
        lines.append("# REAG Fraud Investigation - Public Report")
        lines.append("")
        lines.append(f"Generated: {summary.get('generation_date', '')}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(f"- Total anomalies: {summary.get('total_anomalies', 0)}")
        lines.append(f"- Unique funds affected: {summary.get('unique_funds_affected', 0)}")
        lines.append("")
        lines.append("## Detailed Findings")
        lines.append(f"- Flow anomalies: {summary.get('flow_anomalies_count', 0)}")
        lines.append(f"- PL drops: {summary.get('pl_drops_count', 0)}")
        lines.append(f"- Redemption runs: {summary.get('runs_count', 0)}")
        lines.append(f"- Flow/performance divergences: {summary.get('divergences_count', 0)}")
        lines.append("")
        lines.append("## Methodology")
        lines.append(
            "This report aggregates anomaly CSVs generated by the investigation "
            "pipeline and anonymizes fund identifiers before publication."
        )
        lines.append("")
        lines.append("## Disclaimer")
        lines.append(
            "This is an automated, anonymized summary intended for transparency "
            "and reproducibility. It does not constitute legal, accounting, or "
            "investment advice."
        )
        return "\n".join(lines) + "\n"

    def generate_json_report(
        self,
        summary: dict[str, Any],
        reports: dict[str, pd.DataFrame],
    ) -> str:
        """Render a JSON public report string."""
        anonymized = {
            name: self.anonymize_fund_data(df) for name, df in reports.items()
        }
        payload = {
            "metadata": {
                "title": "REAG Fraud Investigation - Public Report",
                "generation_date": summary.get("generation_date"),
            },
            "summary": summary,
            "findings": {
                key: self._df_to_json_records(df) for key, df in anonymized.items()
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def generate_html_report(
        self,
        summary: dict[str, Any],
        reports: dict[str, pd.DataFrame],
    ) -> str:
        """Render an HTML public report string."""
        title = "REAG Fraud Investigation - Public Report"
        total = summary.get("total_anomalies", 0)
        funds = summary.get("unique_funds_affected", 0)

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
    <p class="muted">Generated: {summary.get('generation_date', '')}</p>

    <h2>Executive Summary</h2>
    <div class="cards">
      <div class="card"><div class="metric">{total}</div><div>Total anomalies</div></div>
      <div class="card"><div class="metric">{funds}</div><div>Unique funds affected</div></div>
    </div>

    <h2>Detailed Findings</h2>
    <ul>
      <li>Flow anomalies: {summary.get('flow_anomalies_count', 0)}</li>
      <li>PL drops: {summary.get('pl_drops_count', 0)}</li>
      <li>Redemption runs: {summary.get('runs_count', 0)}</li>
      <li>Flow/performance divergences: {summary.get('divergences_count', 0)}</li>
    </ul>

    <h2>Methodology</h2>
    <p>
      This report aggregates anomaly CSVs generated by the investigation pipeline
      and anonymizes fund identifiers before publication.
    </p>

    <h2>Disclaimer</h2>
    <p>
      This is an automated, anonymized summary intended for transparency and
      reproducibility. It does not constitute legal, accounting, or investment advice.
    </p>
  </body>
</html>
"""

    def generate_report(self, output_format: str, output_file: str | None = None) -> str:
        """Generate a report in the given format and optionally save it."""
        reports = self.load_anomaly_reports()
        summary = self.calculate_summary_statistics(reports)

        normalized_format = output_format.strip().lower()
        if normalized_format in {"markdown", "md"}:
            content = self.generate_markdown_report(summary, reports)
        elif normalized_format in {"html", "htm"}:
            content = self.generate_html_report(summary, reports)
        elif normalized_format in {"json"}:
            content = self.generate_json_report(summary, reports)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")

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

