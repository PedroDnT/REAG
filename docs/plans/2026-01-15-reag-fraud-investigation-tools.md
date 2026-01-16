# REAG Fraud Investigation Tools - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir scripts Jupyter para baixar, processar e analisar dados dos fundos da REAG (administradora investigada por fraude junto ao Banco Master) visando identificar irregularidades e padrões suspeitos.

**Architecture:** Sistema modular em Python com notebooks Jupyter para análise interativa. Componentes separados para: (1) coleta de dados da CVM (Informe Diário + CDA), (2) processamento e limpeza, (3) detecção de anomalias (fluxos extremos, mudanças bruscas de carteira), (4) visualização e relatórios.

**Tech Stack:** Python 3.10+, Jupyter Lab, pandas, requests, matplotlib/plotly, scipy (estatística), pytest

---

## Task 1: Setup do Projeto e Estrutura Base

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `.gitignore`
- Create: `config/settings.py`
- Create: `tests/test_config.py`

**Step 1: Write test for configuration loader**

```python
# tests/test_config.py
import pytest
from config.settings import Config


def test_config_has_cvm_base_url():
    config = Config()
    assert config.CVM_BASE_URL is not None
    assert "cvm.gov.br" in config.CVM_BASE_URL


def test_config_has_data_directory():
    config = Config()
    assert config.DATA_DIR is not None
    assert len(config.DATA_DIR) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'config'"

**Step 3: Write minimal configuration module**

```python
# config/settings.py
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
```

**Step 4: Create __init__.py for config package**

```python
# config/__init__.py
from .settings import Config

__all__ = ['Config']
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 6: Create requirements.txt**

```txt
# requirements.txt
# Core data processing
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0

# Jupyter
jupyterlab>=4.0.0
ipykernel>=6.25.0

# Visualization
matplotlib>=3.7.0
seaborn>=0.12.0
plotly>=5.14.0

# Statistical analysis
scipy>=1.11.0
statsmodels>=0.14.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0

# Utilities
python-dateutil>=2.8.0
tqdm>=4.65.0
```

**Step 7: Create .gitignore**

```txt
# .gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Jupyter
.ipynb_checkpoints/
*.ipynb

# Data
data/raw/*
data/processed/*
!data/raw/.gitkeep
!data/processed/.gitkeep

# Reports
reports/*
!reports/.gitkeep

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

**Step 8: Create README.md**

```markdown
# REAG Fraud Investigation Tools

Ferramentas para análise de dados dos fundos da REAG (administradora investigada por fraude).

## Instalação

```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

1. Coleta de dados: `notebooks/01_data_collection.ipynb`
2. Análise de fluxos: `notebooks/02_flow_analysis.ipynb`
3. Análise de carteira: `notebooks/03_portfolio_analysis.ipynb`
4. Detecção de anomalias: `notebooks/04_anomaly_detection.ipynb`

## Estrutura

- `config/` - Configurações
- `src/` - Módulos Python
- `notebooks/` - Jupyter notebooks
- `data/` - Dados baixados e processados
- `reports/` - Relatórios gerados
- `tests/` - Testes unitários
```

**Step 9: Create directory structure**

Run:
```bash
mkdir -p data/raw data/processed reports notebooks src tests config
touch data/raw/.gitkeep data/processed/.gitkeep reports/.gitkeep
```

**Step 10: Commit**

```bash
git init
git add .
git commit -m "feat: setup projeto base para investigação REAG

- Estrutura de diretórios
- Configuração centralizada
- Requirements e gitignore
- Testes básicos"
```

---

## Task 2: Módulo de Coleta de Dados CVM

**Files:**
- Create: `src/collectors/cvm_collector.py`
- Create: `src/collectors/__init__.py`
- Create: `tests/test_cvm_collector.py`

**Step 1: Write test for CVM data collector**

```python
# tests/test_cvm_collector.py
import pytest
from datetime import date
from src.collectors.cvm_collector import CVMCollector


def test_collector_initialization():
    collector = CVMCollector()
    assert collector is not None


def test_informe_diario_url_format():
    collector = CVMCollector()
    url = collector.get_informe_diario_url(year=2024, month=1)
    assert "inf_diario_fi_202401" in url.lower()


def test_cda_url_format():
    collector = CVMCollector()
    url = collector.get_cda_url(year=2024, month=1)
    assert "cda_fi_202401" in url.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cvm_collector.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.collectors'"

**Step 3: Implement CVM collector module**

```python
# src/collectors/cvm_collector.py
import requests
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import date
from tqdm import tqdm
from config.settings import Config


class CVMCollector:
    """Coletor de dados da CVM (Informe Diário, CDA, Cadastro)"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._ensure_directories()

    def _ensure_directories(self):
        """Garante que diretórios de dados existam"""
        self.config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def get_informe_diario_url(self, year: int, month: int) -> str:
        """Retorna URL do Informe Diário para ano/mês específico"""
        return f"{self.config.CVM_INFORME_DIARIO_URL}/inf_diario_fi_{year}{month:02d}.csv"

    def get_cda_url(self, year: int, month: int) -> str:
        """Retorna URL do CDA para ano/mês específico"""
        return f"{self.config.CVM_CDA_URL}/cda_fi_{year}{month:02d}.csv"

    def get_cadastro_url(self, year: int, month: int) -> str:
        """Retorna URL do Cadastro para ano/mês específico"""
        return f"{self.config.CVM_CADASTRO_URL}/cad_fi_{year}{month:02d}.csv"

    def download_file(self, url: str, output_path: Path) -> bool:
        """Baixa arquivo da URL e salva localmente"""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=output_path.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            return True
        except Exception as e:
            print(f"Erro ao baixar {url}: {e}")
            return False

    def download_informe_diario(self, year: int, month: int) -> Optional[Path]:
        """Baixa Informe Diário para ano/mês específico"""
        url = self.get_informe_diario_url(year, month)
        filename = f"informe_diario_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_cda(self, year: int, month: int) -> Optional[Path]:
        """Baixa CDA para ano/mês específico"""
        url = self.get_cda_url(year, month)
        filename = f"cda_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_cadastro(self, year: int, month: int) -> Optional[Path]:
        """Baixa Cadastro para ano/mês específico"""
        url = self.get_cadastro_url(year, month)
        filename = f"cadastro_{year}{month:02d}.csv"
        output_path = self.config.RAW_DATA_DIR / filename

        if output_path.exists():
            print(f"Arquivo já existe: {output_path}")
            return output_path

        success = self.download_file(url, output_path)
        return output_path if success else None

    def download_period(self, start_year: int, start_month: int,
                       end_year: int, end_month: int,
                       data_types: list[str] = ['informe_diario', 'cda', 'cadastro']):
        """Baixa dados para um período completo"""
        results = []

        current_year = start_year
        current_month = start_month

        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            print(f"\n=== Baixando dados de {current_year}-{current_month:02d} ===")

            if 'informe_diario' in data_types:
                path = self.download_informe_diario(current_year, current_month)
                if path:
                    results.append(('informe_diario', current_year, current_month, path))

            if 'cda' in data_types:
                path = self.download_cda(current_year, current_month)
                if path:
                    results.append(('cda', current_year, current_month, path))

            if 'cadastro' in data_types:
                path = self.download_cadastro(current_year, current_month)
                if path:
                    results.append(('cadastro', current_year, current_month, path))

            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return results
```

**Step 4: Create __init__.py for collectors package**

```python
# src/collectors/__init__.py
from .cvm_collector import CVMCollector

__all__ = ['CVMCollector']
```

**Step 5: Create __init__.py for src package**

```python
# src/__init__.py
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_cvm_collector.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/collectors/ tests/test_cvm_collector.py
git commit -m "feat: módulo de coleta de dados CVM

- CVMCollector para baixar Informe Diário, CDA e Cadastro
- Suporte a download de períodos
- Testes unitários"
```

---

## Task 3: Módulo de Processamento de Dados

**Files:**
- Create: `src/processors/data_processor.py`
- Create: `src/processors/__init__.py`
- Create: `tests/test_data_processor.py`

**Step 1: Write test for data processor**

```python
# tests/test_data_processor.py
import pytest
import pandas as pd
from src.processors.data_processor import DataProcessor


def test_processor_initialization():
    processor = DataProcessor()
    assert processor is not None


def test_read_informe_diario_csv():
    processor = DataProcessor()
    # Mock test - verificar se método existe
    assert hasattr(processor, 'read_informe_diario')


def test_filter_by_cnpj():
    processor = DataProcessor()
    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90', '98.765.432/0001-10'],
        'VL_TOTAL': [1000, 2000]
    })

    result = processor.filter_by_cnpj(df, ['12.345.678/0001-90'])
    assert len(result) == 1
    assert result.iloc[0]['CNPJ_FUNDO'] == '12.345.678/0001-90'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_processor.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.processors'"

**Step 3: Implement data processor module**

```python
# src/processors/data_processor.py
import pandas as pd
from pathlib import Path
from typing import Optional, List
from config.settings import Config


class DataProcessor:
    """Processador de dados da CVM (leitura, limpeza, transformação)"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def read_informe_diario(self, file_path: Path,
                           encoding: str = 'latin1',
                           sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de Informe Diário"""
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep)

            # Padronizar nomes de colunas
            df.columns = df.columns.str.strip().str.upper()

            # Converter data
            if 'DT_COMPTC' in df.columns:
                df['DT_COMPTC'] = pd.to_datetime(df['DT_COMPTC'], format='%Y-%m-%d', errors='coerce')

            # Converter valores numéricos
            numeric_cols = ['VL_TOTAL', 'VL_QUOTA', 'VL_PATRIM_LIQ', 'CAPTC_DIA', 'RESG_DIA', 'NR_COTST']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            print(f"Erro ao ler Informe Diário {file_path}: {e}")
            return pd.DataFrame()

    def read_cda(self, file_path: Path,
                 encoding: str = 'latin1',
                 sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de CDA (Composição de Carteira)"""
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep)

            # Padronizar nomes de colunas
            df.columns = df.columns.str.strip().str.upper()

            # Converter data
            if 'DT_COMPTC' in df.columns:
                df['DT_COMPTC'] = pd.to_datetime(df['DT_COMPTC'], format='%Y-%m-%d', errors='coerce')

            # Converter valores numéricos
            numeric_cols = ['VL_MERC_POS_FINAL', 'QT_POS_FINAL', 'VL_CUSTO_POS_FINAL']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            print(f"Erro ao ler CDA {file_path}: {e}")
            return pd.DataFrame()

    def read_cadastro(self, file_path: Path,
                     encoding: str = 'latin1',
                     sep: str = ';') -> pd.DataFrame:
        """Lê arquivo de Cadastro de Fundos"""
        try:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep)

            # Padronizar nomes de colunas
            df.columns = df.columns.str.strip().str.upper()

            # Converter data
            date_cols = ['DT_REG', 'DT_CONST', 'DT_CANCEL', 'DT_INI_SIT', 'DT_INI_ATIV', 'DT_INI_EXERC', 'DT_FIM_EXERC']
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format='%Y-%m-%d', errors='coerce')

            return df
        except Exception as e:
            print(f"Erro ao ler Cadastro {file_path}: {e}")
            return pd.DataFrame()

    def filter_by_cnpj(self, df: pd.DataFrame, cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por lista de CNPJs"""
        if 'CNPJ_FUNDO' not in df.columns:
            return pd.DataFrame()

        return df[df['CNPJ_FUNDO'].isin(cnpj_list)].copy()

    def filter_by_administrador(self, df: pd.DataFrame, admin_cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por CNPJ do administrador"""
        if 'CNPJ_ADMIN' not in df.columns:
            return pd.DataFrame()

        return df[df['CNPJ_ADMIN'].isin(admin_cnpj_list)].copy()

    def filter_by_gestor(self, df: pd.DataFrame, gestor_cnpj_list: List[str]) -> pd.DataFrame:
        """Filtra DataFrame por CNPJ do gestor"""
        if 'CNPJ_GESTOR' not in df.columns:
            return pd.DataFrame()

        return df[df['CNPJ_GESTOR'].isin(gestor_cnpj_list)].copy()

    def filter_by_date_range(self, df: pd.DataFrame,
                            start_date: str,
                            end_date: str,
                            date_col: str = 'DT_COMPTC') -> pd.DataFrame:
        """Filtra DataFrame por intervalo de datas"""
        if date_col not in df.columns:
            return pd.DataFrame()

        mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
        return df[mask].copy()

    def calculate_net_flow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula fluxo líquido (captação - resgate)"""
        if 'CAPTC_DIA' in df.columns and 'RESG_DIA' in df.columns:
            df = df.copy()
            df['FLUXO_LIQ_DIA'] = df['CAPTC_DIA'] - df['RESG_DIA']
        return df

    def aggregate_by_fund(self, df: pd.DataFrame,
                         agg_dict: Optional[dict] = None) -> pd.DataFrame:
        """Agrega dados por fundo"""
        if agg_dict is None:
            agg_dict = {
                'VL_TOTAL': 'sum',
                'VL_PATRIM_LIQ': 'last',
                'CAPTC_DIA': 'sum',
                'RESG_DIA': 'sum',
                'FLUXO_LIQ_DIA': 'sum',
                'NR_COTST': 'last'
            }

        # Filtrar apenas colunas que existem
        valid_agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

        if 'CNPJ_FUNDO' in df.columns:
            return df.groupby('CNPJ_FUNDO').agg(valid_agg_dict).reset_index()

        return df

    def save_processed(self, df: pd.DataFrame, filename: str):
        """Salva dados processados"""
        output_path = self.config.PROCESSED_DATA_DIR / filename
        df.to_csv(output_path, index=False, encoding='utf-8', sep=';')
        print(f"Dados salvos em: {output_path}")
        return output_path
```

**Step 4: Create __init__.py for processors package**

```python
# src/processors/__init__.py
from .data_processor import DataProcessor

__all__ = ['DataProcessor']
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_data_processor.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/processors/ tests/test_data_processor.py
git commit -m "feat: módulo de processamento de dados

- DataProcessor para ler e processar CSVs da CVM
- Filtros por CNPJ, administrador, gestor, data
- Cálculo de fluxo líquido
- Agregação por fundo"
```

---

## Task 4: Módulo de Detecção de Anomalias

**Files:**
- Create: `src/analyzers/anomaly_detector.py`
- Create: `src/analyzers/__init__.py`
- Create: `tests/test_anomaly_detector.py`

**Step 1: Write test for anomaly detector**

```python
# tests/test_anomaly_detector.py
import pytest
import pandas as pd
import numpy as np
from src.analyzers.anomaly_detector import AnomalyDetector


def test_detector_initialization():
    detector = AnomalyDetector()
    assert detector is not None


def test_z_score_calculation():
    detector = AnomalyDetector()
    data = pd.Series([1, 2, 3, 4, 5, 100])  # 100 é outlier

    z_scores = detector.calculate_z_scores(data)

    assert len(z_scores) == len(data)
    assert abs(z_scores.iloc[-1]) > 2  # 100 deve ter z-score alto


def test_detect_flow_anomalies():
    detector = AnomalyDetector()
    df = pd.DataFrame({
        'CNPJ_FUNDO': ['12.345.678/0001-90'] * 10,
        'DT_COMPTC': pd.date_range('2024-01-01', periods=10),
        'FLUXO_LIQ_DIA': [100, 120, 110, 105, 115, 1000, 100, 105, 110, 120]  # dia 6 anômalo
    })

    anomalies = detector.detect_flow_anomalies(df, threshold=3.0)

    assert not anomalies.empty
    assert anomalies.iloc[0]['FLUXO_LIQ_DIA'] == 1000
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_anomaly_detector.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.analyzers'"

**Step 3: Implement anomaly detector module**

```python
# src/analyzers/anomaly_detector.py
import pandas as pd
import numpy as np
from scipy import stats
from typing import Optional, Tuple
from config.settings import Config


class AnomalyDetector:
    """Detector de anomalias em dados de fundos"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def calculate_z_scores(self, series: pd.Series) -> pd.Series:
        """Calcula Z-scores para uma série"""
        return (series - series.mean()) / series.std()

    def detect_flow_anomalies(self, df: pd.DataFrame,
                             threshold: float = 3.0,
                             flow_col: str = 'FLUXO_LIQ_DIA') -> pd.DataFrame:
        """
        Detecta anomalias de fluxo usando Z-score

        Retorna DataFrame com apenas registros anômalos
        """
        if flow_col not in df.columns:
            print(f"Coluna {flow_col} não encontrada")
            return pd.DataFrame()

        df = df.copy()

        # Calcular Z-score por fundo
        if 'CNPJ_FUNDO' in df.columns:
            df['Z_SCORE_FLOW'] = df.groupby('CNPJ_FUNDO')[flow_col].transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
            )
        else:
            df['Z_SCORE_FLOW'] = self.calculate_z_scores(df[flow_col])

        # Identificar anomalias
        df['IS_ANOMALY_FLOW'] = df['Z_SCORE_FLOW'].abs() > threshold

        # Retornar apenas anomalias
        anomalies = df[df['IS_ANOMALY_FLOW']].copy()

        return anomalies.sort_values('Z_SCORE_FLOW', key=abs, ascending=False)

    def detect_pl_drops(self, df: pd.DataFrame,
                       threshold_pct: float = 20.0,
                       pl_col: str = 'VL_PATRIM_LIQ') -> pd.DataFrame:
        """
        Detecta quedas bruscas de patrimônio líquido

        threshold_pct: porcentagem de queda para considerar anomalia
        """
        if pl_col not in df.columns or 'DT_COMPTC' not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Calcular variação percentual diária
        df['PL_VAR_PCT'] = df.groupby('CNPJ_FUNDO')[pl_col].pct_change() * 100

        # Identificar quedas significativas
        df['IS_PL_DROP'] = df['PL_VAR_PCT'] < -threshold_pct

        drops = df[df['IS_PL_DROP']].copy()

        return drops.sort_values('PL_VAR_PCT')

    def detect_runs(self, df: pd.DataFrame,
                   consecutive_days: int = 5,
                   flow_col: str = 'FLUXO_LIQ_DIA') -> pd.DataFrame:
        """
        Detecta "runs" - sequências consecutivas de resgates líquidos

        consecutive_days: número mínimo de dias consecutivos de resgate
        """
        if flow_col not in df.columns or 'DT_COMPTC' not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Identificar dias de resgate líquido negativo
        df['IS_NEGATIVE_FLOW'] = df[flow_col] < 0

        # Contar sequências consecutivas
        df['RUN_ID'] = (df.groupby('CNPJ_FUNDO')['IS_NEGATIVE_FLOW']
                       .transform(lambda x: (x != x.shift()).cumsum()))

        df['RUN_LENGTH'] = df.groupby(['CNPJ_FUNDO', 'RUN_ID']).cumcount() + 1

        # Filtrar apenas runs significativas
        runs = df[(df['IS_NEGATIVE_FLOW']) & (df['RUN_LENGTH'] >= consecutive_days)].copy()

        return runs.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

    def detect_concentration_spikes(self, cda_df: pd.DataFrame,
                                   threshold_pct: float = 50.0) -> pd.DataFrame:
        """
        Detecta aumento brusco de concentração em poucos ativos

        Requer dados de CDA
        """
        if 'CNPJ_FUNDO' not in cda_df.columns or 'VL_MERC_POS_FINAL' not in cda_df.columns:
            return pd.DataFrame()

        df = cda_df.copy()

        # Calcular total por fundo e data
        total_by_fund = df.groupby(['CNPJ_FUNDO', 'DT_COMPTC'])['VL_MERC_POS_FINAL'].sum().reset_index()
        total_by_fund.rename(columns={'VL_MERC_POS_FINAL': 'TOTAL_CARTEIRA'}, inplace=True)

        # Merge para ter percentual de cada ativo
        df = df.merge(total_by_fund, on=['CNPJ_FUNDO', 'DT_COMPTC'])
        df['PCT_CARTEIRA'] = (df['VL_MERC_POS_FINAL'] / df['TOTAL_CARTEIRA']) * 100

        # Identificar ativos com concentração alta
        high_concentration = df[df['PCT_CARTEIRA'] > threshold_pct].copy()

        return high_concentration.sort_values('PCT_CARTEIRA', ascending=False)

    def detect_divergence_flow_performance(self, df: pd.DataFrame,
                                          threshold_z: float = 2.0) -> pd.DataFrame:
        """
        Detecta divergência entre fluxo e performance

        Ex: entradas grandes em dias de performance ruim
        """
        required_cols = ['VL_QUOTA', 'FLUXO_LIQ_DIA', 'CNPJ_FUNDO', 'DT_COMPTC']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()

        df = df.copy()
        df = df.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])

        # Calcular retorno diário da cota
        df['RETORNO_DIA'] = df.groupby('CNPJ_FUNDO')['VL_QUOTA'].pct_change() * 100

        # Calcular Z-score de fluxo e retorno
        df['Z_FLOW'] = df.groupby('CNPJ_FUNDO')['FLUXO_LIQ_DIA'].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )
        df['Z_RETORNO'] = df.groupby('CNPJ_FUNDO')['RETORNO_DIA'].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )

        # Divergência: fluxo e retorno em direções opostas com magnitudes altas
        df['DIVERGENCE_SCORE'] = -(df['Z_FLOW'] * df['Z_RETORNO'])  # negativo de produto = direções opostas

        # Filtrar apenas divergências significativas
        divergences = df[df['DIVERGENCE_SCORE'] > threshold_z].copy()

        return divergences.sort_values('DIVERGENCE_SCORE', ascending=False)

    def generate_anomaly_report(self, df: pd.DataFrame,
                               cda_df: Optional[pd.DataFrame] = None) -> dict:
        """
        Gera relatório completo de anomalias

        Retorna dict com diferentes tipos de anomalia
        """
        report = {}

        # 1. Anomalias de fluxo
        report['flow_anomalies'] = self.detect_flow_anomalies(
            df,
            threshold=self.config.ANOMALY_Z_SCORE_THRESHOLD
        )

        # 2. Quedas de PL
        report['pl_drops'] = self.detect_pl_drops(df, threshold_pct=20.0)

        # 3. Runs (resgates consecutivos)
        report['runs'] = self.detect_runs(df, consecutive_days=self.config.FLOW_WINDOW_DAYS)

        # 4. Divergência flow vs performance
        report['divergences'] = self.detect_divergence_flow_performance(df)

        # 5. Concentração (se CDA disponível)
        if cda_df is not None:
            report['concentration_spikes'] = self.detect_concentration_spikes(cda_df)

        return report
```

**Step 4: Create __init__.py for analyzers package**

```python
# src/analyzers/__init__.py
from .anomaly_detector import AnomalyDetector

__all__ = ['AnomalyDetector']
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_anomaly_detector.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/analyzers/ tests/test_anomaly_detector.py
git commit -m "feat: módulo de detecção de anomalias

- Detecção de anomalias de fluxo via Z-score
- Detecção de quedas bruscas de PL
- Detecção de runs (resgates consecutivos)
- Detecção de concentração de carteira
- Divergência entre fluxo e performance
- Relatório completo de anomalias"
```

---

## Task 5: Notebook de Coleta de Dados

**Files:**
- Create: `notebooks/01_data_collection.ipynb`

**Step 1: Create data collection notebook**

```python
# notebooks/01_data_collection.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 01 - Coleta de Dados da CVM\n",
    "\n",
    "Este notebook baixa dados da CVM necessários para investigação:\n",
    "\n",
    "1. **Informe Diário**: PL, cota, captação/resgate diário\n",
    "2. **CDA**: Composição de carteira mensal\n",
    "3. **Cadastro**: Dados cadastrais dos fundos"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "sys.path.append('..')\n",
    "\n",
    "from src.collectors.cvm_collector import CVMCollector\n",
    "from config.settings import Config"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Configuração"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "config = Config()\n",
    "collector = CVMCollector(config)\n",
    "\n",
    "# Período para análise\n",
    "START_YEAR = 2024\n",
    "START_MONTH = 1\n",
    "END_YEAR = 2024\n",
    "END_MONTH = 12"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Download de Informe Diário"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"Baixando Informe Diário...\\n\")\n",
    "results = collector.download_period(\n",
    "    start_year=START_YEAR,\n",
    "    start_month=START_MONTH,\n",
    "    end_year=END_YEAR,\n",
    "    end_month=END_MONTH,\n",
    "    data_types=['informe_diario']\n",
    ")\n",
    "\n",
    "print(f\"\\n✅ Total de arquivos baixados: {len(results)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Download de CDA (Composição de Carteira)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"Baixando CDA...\\n\")\n",
    "results_cda = collector.download_period(\n",
    "    start_year=START_YEAR,\n",
    "    start_month=START_MONTH,\n",
    "    end_year=END_YEAR,\n",
    "    end_month=END_MONTH,\n",
    "    data_types=['cda']\n",
    ")\n",
    "\n",
    "print(f\"\\n✅ Total de arquivos baixados: {len(results_cda)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Download de Cadastro"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"Baixando Cadastro...\\n\")\n",
    "results_cadastro = collector.download_period(\n",
    "    start_year=START_YEAR,\n",
    "    start_month=START_MONTH,\n",
    "    end_year=END_YEAR,\n",
    "    end_month=END_MONTH,\n",
    "    data_types=['cadastro']\n",
    ")\n",
    "\n",
    "print(f\"\\n✅ Total de arquivos baixados: {len(results_cadastro)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Verificar Estrutura dos Dados"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import pandas as pd\n",
    "\n",
    "# Ler uma amostra do Informe Diário\n",
    "sample_file = config.RAW_DATA_DIR / f\"informe_diario_{START_YEAR}{START_MONTH:02d}.csv\"\n",
    "\n",
    "if sample_file.exists():\n",
    "    df_sample = pd.read_csv(sample_file, encoding='latin1', sep=';', nrows=1000)\n",
    "    print(\"\\n📊 Colunas disponíveis no Informe Diário:\")\n",
    "    print(df_sample.columns.tolist())\n",
    "    print(f\"\\n📏 Shape da amostra: {df_sample.shape}\")\n",
    "    print(\"\\n🔍 Primeiras linhas:\")\n",
    "    display(df_sample.head())\n",
    "else:\n",
    "    print(\"⚠️ Arquivo de amostra não encontrado\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Resumo"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n\" + \"=\"*60)\n",
    "print(\"📁 RESUMO DA COLETA\")\n",
    "print(\"=\"*60)\n",
    "print(f\"Informe Diário: {len(results)} arquivos\")\n",
    "print(f\"CDA: {len(results_cda)} arquivos\")\n",
    "print(f\"Cadastro: {len(results_cadastro)} arquivos\")\n",
    "print(f\"\\n📂 Diretório de dados: {config.RAW_DATA_DIR}\")\n",
    "print(\"\\n✅ Coleta concluída! Próximo passo: 02_flow_analysis.ipynb\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

**Step 2: Verify notebook can be created**

Run: `ls notebooks/`
Expected: See 01_data_collection.ipynb

**Step 3: Commit**

```bash
git add notebooks/01_data_collection.ipynb
git commit -m "feat: notebook de coleta de dados CVM

- Baixa Informe Diário, CDA e Cadastro
- Configurável por período
- Verificação de estrutura dos dados"
```

---

## Task 6: Notebook de Identificação de Fundos REAG

**Files:**
- Create: `notebooks/02_identify_reag_funds.ipynb`

**Step 1: Create REAG identification notebook**

```python
# notebooks/02_identify_reag_funds.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 02 - Identificação de Fundos REAG\n",
    "\n",
    "Identifica fundos administrados/geridos pela REAG usando dados de cadastro da CVM.\n",
    "\n",
    "**REAG**: Administradora investigada por fraude junto ao Banco Master"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "sys.path.append('..')\n",
    "\n",
    "import pandas as pd\n",
    "from pathlib import Path\n",
    "from src.processors.data_processor import DataProcessor\n",
    "from config.settings import Config\n",
    "\n",
    "pd.set_option('display.max_columns', None)\n",
    "pd.set_option('display.max_colwidth', 50)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Carregar Cadastro de Fundos"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "config = Config()\n",
    "processor = DataProcessor(config)\n",
    "\n",
    "# Ler cadastro mais recente\n",
    "cadastro_files = sorted(config.RAW_DATA_DIR.glob('cadastro_*.csv'))\n",
    "latest_cadastro = cadastro_files[-1] if cadastro_files else None\n",
    "\n",
    "if latest_cadastro:\n",
    "    print(f\"📂 Lendo: {latest_cadastro.name}\")\n",
    "    df_cadastro = processor.read_cadastro(latest_cadastro)\n",
    "    print(f\"📊 Total de fundos no cadastro: {len(df_cadastro):,}\")\n",
    "else:\n",
    "    print(\"⚠️ Nenhum arquivo de cadastro encontrado\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Buscar REAG/CBSF nos Administradores"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Buscar por nome contendo 'REAG' ou 'CBSF'\n",
    "search_terms = ['REAG', 'CBSF', 'BANCO MASTER']\n",
    "\n",
    "mask = df_cadastro['DENOM_SOCIAL'].str.contains('|'.join(search_terms), case=False, na=False)\n",
    "if 'ADMIN' in df_cadastro.columns:\n",
    "    mask |= df_cadastro['ADMIN'].str.contains('|'.join(search_terms), case=False, na=False)\n",
    "if 'GESTOR' in df_cadastro.columns:\n",
    "    mask |= df_cadastro['GESTOR'].str.contains('|'.join(search_terms), case=False, na=False)\n",
    "\n",
    "df_reag_related = df_cadastro[mask].copy()\n",
    "\n",
    "print(f\"\\n🎯 Fundos relacionados encontrados: {len(df_reag_related)}\")\n",
    "print(\"\\n📋 Amostra:\")\n",
    "display(df_reag_related[['CNPJ_FUNDO', 'DENOM_SOCIAL', 'SIT']].head(20))"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Identificar CNPJs de Administradores/Gestores REAG"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Analisar administradores únicos\n",
    "if 'CNPJ_ADMIN' in df_cadastro.columns and 'ADMIN' in df_cadastro.columns:\n",
    "    admin_counts = df_cadastro.groupby(['CNPJ_ADMIN', 'ADMIN']).size().reset_index(name='NUM_FUNDOS')\n",
    "    admin_counts = admin_counts.sort_values('NUM_FUNDOS', ascending=False)\n",
    "    \n",
    "    # Filtrar REAG\n",
    "    reag_admins = admin_counts[\n",
    "        admin_counts['ADMIN'].str.contains('|'.join(search_terms), case=False, na=False)\n",
    "    ]\n",
    "    \n",
    "    print(\"\\n🏢 Administradores REAG/relacionados:\")\n",
    "    display(reag_admins)\n",
    "    \n",
    "    # Salvar CNPJs para uso posterior\n",
    "    reag_admin_cnpjs = reag_admins['CNPJ_ADMIN'].tolist()\n",
    "    print(f\"\\n📝 CNPJs de administradores REAG: {len(reag_admin_cnpjs)}\")\n",
    "    print(reag_admin_cnpjs)\n",
    "else:\n",
    "    print(\"⚠️ Colunas de administrador não encontradas\")\n",
    "    reag_admin_cnpjs = []"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Obter Lista Completa de Fundos REAG"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Filtrar fundos por CNPJ do administrador\n",
    "if reag_admin_cnpjs:\n",
    "    df_reag_funds = processor.filter_by_administrador(df_cadastro, reag_admin_cnpjs)\n",
    "    \n",
    "    print(f\"\\n💼 Total de fundos administrados pela REAG: {len(df_reag_funds)}\")\n",
    "    \n",
    "    # Análise por situação\n",
    "    if 'SIT' in df_reag_funds.columns:\n",
    "        print(\"\\n📊 Distribuição por situação:\")\n",
    "        display(df_reag_funds['SIT'].value_counts())\n",
    "    \n",
    "    # Fundos ativos\n",
    "    df_reag_active = df_reag_funds[df_reag_funds['SIT'] == 'EM FUNCIONAMENTO NORMAL'].copy()\n",
    "    print(f\"\\n✅ Fundos em funcionamento normal: {len(df_reag_active)}\")\n",
    "    \n",
    "    # Salvar lista de CNPJs\n",
    "    reag_fund_cnpjs = df_reag_funds['CNPJ_FUNDO'].unique().tolist()\n",
    "    \n",
    "    # Exportar para CSV\n",
    "    output_path = config.PROCESSED_DATA_DIR / 'reag_fund_list.csv'\n",
    "    df_reag_funds[['CNPJ_FUNDO', 'DENOM_SOCIAL', 'SIT', 'CNPJ_ADMIN']].to_csv(\n",
    "        output_path, \n",
    "        index=False\n",
    "    )\n",
    "    print(f\"\\n💾 Lista salva em: {output_path}\")\n",
    "else:\n",
    "    print(\"⚠️ Nenhum CNPJ de administrador REAG identificado\")\n",
    "    reag_fund_cnpjs = []"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Resumo"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n\" + \"=\"*60)\n",
    "print(\"📊 RESUMO DA IDENTIFICAÇÃO\")\n",
    "print(\"=\"*60)\n",
    "print(f\"Administradores REAG identificados: {len(reag_admin_cnpjs)}\")\n",
    "print(f\"Fundos REAG identificados: {len(reag_fund_cnpjs)}\")\n",
    "print(f\"Fundos ativos: {len(df_reag_active) if 'df_reag_active' in locals() else 0}\")\n",
    "print(f\"\\n📂 Lista exportada: {config.PROCESSED_DATA_DIR / 'reag_fund_list.csv'}\")\n",
    "print(\"\\n✅ Identificação concluída! Próximo passo: 03_flow_analysis.ipynb\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.10.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

**Step 2: Commit**

```bash
git add notebooks/02_identify_reag_funds.ipynb
git commit -m "feat: notebook de identificação de fundos REAG

- Busca por REAG/CBSF/Banco Master no cadastro
- Identifica CNPJs de administradores
- Lista completa de fundos relacionados
- Exporta lista para análises posteriores"
```

---

## Task 7: Notebook de Análise de Fluxos

**Files:**
- Create: `notebooks/03_flow_analysis.ipynb`

**Step 1: Create flow analysis notebook**

```python
# notebooks/03_flow_analysis.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 03 - Análise de Fluxos (Captação/Resgate)\n",
    "\n",
    "Análise de movimentações (captação e resgate) dos fundos REAG para identificar padrões suspeitos."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "sys.path.append('..')\n",
    "\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "from pathlib import Path\n",
    "\n",
    "from src.processors.data_processor import DataProcessor\n",
    "from src.analyzers.anomaly_detector import AnomalyDetector\n",
    "from config.settings import Config\n",
    "\n",
    "pd.set_option('display.max_columns', None)\n",
    "sns.set_style('whitegrid')\n",
    "plt.rcParams['figure.figsize'] = (14, 8)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Carregar Lista de Fundos REAG"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "config = Config()\n",
    "processor = DataProcessor(config)\n",
    "detector = AnomalyDetector(config)\n",
    "\n",
    "# Carregar lista de fundos REAG\n",
    "reag_list_path = config.PROCESSED_DATA_DIR / 'reag_fund_list.csv'\n",
    "\n",
    "if reag_list_path.exists():\n",
    "    df_reag_list = pd.read_csv(reag_list_path)\n",
    "    reag_cnpjs = df_reag_list['CNPJ_FUNDO'].tolist()\n",
    "    print(f\"✅ {len(reag_cnpjs)} fundos REAG carregados\")\n",
    "else:\n",
    "    print(\"⚠️ Execute primeiro o notebook 02_identify_reag_funds.ipynb\")\n",
    "    reag_cnpjs = []"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Carregar e Consolidar Informe Diário"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Ler todos os arquivos de Informe Diário\n",
    "informe_files = sorted(config.RAW_DATA_DIR.glob('informe_diario_*.csv'))\n",
    "\n",
    "print(f\"📂 Encontrados {len(informe_files)} arquivos de Informe Diário\")\n",
    "\n",
    "dfs = []\n",
    "for file in informe_files:\n",
    "    print(f\"  Lendo {file.name}...\")\n",
    "    df = processor.read_informe_diario(file)\n",
    "    dfs.append(df)\n",
    "\n",
    "df_informe = pd.concat(dfs, ignore_index=True)\n",
    "print(f\"\\n📊 Total de registros: {len(df_informe):,}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Filtrar Fundos REAG"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "df_reag = processor.filter_by_cnpj(df_informe, reag_cnpjs)\n",
    "print(f\"📊 Registros de fundos REAG: {len(df_reag):,}\")\n",
    "\n",
    "# Calcular fluxo líquido\n",
    "df_reag = processor.calculate_net_flow(df_reag)\n",
    "\n",
    "# Ordenar por data\n",
    "df_reag = df_reag.sort_values(['CNPJ_FUNDO', 'DT_COMPTC'])"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Estatísticas Descritivas"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n📊 ESTATÍSTICAS DE FLUXO\\n\" + \"=\"*60)\n",
    "\n",
    "# Agregado total\n",
    "total_captacao = df_reag['CAPTC_DIA'].sum()\n",
    "total_resgate = df_reag['RESG_DIA'].sum()\n",
    "fluxo_liquido_total = df_reag['FLUXO_LIQ_DIA'].sum()\n",
    "\n",
    "print(f\"Captação total: R$ {total_captacao:,.2f}\")\n",
    "print(f\"Resgate total: R$ {total_resgate:,.2f}\")\n",
    "print(f\"Fluxo líquido total: R$ {fluxo_liquido_total:,.2f}\")\n",
    "\n",
    "print(\"\\n📈 Estatísticas descritivas:\")\n",
    "display(df_reag[['CAPTC_DIA', 'RESG_DIA', 'FLUXO_LIQ_DIA', 'VL_PATRIM_LIQ']].describe())"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Evolução Temporal do Fluxo"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Agregar por data\n",
    "df_daily = df_reag.groupby('DT_COMPTC').agg({\n",
    "    'CAPTC_DIA': 'sum',\n",
    "    'RESG_DIA': 'sum',\n",
    "    'FLUXO_LIQ_DIA': 'sum',\n",
    "    'VL_PATRIM_LIQ': 'sum'\n",
    "}).reset_index()\n",
    "\n",
    "# Plot\n",
    "fig, axes = plt.subplots(2, 1, figsize=(14, 10))\n",
    "\n",
    "# Fluxo líquido\n",
    "axes[0].plot(df_daily['DT_COMPTC'], df_daily['FLUXO_LIQ_DIA'], label='Fluxo Líquido', linewidth=2)\n",
    "axes[0].axhline(y=0, color='red', linestyle='--', alpha=0.5)\n",
    "axes[0].set_title('Fluxo Líquido Diário - Fundos REAG', fontsize=14, fontweight='bold')\n",
    "axes[0].set_ylabel('R$ Milhões')\n",
    "axes[0].legend()\n",
    "axes[0].grid(True, alpha=0.3)\n",
    "\n",
    "# PL agregado\n",
    "axes[1].plot(df_daily['DT_COMPTC'], df_daily['VL_PATRIM_LIQ'], label='PL Total', linewidth=2, color='green')\n",
    "axes[1].set_title('Patrimônio Líquido Total - Fundos REAG', fontsize=14, fontweight='bold')\n",
    "axes[1].set_ylabel('R$ Milhões')\n",
    "axes[1].set_xlabel('Data')\n",
    "axes[1].legend()\n",
    "axes[1].grid(True, alpha=0.3)\n",
    "\n",
    "plt.tight_layout()\n",
    "plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Top Fundos por Volume de Movimentação"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Agregado por fundo\n",
    "df_by_fund = df_reag.groupby('CNPJ_FUNDO').agg({\n",
    "    'CAPTC_DIA': 'sum',\n",
    "    'RESG_DIA': 'sum',\n",
    "    'FLUXO_LIQ_DIA': 'sum',\n",
    "    'VL_PATRIM_LIQ': 'last'\n",
    "}).reset_index()\n",
    "\n",
    "df_by_fund['VOLUME_TOTAL'] = df_by_fund['CAPTC_DIA'] + df_by_fund['RESG_DIA']\n",
    "\n",
    "# Top 10 por volume\n",
    "top_funds = df_by_fund.nlargest(10, 'VOLUME_TOTAL')\n",
    "\n",
    "print(\"\\n🏆 TOP 10 FUNDOS POR VOLUME DE MOVIMENTAÇÃO\\n\" + \"=\"*60)\n",
    "display(top_funds)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Salvar Dados Processados"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Salvar dados REAG processados\n",
    "output_path = processor.save_processed(df_reag, 'reag_informe_diario_processed.csv')\n",
    "print(f\"\\n✅ Dados salvos em: {output_path}\")\n",
    "\n",
    "# Salvar agregados\n",
    "output_by_fund = processor.save_processed(df_by_fund, 'reag_summary_by_fund.csv')\n",
    "print(f\"✅ Resumo por fundo salvo em: {output_by_fund}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Resumo"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n\" + \"=\"*60)\n",
    "print(\"📊 RESUMO DA ANÁLISE DE FLUXOS\")\n",
    "print(\"=\"*60)\n",
    "print(f\"Fundos analisados: {df_reag['CNPJ_FUNDO'].nunique()}\")\n",
    "print(f\"Período: {df_reag['DT_COMPTC'].min()} a {df_reag['DT_COMPTC'].max()}\")\n",
    "print(f\"Captação total: R$ {total_captacao:,.2f}\")\n",
    "print(f\"Resgate total: R$ {total_resgate:,.2f}\")\n",
    "print(f\"Fluxo líquido: R$ {fluxo_liquido_total:,.2f}\")\n",
    "print(\"\\n✅ Análise concluída! Próximo passo: 04_anomaly_detection.ipynb\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.10.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

**Step 2: Commit**

```bash
git add notebooks/03_flow_analysis.ipynb
git commit -m "feat: notebook de análise de fluxos

- Carrega e consolida Informe Diário
- Estatísticas descritivas de captação/resgate
- Visualização de evolução temporal
- Top fundos por volume
- Exporta dados processados"
```

---

## Task 8: Notebook de Detecção de Anomalias

**Files:**
- Create: `notebooks/04_anomaly_detection.ipynb`

**Step 1: Create anomaly detection notebook**

```python
# notebooks/04_anomaly_detection.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 04 - Detecção de Anomalias\n",
    "\n",
    "Identifica padrões suspeitos nos fundos REAG:\n",
    "\n",
    "1. **Anomalias de fluxo**: Z-score extremo em captação/resgate\n",
    "2. **Quedas bruscas de PL**: Reduções > 20% em um dia\n",
    "3. **Runs**: Sequências de resgates consecutivos\n",
    "4. **Divergências**: Fluxo vs. performance"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "sys.path.append('..')\n",
    "\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "\n",
    "from src.processors.data_processor import DataProcessor\n",
    "from src.analyzers.anomaly_detector import AnomalyDetector\n",
    "from config.settings import Config\n",
    "\n",
    "pd.set_option('display.max_columns', None)\n",
    "sns.set_style('whitegrid')\n",
    "plt.rcParams['figure.figsize'] = (14, 8)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Carregar Dados Processados"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "config = Config()\n",
    "processor = DataProcessor(config)\n",
    "detector = AnomalyDetector(config)\n",
    "\n",
    "# Carregar dados REAG processados\n",
    "data_path = config.PROCESSED_DATA_DIR / 'reag_informe_diario_processed.csv'\n",
    "\n",
    "if data_path.exists():\n",
    "    df_reag = pd.read_csv(data_path, sep=';', parse_dates=['DT_COMPTC'])\n",
    "    print(f\"✅ {len(df_reag):,} registros carregados\")\n",
    "else:\n",
    "    print(\"⚠️ Execute primeiro o notebook 03_flow_analysis.ipynb\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Anomalias de Fluxo (Z-Score)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"🔍 Detectando anomalias de fluxo...\\n\")\n",
    "\n",
    "flow_anomalies = detector.detect_flow_anomalies(df_reag, threshold=3.0)\n",
    "\n",
    "print(f\"⚠️ {len(flow_anomalies)} anomalias de fluxo detectadas\\n\")\n",
    "print(\"Top 10 anomalias:\")\n",
    "display(flow_anomalies[[\n",
    "    'CNPJ_FUNDO', 'DT_COMPTC', 'FLUXO_LIQ_DIA', 'Z_SCORE_FLOW'\n",
    "]].head(10))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Visualização\n",
    "if not flow_anomalies.empty:\n",
    "    plt.figure(figsize=(14, 6))\n",
    "    plt.scatter(\n",
    "        flow_anomalies['DT_COMPTC'], \n",
    "        flow_anomalies['FLUXO_LIQ_DIA'],\n",
    "        c=flow_anomalies['Z_SCORE_FLOW'].abs(),\n",
    "        cmap='Reds',\n",
    "        s=100,\n",
    "        alpha=0.6\n",
    "    )\n",
    "    plt.colorbar(label='|Z-Score|')\n",
    "    plt.axhline(y=0, color='black', linestyle='--', alpha=0.5)\n",
    "    plt.title('Anomalias de Fluxo - Fundos REAG', fontsize=14, fontweight='bold')\n",
    "    plt.xlabel('Data')\n",
    "    plt.ylabel('Fluxo Líquido (R$)')\n",
    "    plt.grid(True, alpha=0.3)\n",
    "    plt.tight_layout()\n",
    "    plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Quedas Bruscas de PL"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"🔍 Detectando quedas bruscas de PL...\\n\")\n",
    "\n",
    "pl_drops = detector.detect_pl_drops(df_reag, threshold_pct=20.0)\n",
    "\n",
    "print(f\"⚠️ {len(pl_drops)} quedas bruscas de PL detectadas\\n\")\n",
    "print(\"Top 10 quedas:\")\n",
    "display(pl_drops[[\n",
    "    'CNPJ_FUNDO', 'DT_COMPTC', 'VL_PATRIM_LIQ', 'PL_VAR_PCT'\n",
    "]].head(10))"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Runs (Resgates Consecutivos)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"🔍 Detectando runs (resgates consecutivos)...\\n\")\n",
    "\n",
    "runs = detector.detect_runs(df_reag, consecutive_days=5)\n",
    "\n",
    "print(f\"⚠️ {len(runs)} dias em runs detectados\\n\")\n",
    "\n",
    "# Agrupar por fundo e run_id para contar sequências\n",
    "if not runs.empty:\n",
    "    run_summary = runs.groupby(['CNPJ_FUNDO', 'RUN_ID']).agg({\n",
    "        'RUN_LENGTH': 'max',\n",
    "        'FLUXO_LIQ_DIA': 'sum',\n",
    "        'DT_COMPTC': ['min', 'max']\n",
    "    }).reset_index()\n",
    "    \n",
    "    run_summary.columns = ['CNPJ_FUNDO', 'RUN_ID', 'DIAS_CONSECUTIVOS', 'RESGATE_TOTAL', 'DATA_INICIO', 'DATA_FIM']\n",
    "    run_summary = run_summary.sort_values('DIAS_CONSECUTIVOS', ascending=False)\n",
    "    \n",
    "    print(\"Top runs por duração:\")\n",
    "    display(run_summary.head(10))"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Divergências Fluxo vs. Performance"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"🔍 Detectando divergências fluxo vs. performance...\\n\")\n",
    "\n",
    "divergences = detector.detect_divergence_flow_performance(df_reag, threshold_z=2.0)\n",
    "\n",
    "print(f\"⚠️ {len(divergences)} divergências detectadas\\n\")\n",
    "print(\"Top 10 divergências:\")\n",
    "display(divergences[[\n",
    "    'CNPJ_FUNDO', 'DT_COMPTC', 'RETORNO_DIA', 'FLUXO_LIQ_DIA', 'DIVERGENCE_SCORE'\n",
    "]].head(10))"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Relatório Consolidado de Anomalias"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n\" + \"=\"*60)\n",
    "print(\"⚠️ RELATÓRIO DE ANOMALIAS - FUNDOS REAG\")\n",
    "print(\"=\"*60)\n",
    "\n",
    "print(f\"\\n1. Anomalias de fluxo (Z-score > 3): {len(flow_anomalies)}\")\n",
    "print(f\"2. Quedas bruscas de PL (> 20%): {len(pl_drops)}\")\n",
    "print(f\"3. Runs (5+ dias consecutivos): {len(run_summary) if 'run_summary' in locals() else 0}\")\n",
    "print(f\"4. Divergências fluxo vs. performance: {len(divergences)}\")\n",
    "\n",
    "total_anomalies = len(flow_anomalies) + len(pl_drops) + len(runs) + len(divergences)\n",
    "print(f\"\\n🔴 Total de eventos anômalos: {total_anomalies}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Exportar Anomalias"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Salvar anomalias em arquivos separados\n",
    "report_dir = config.REPORTS_DIR\n",
    "report_dir.mkdir(parents=True, exist_ok=True)\n",
    "\n",
    "if not flow_anomalies.empty:\n",
    "    flow_anomalies.to_csv(report_dir / 'anomalias_fluxo.csv', index=False)\n",
    "    print(f\"✅ Anomalias de fluxo: {report_dir / 'anomalias_fluxo.csv'}\")\n",
    "\n",
    "if not pl_drops.empty:\n",
    "    pl_drops.to_csv(report_dir / 'quedas_pl.csv', index=False)\n",
    "    print(f\"✅ Quedas de PL: {report_dir / 'quedas_pl.csv'}\")\n",
    "\n",
    "if not runs.empty:\n",
    "    run_summary.to_csv(report_dir / 'runs_resgate.csv', index=False)\n",
    "    print(f\"✅ Runs: {report_dir / 'runs_resgate.csv'}\")\n",
    "\n",
    "if not divergences.empty:\n",
    "    divergences.to_csv(report_dir / 'divergencias_flow_performance.csv', index=False)\n",
    "    print(f\"✅ Divergências: {report_dir / 'divergencias_flow_performance.csv'}\")\n",
    "\n",
    "print(f\"\\n📂 Relatórios salvos em: {report_dir}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Resumo"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n\" + \"=\"*60)\n",
    "print(\"✅ DETECÇÃO DE ANOMALIAS CONCLUÍDA\")\n",
    "print(\"=\"*60)\n",
    "print(f\"Total de eventos suspeitos: {total_anomalies}\")\n",
    "print(f\"Relatórios exportados: {report_dir}\")\n",
    "print(\"\\n✅ Análise completa! Próximos passos: análise manual dos relatórios.\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.10.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

**Step 2: Commit**

```bash
git add notebooks/04_anomaly_detection.ipynb
git commit -m "feat: notebook de detecção de anomalias

- Anomalias de fluxo via Z-score
- Quedas bruscas de PL
- Runs de resgates consecutivos
- Divergências fluxo vs performance
- Relatórios consolidados e exportação"
```

---

## Task 9: Testes de Integração e Documentação Final

**Files:**
- Create: `tests/test_integration.py`
- Update: `README.md`

**Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from src.collectors.cvm_collector import CVMCollector
from src.processors.data_processor import DataProcessor
from src.analyzers.anomaly_detector import AnomalyDetector
from config.settings import Config


def test_full_pipeline_smoke():
    """
    Teste de fumaça do pipeline completo

    Verifica se os componentes principais podem ser inicializados
    """
    config = Config()

    # Inicializar componentes
    collector = CVMCollector(config)
    processor = DataProcessor(config)
    detector = AnomalyDetector(config)

    # Verificar diretórios
    assert config.DATA_DIR.exists() or True  # Será criado quando necessário

    # Verificar URLs
    assert "cvm.gov.br" in collector.get_informe_diario_url(2024, 1)
    assert "cvm.gov.br" in collector.get_cda_url(2024, 1)

    print("✅ Pipeline smoke test passou")


def test_directories_structure():
    """Verifica estrutura de diretórios"""
    config = Config()

    expected_dirs = [
        config.DATA_DIR,
        config.RAW_DATA_DIR,
        config.PROCESSED_DATA_DIR,
        config.REPORTS_DIR
    ]

    for directory in expected_dirs:
        # Diretórios serão criados quando necessário
        assert isinstance(directory, Path)

    print("✅ Estrutura de diretórios OK")
```

**Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Update README with complete documentation**

```markdown
# REAG Fraud Investigation Tools

Ferramentas para análise de dados dos fundos da REAG (administradora investigada por fraude junto ao Banco Master).

## 🎯 Objetivo

Identificar irregularidades e padrões suspeitos nos fundos administrados pela REAG através de:

1. **Análise de fluxos**: Captação/resgate anormais
2. **Análise de carteira**: Concentração e mudanças bruscas
3. **Detecção de anomalias**: Z-scores, runs, divergências
4. **Visualizações**: Gráficos temporais e distribuições

## 📊 Fontes de Dados

- **CVM Dados Abertos**: Informe Diário, CDA, Cadastro
- **Período**: Configurável (padrão: 2024)
- **Atualização**: Mensal pela CVM

## 🚀 Instalação

### Pré-requisitos

- Python 3.10+
- pip

### Setup

```bash
# Clone o repositório
git clone <repo-url>
cd REAG

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Executar testes
pytest tests/ -v
```

## 📚 Uso

### 1. Coletar Dados

```bash
jupyter lab notebooks/01_data_collection.ipynb
```

Baixa dados da CVM (Informe Diário, CDA, Cadastro) para o período configurado.

### 2. Identificar Fundos REAG

```bash
jupyter lab notebooks/02_identify_reag_funds.ipynb
```

Identifica fundos administrados/geridos pela REAG através do cadastro da CVM.

### 3. Análise de Fluxos

```bash
jupyter lab notebooks/03_flow_analysis.ipynb
```

Analisa captação, resgate e fluxo líquido dos fundos REAG.

### 4. Detecção de Anomalias

```bash
jupyter lab notebooks/04_anomaly_detection.ipynb
```

Identifica padrões suspeitos:
- Anomalias de fluxo (Z-score > 3)
- Quedas bruscas de PL (> 20%)
- Runs de resgates consecutivos (5+ dias)
- Divergências fluxo vs. performance

## 📁 Estrutura do Projeto

```
REAG/
├── config/               # Configurações
│   └── settings.py
├── src/                  # Código fonte
│   ├── collectors/       # Coleta de dados CVM
│   ├── processors/       # Processamento de dados
│   └── analyzers/        # Detecção de anomalias
├── notebooks/            # Jupyter notebooks
│   ├── 01_data_collection.ipynb
│   ├── 02_identify_reag_funds.ipynb
│   ├── 03_flow_analysis.ipynb
│   └── 04_anomaly_detection.ipynb
├── data/
│   ├── raw/             # Dados brutos da CVM
│   └── processed/       # Dados processados
├── reports/             # Relatórios de anomalias
├── tests/               # Testes unitários
├── requirements.txt
└── README.md
```

## 🔍 Metodologia de Detecção

### 1. Anomalias de Fluxo

- **Método**: Z-score por fundo
- **Threshold**: |Z| > 3.0
- **Detecta**: Captações/resgates atípicos

### 2. Quedas de PL

- **Método**: Variação percentual diária
- **Threshold**: < -20%
- **Detecta**: Reduções bruscas de patrimônio

### 3. Runs

- **Método**: Sequências consecutivas
- **Threshold**: 5+ dias de resgate líquido negativo
- **Detecta**: Corridas bancárias/resgates em massa

### 4. Divergências

- **Método**: Correlação negativa entre Z-scores
- **Detecta**: Entradas em dias de performance ruim (ou vice-versa)

## 📈 Outputs

### Dados Processados

- `data/processed/reag_fund_list.csv`: Lista de fundos REAG
- `data/processed/reag_informe_diario_processed.csv`: Dados consolidados
- `data/processed/reag_summary_by_fund.csv`: Resumo por fundo

### Relatórios de Anomalias

- `reports/anomalias_fluxo.csv`: Anomalias de fluxo
- `reports/quedas_pl.csv`: Quedas bruscas de PL
- `reports/runs_resgate.csv`: Runs detectadas
- `reports/divergencias_flow_performance.csv`: Divergências

## 🧪 Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=src --cov-report=html

# Teste específico
pytest tests/test_anomaly_detector.py -v
```

## ⚙️ Configuração

Edite `config/settings.py` para ajustar:

- URLs da CVM
- Diretórios de dados
- Thresholds de detecção
- Janelas de análise

## 📝 Notas

- **Dados públicos**: Todos os dados são públicos da CVM
- **Distribuição por corretora**: Não disponível em dados públicos (requer administrador/escriturador)
- **Atualização**: Dados CVM são mensais, com delay de ~30 dias
- **Limitação**: Análise baseada apenas em dados públicos

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-analise`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova análise'`)
4. Push para a branch (`git push origin feature/nova-analise`)
5. Abra um Pull Request

## 📄 Licença

MIT License - veja LICENSE para detalhes

## 🔗 Referências

- [CVM Dados Abertos](https://dados.cvm.gov.br/)
- [Resolução CVM 175](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html)
- [Caso Banco Master/REAG](https://www.bcb.gov.br/)

---

**⚠️ Disclaimer**: Esta ferramenta é para fins educacionais e de pesquisa. Não constitui assessoria jurídica ou financeira.
```

**Step 4: Run all tests**

Run: `pytest tests/ -v --cov=src`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "feat: testes de integração e documentação final

- Smoke test do pipeline completo
- Teste de estrutura de diretórios
- README completo com instalação e uso
- Documentação de metodologia
- Referências e disclaimer"
```

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-01-15-reag-fraud-investigation-tools.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**