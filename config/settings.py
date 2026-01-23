from pathlib import Path


class Config:
    """Configurações centralizadas do projeto"""

    # URLs base da CVM
    CVM_BASE_URL = "https://dados.cvm.gov.br/dados"
    CVM_INFORME_DIARIO_URL = f"{CVM_BASE_URL}/FI/DOC/INF_DIARIO/DADOS"
    CVM_CDA_URL = f"{CVM_BASE_URL}/FI/DOC/CDA/DADOS"
    CVM_CADASTRO_URL = f"{CVM_BASE_URL}/FI/CAD/DADOS"

    # Diretórios
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    REPORTS_DIR = BASE_DIR / "reports"

    # Configurações de análise
    ANOMALY_Z_SCORE_THRESHOLD = 2.5
    FLOW_WINDOW_DAYS = 10

    # Período de análise padrão (com dados disponíveis)
    DEFAULT_START_YEAR = 2024
    DEFAULT_START_MONTH = 1
    DEFAULT_END_YEAR = 2024
    DEFAULT_END_MONTH = 12  # Ajustar conforme disponibilidade

    # Disponibilidade conhecida de dados
    CDA_START_DATE = (2023, 1)  # CDA disponível a partir de Jan/2023
    INFORME_START_DATE = (2021, 1)  # Informe disponível a partir de Jan/2021

    # Comportamento de download
    DOWNLOAD_CHECK_AVAILABILITY = True  # Verificar antes de baixar
    DOWNLOAD_MAX_RETRIES = 4  # Tentativas com backoff exponencial
    DOWNLOAD_TIMEOUT = 30  # Timeout em segundos

---
name: Financial Investigator
description: Specialized in identifying patterns in financial data that indicate potential fraud, anomalies, and suspicious trading activities in Brazilian investment funds.
model: claude-opus
tools:
  - cvm-collector
  - anomaly-detector
  - data-processor
---

This agent specializes in identifying patterns and anomalies in financial data that indicate potential fraud and suspicious activities. It analyzes fund performance data, cash flow patterns, and market discrepancies to uncover irregularities.

## When to use it
- Detect unusual fund performance patterns
- Identify suspicious cash flows (runs, gate subscriptions)
- Analyze market data discrepancies
- Investigate potential fraud in Brazilian investment funds

## Capabilities
- Analyzes fund data against expected patterns
- Identifies statistical anomalies in performance metrics
- Cross-references fund data with market behavior
- Generates detailed fraud risk reports
