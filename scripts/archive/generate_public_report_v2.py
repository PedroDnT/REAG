from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

LOGGER = logging.getLogger(__name__)


REPORT_DIR = Path("reports")
PUBLIC_DIR = REPORT_DIR / "public"
PROCESSED_DIR = Path("data") / "processed"


def _ensure_output_dir() -> None:
  PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


def _load_csv(path: Path) -> pd.DataFrame | None:
  if not path.exists():
    LOGGER.warning("Arquivo não encontrado: %s", path)
    return None
  return pd.read_csv(path)


def _pick_column(columns: list[str], candidates: list[str]) -> str | None:
  for candidate in candidates:
    if candidate in columns:
      return candidate
  for column in columns:
    if "CNPJ" in column.upper():
      return column
  return None


def _mask_cnpj(value: str) -> str:
  digits = re.sub(r"\D", "", str(value))
  if len(digits) < 14:
    return str(value)
  return f"{digits[:2]}.{digits[2:5]}.***/****-{digits[-2:]}"


def _plot_top_counts(series: pd.Series, title: str, output_name: str) -> str | None:
  if series.empty:
    return None
  top = series.head(10)
  labels = [_mask_cnpj(label) for label in top.index.astype(str)]
  plt.figure(figsize=(10, 5))
  plt.bar(labels, top.values, color="#2c7fb8")
  plt.title(title)
  plt.xticks(rotation=45, ha="right")
  plt.tight_layout()
  output_path = PUBLIC_DIR / output_name
  plt.savefig(output_path, dpi=150)
  plt.close()
  return output_path.name


def _plot_run_days(run_df: pd.DataFrame) -> str | None:
  if run_df is None or run_df.empty:
    return None
  fund_col = _pick_column(run_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
  if not fund_col:
    return None
  length_col = _pick_column(
    run_df.columns.tolist(),
    [
      "RUN_LENGTH",
      "run_length",
      "RUN_DAYS",
      "run_days",
      "CONSECUTIVE_DAYS",
      "consecutive_days",
    ],
  )
  if length_col:
    totals = run_df.groupby(fund_col)[length_col].sum().sort_values(ascending=False)
  else:
    totals = run_df[fund_col].value_counts()
  return _plot_top_counts(totals, "Дни подряд с оттоками (топ 10)", "runs.png")


def _write_report(lines: list[str]) -> Path:
  report_path = PUBLIC_DIR / "public_report.md"
  report_path.write_text("\n".join(lines), encoding="utf-8")
  return report_path


def generate_public_report() -> Path:
  _ensure_output_dir()

  anomalies_df = _load_csv(REPORT_DIR / "anomalias_fluxo.csv")
  pl_drops_df = _load_csv(REPORT_DIR / "quedas_pl.csv")
  runs_df = _load_csv(REPORT_DIR / "runs_resgate.csv")
  divergences_df = _load_csv(REPORT_DIR / "divergencias_flow_performance.csv")
  summary_df = _load_csv(PROCESSED_DIR / "reag_summary_by_fund.csv")

  lines = [
    "# Публичный отчет о результатах (REAG)",
    "",
    f"Обновлено: {datetime.now():%Y-%m-%d %H:%M}",
    "",
    "Этот отчет обобщает статистические сигналы, выявленные в публичных данных CVM. ",
    "Он предназначен для первичной оценки и сам по себе не является доказательством мошенничества.",
    "",
    "## Обзор доступных данных",
    "",
  ]

  def _availability(label: str, df: pd.DataFrame | None) -> None:
    status = "✅" if df is not None and not df.empty else "⚠️"
    lines.append(f"- {status} {label}")

  _availability("Аномалии потоков", anomalies_df)
  _availability("Резкие падения стоимости активов (PL)", pl_drops_df)
  _availability("Серии оттоков (runs)", runs_df)
  _availability("Расхождения поток/доходность", divergences_df)
  _availability("Сводка по фондам", summary_df)

  lines.extend(
    [
      "",
      "## Ключевые индикаторы",
      "",
      "- **Аномалии потоков**: дни с притоком/оттоком значительно выше исторической нормы фонда.",
      "- **Резкие падения PL**: атипичные изменения стоимости активов; могут указывать на ликвидацию или учетные корректировки.",
      "- **Серии оттоков (runs)**: длительные последовательности чистых оттоков; сигнал стресса ликвидности.",
      "- **Расхождения поток/доходность**: притоки в плохие дни или оттоки в хорошие дни, повод для проверки.",
      "",
    ]
  )

  if summary_df is not None and not summary_df.empty:
    lines.extend(
      [
        "## Количественная сводка",
        "",
        f"- Проанализировано фондов: **{summary_df.shape[0]:,}**",
        "",
      ]
    )

  if anomalies_df is not None and not anomalies_df.empty:
    fund_col = _pick_column(anomalies_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = anomalies_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Аномалии потоков по фондам (топ 10)",
        "anomalias_fluxo.png",
      )
      if image_name:
        lines.extend(["## Аномалии потоков", "", f"![Аномалии](./{image_name})", ""])

  if pl_drops_df is not None and not pl_drops_df.empty:
    fund_col = _pick_column(pl_drops_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = pl_drops_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Резкие падения PL по фондам (топ 10)",
        "quedas_pl.png",
      )
      if image_name:
        lines.extend(["## Резкие падения PL", "", f"![PL](./{image_name})", ""])

  run_image = _plot_run_days(runs_df) if runs_df is not None else None
  if run_image:
    lines.extend(["## Серии оттоков (runs)", "", f"![Runs](./{run_image})", ""])

  if divergences_df is not None and not divergences_df.empty:
    fund_col = _pick_column(divergences_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = divergences_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Расхождения поток/доходность (топ 10)",
        "divergencias.png",
      )
      if image_name:
        lines.extend(["## Расхождения поток/доходность", "", f"![Расхождения](./{image_name})", ""])

  lines.extend(
    [
      "## Как читать этот отчет",
      "",
      "1. **Начните с графиков**: обратите внимание на фонды, которые встречаются чаще всего.",
      "2. **Сверяйтесь с контекстом**: события могут быть связаны с ликвидацией, миграцией пайщиков или корректировками.",
      "3. **Выделяйте критические даты**: используйте CSV-отчеты для детальной проверки событий.",
      "",
      "> Примечание: CNPJ частично замаскированы для публичного использования.",
    ]
  )

  return _write_report(lines)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
  report_path = generate_public_report()
  print(f"Relatório gerado em {report_path}")
