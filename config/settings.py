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
    DEFAULT_END_YEAR = 2025
    DEFAULT_END_MONTH = 12  # Ajustar conforme disponibilidade

    # Disponibilidade conhecida de dados
    CDA_START_DATE = (2023, 1)  # CDA disponível a partir de Jan/2023
    INFORME_START_DATE = (2021, 1)  # Informe disponível a partir de Jan/2021

    # Comportamento de download
    DOWNLOAD_CHECK_AVAILABILITY = True  # Verificar antes de baixar
    DOWNLOAD_MAX_RETRIES = 4  # Tentativas com backoff exponencial
    DOWNLOAD_TIMEOUT = 30  # Timeout em segundos

    # =============================================================================
    # Fund Selection Configuration
    # =============================================================================

    # Fund selection mode: "administrator", "manager", "fund_list", "all", "legacy_reag"
    TARGET_FUND_MODE: str = "legacy_reag"

    # Target identifier (administrator name, manager name, or None for 'all'/'fund_list' modes)
    TARGET_IDENTIFIER: str | None = None

    # Explicit list of fund CNPJs (used when TARGET_FUND_MODE = "fund_list")
    TARGET_FUND_CNPJS: list[str] = []

    # Investigation name for reports and outputs (replaces "REAG" in generated content)
    INVESTIGATION_NAME: str = "REAG"

    # Enable peer comparison against other funds
    COMPARISON_MODE: bool = True

    # Peer selection strategy: "same_category", "similar_size", "all_others", "custom"
    PEER_SELECTION_MODE: str = "all_others"

    # Custom peer fund CNPJs (used when PEER_SELECTION_MODE = "custom")
    PEER_FUND_CNPJS: list[str] = []

    # Include target funds in the comparison universe
    INCLUDE_TARGET_IN_UNIVERSE: bool = False

    # Legacy REAG mode - when True, defaults to REAG administrator selection
    LEGACY_REAG_MODE: bool = True

    # REAG administrator search terms (used in legacy mode)
    REAG_SEARCH_TERMS: list[str] = ["REAG", "CBSF", "BANCO MASTER"]
