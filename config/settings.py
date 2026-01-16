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
    ANOMALY_Z_SCORE_THRESHOLD = 3.0
    FLOW_WINDOW_DAYS = 10
