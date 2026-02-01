from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

LOGGER = logging.getLogger(__name__)

REPORT_DIR = Path("reports")
PUBLIC_DIR = REPORT_DIR / "public"
PROCESSED_DIR = Path("data") / "processed"
SUMMARY_PATH = PROCESSED_DIR / "reag_summary_by_fund.csv"
REPORT_FILES = [
  REPORT_DIR / "anomalias_fluxo.csv",
  REPORT_DIR / "quedas_pl.csv",
  REPORT_DIR / "runs_resgate.csv",
  REPORT_DIR / "divergencias_flow_performance.csv",
]


def _ensure_output_dir() -> None:
  PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


def _load_csv(path: Path) -> pd.DataFrame | None:
  if not path.exists():
    LOGGER.debug("Arquivo não encontrado: %s", path)
    return None
  try:
    return pd.read_csv(path)
  except Exception as exc:  # pragma: no cover - best effort load
    LOGGER.warning("Falha ao ler %s: %s", path, exc)
    return None


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
  return f"{digits[:2]}.{digits[2:5]}.***\/****-{digits[-2:]}"


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
  return _plot_top_counts(totals, "Runs consecutivos (top 10)", "runs.png")


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
  summary_df = _load_csv(SUMMARY_PATH)

  lines = [
    "# Relatório público consolidado (REAG)",
    "",
    f"Atualizado em: {datetime.now():%Y-%m-%d %H:%M}",
    "",
    "Este documento resume sinais detectados nos dados públicos da CVM para os fundos REAG.",
    "Ele serve como ponto de partida e não substitui diligência especializada.",
    "",
    "## Dados prontos para revisão",
    "",
  ]

  def _availability(label: str, df: pd.DataFrame | None) -> None:
    status = "✅" if df is not None and not df.empty else "⚠️"
    lines.append(f"- {status} {label}")

  _availability("Anomalias de fluxo", anomalies_df)
  _availability("Quedas bruscas de PL", pl_drops_df)
  _availability("Runs consecutivos", runs_df)
  _availability("Divergências fluxo x performance", divergences_df)
  _availability("Resumo por fundo", summary_df)

  lines.extend([
    "",
    "## Principais indicadores",
    "",
    "- **Anomalias de fluxo**: movimentos de captação/resgate com Z-score extremo.",
    "- **Quedas de PL**: revisões contábeis ou liquidações que reduzem > 20% do patrimônio.",
    "- **Runs de resgate**: sequência de dias líquidos negativos que pressionam liquidez.",
    "- **Divergências fluxo x performance**: entradas em dias ruins ou saídas em dias bons.",
    "",
  ])

  if summary_df is not None and not summary_df.empty:
    lines.extend([
      "## Resumo quantitativo",
      "",
      f"- Fundos analisados: **{summary_df.shape[0]:,}**",
      "",
    ])

  if anomalies_df is not None and not anomalies_df.empty:
    fund_col = _pick_column(anomalies_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = anomalies_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Anomalias de fluxo por fundo (top 10)",
        "anomalias_fluxo.png",
      )
      if image_name:
        lines.extend(["## Anomalias de fluxo", "", f"![Anomalias](./{image_name})", ""])

  if pl_drops_df is not None and not pl_drops_df.empty:
    fund_col = _pick_column(pl_drops_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = pl_drops_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Quedas de PL por fundo (top 10)",
        "quedas_pl.png",
      )
      if image_name:
        lines.extend(["## Quedas bruscas de PL", "", f"![PL](./{image_name})", ""])

  run_image = _plot_run_days(runs_df) if runs_df is not None else None
  if run_image:
    lines.extend(["## Runs consecutivos", "", f"![Runs](./{run_image})", ""])

  if divergences_df is not None and not divergences_df.empty:
    fund_col = _pick_column(divergences_df.columns.tolist(), ["CNPJ_FUNDO", "cnpj_fundo"])
    if fund_col:
      counts = divergences_df[fund_col].value_counts()
      image_name = _plot_top_counts(
        counts,
        "Divergências fluxo vs performance (top 10)",
        "divergencias.png",
      )
      if image_name:
        lines.extend(["## Divergências fluxo x performance", "", f"![Divergências](./{image_name})", ""])

  lines.extend([
    "## Como interpretar este relatório",
    "",
    "1. Comece pelos gráficos para identificar fundos que aparecem repetidamente.",
    "2. Contextualize ocorrências com datas e eventos externos (liquidação, migração, notícias).",
    "3. Use os CSVs salvos para aprofundar e validar sinais antes de compartilhar.",
    "",
    "> Nota: CNPJ foram parcialmente mascarados para publicação pública.",
  ])

  return _write_report(lines)


def _wait_for_summary(timeout: float, interval: float) -> bool:
  start = time.monotonic()
  LOGGER.info("Aguardando o resumo por fundo (%s)...", SUMMARY_PATH)
  while True:
    if SUMMARY_PATH.exists():
      LOGGER.info("Resumo por fundo disponível: %s", SUMMARY_PATH)
      return True
    if timeout and time.monotonic() - start >= timeout:
      return False
    time.sleep(interval)


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Gera o relatório público consolidado a partir das saídas de análise",
  )
  parser.add_argument(
    "--no-wait",
    action="store_true",
    help="Não aguarda a criação do resumo por fundo (falha se ainda não existir)",
  )
  parser.add_argument(
    "--timeout",
    type=float,
    default=600,
    help="Tempo máximo em segundos para aguardar o resumo por fundo (padrão: 600)",
  )
  parser.add_argument(
    "--interval",
    type=float,
    default=5,
    help="Intervalo em segundos entre tentativas de verificação",
  )
  return parser.parse_args()


def main() -> None:
  args = _parse_args()
  if not args.no_wait:
    if not _wait_for_summary(args.timeout, args.interval):
      LOGGER.error(
        "Timeout aguardando os dados de análise (%s s) e o arquivo %s ainda não existe",
        args.timeout,
        SUMMARY_PATH,
      )
      raise SystemExit(1)
  elif not SUMMARY_PATH.exists():
    LOGGER.error("Resumo por fundo não encontrado em %s. Execute o notebook de análise antes.", SUMMARY_PATH)
    raise SystemExit(1)

  report_path = generate_public_report()
  print(f"Relatório público atualizado em {report_path}")


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
  main()
