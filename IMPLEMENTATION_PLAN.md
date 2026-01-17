# Plano de Implementação - Correção Crítica de Coleta de Dados

**Data:** 2026-01-16
**Branch:** `claude/review-repo-improvements-zweSL`
**Prioridade:** 🔴 CRÍTICA

---

## 🔍 Investigação Completa - URLs da CVM

### ✅ Descobertas da Investigação

#### 1. **Informe Diário** (`/FI/DOC/INF_DIARIO/DADOS/`)

**Status:** ✅ Estrutura CORRETA no código

- **Formato:** ZIP (não CSV direto!)
- **Padrão:** `inf_diario_fi_YYYYMM.zip`
- **Disponibilidade:** 202101 (Jan 2021) → 202601 (Jan 2026)
- **Tamanho:** 5-12 MB por arquivo
- **Exemplo:** `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202401.zip`

**Problema Identificado:** Código já suporta ZIP, mas notebooks tentam baixar meses futuros que não existem.

---

#### 2. **Cadastro** (`/FI/CAD/DADOS/`)

**Status:** ❌ Estrutura INCORRETA no código

- **Formato Atual CVM:**
  - `cad_fi.csv` (17M, atualizado 2026-01-16) ← arquivo único atual
  - `cad_fi_hist.zip` (17M) ← histórico completo
  - `registro_fundo_classe.zip` (6M)

- **Formato que o Código Espera:**
  - `cad_fi_YYYYMM.csv` ← NÃO EXISTE!

**Problema Identificado:** CVM não publica Cadastro mensalmente. É um arquivo único que contém todos os fundos ativos.

**Solução:** Baixar apenas `cad_fi.csv` (versão atual) ou `cad_fi_hist.zip` (histórico completo).

---

#### 3. **CDA - Composição de Carteira** (`/FI/DOC/CDA/DADOS/`)

**Status:** ✅ Estrutura CORRETA no código

- **Formato:** ZIP
- **Padrão:** `cda_fi_YYYYMM.zip`
- **Disponibilidade:** 202301 (Jan 2023) → 202512 (Dez 2025)
- **Tamanho:** 13-24 MB por arquivo
- **Exemplo:** `https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_202412.zip`

**Problema Identificado:** Notebooks tentam baixar 2025-01 em diante, mas CVM só tem até 2025-12.

---

## 🎯 Plano de Correção

### Fase 1: Correções Imediatas (Alta Prioridade)

#### ✅ Task 1.1: Corrigir Método de Cadastro

**Arquivo:** `src/collectors/cvm_collector.py`

**Mudança Necessária:**

```python
def download_cadastro(self, use_current: bool = True) -> Optional[Path]:
    """
    Baixa Cadastro de Fundos

    Args:
        use_current: Se True, baixa arquivo atual (cad_fi.csv)
                     Se False, baixa histórico completo (cad_fi_hist.zip)

    Nota: Cadastro NÃO é mensal - é um arquivo único atualizado regularmente
    """
    if use_current:
        url = f"{self.config.CVM_CADASTRO_URL}/cad_fi.csv"
        filename = "cad_fi.csv"
    else:
        url = f"{self.config.CVM_CADASTRO_URL}/cad_fi_hist.zip"
        filename = "cad_fi_hist.zip"

    output_path = self.config.RAW_DATA_DIR / filename

    if output_path.exists():
        print(f"Arquivo já existe: {output_path}")
        return output_path

    success = self.download_file(url, output_path)

    # Se for ZIP, extrair
    if success and filename.endswith('.zip'):
        extracted_path = self.extract_zip(output_path)
        if extracted_path and output_path.exists():
            output_path.unlink()  # Remove ZIP após extração
        return extracted_path

    return output_path if success else None
```

**Impacto:** Remove erros 404 para Cadastro.

---

#### ✅ Task 1.2: Adicionar Verificação de Disponibilidade

**Arquivo:** `src/collectors/cvm_collector.py`

**Novo Método:**

```python
def check_file_exists(self, url: str) -> bool:
    """
    Verifica se arquivo existe na CVM usando HEAD request

    Returns:
        True se arquivo existe (HTTP 200), False caso contrário
    """
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao verificar {url}: {e}")
        return False

def get_available_months(self, data_type: str = 'informe_diario',
                        start_year: int = 2021,
                        end_year: int = 2026) -> list:
    """
    Lista meses disponíveis na CVM para um tipo de dado

    Args:
        data_type: 'informe_diario' ou 'cda'
        start_year: Ano inicial para verificar
        end_year: Ano final para verificar

    Returns:
        Lista de tuplas (year, month) disponíveis
    """
    available = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if data_type == 'informe_diario':
                url = self.get_informe_diario_url(year, month)
            elif data_type == 'cda':
                url = self.get_cda_url(year, month)
            else:
                continue

            if self.check_file_exists(url):
                available.append((year, month))
            else:
                # Se encontrar mês não disponível, assume que meses futuros também não estão
                if year * 12 + month > datetime.now().year * 12 + datetime.now().month:
                    break

    return available
```

**Impacto:** Evita tentativas de download de arquivos inexistentes.

---

#### ✅ Task 1.3: Adicionar Retry Logic com Exponential Backoff

**Arquivo:** `src/collectors/cvm_collector.py`

**Modificar Método Existente:**

```python
def download_file(self, url: str, output_path: Path,
                 max_retries: int = 4) -> bool:
    """
    Baixa arquivo da URL e salva localmente com retry logic

    Args:
        url: URL do arquivo
        output_path: Caminho de saída
        max_retries: Número máximo de tentativas (padrão: 4)

    Returns:
        True se sucesso, False caso contrário
    """
    import time

    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True,
                         desc=output_path.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            return True

        except requests.exceptions.HTTPError as e:
            # Erros 4xx (cliente) não devem ter retry
            if 400 <= e.response.status_code < 500:
                print(f"Erro HTTP {e.response.status_code}: {url}")
                return False

            # Erros 5xx (servidor) podem ter retry
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s
                print(f"Erro no download (tentativa {attempt + 1}/{max_retries}). "
                      f"Aguardando {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Falha após {max_retries} tentativas: {url}")
                return False

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Erro: {e}. Tentando novamente em {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Erro ao baixar {url}: {e}")
                return False

    return False
```

**Impacto:** Resolve problemas transitórios de rede.

---

#### ✅ Task 1.4: Atualizar Método `download_period`

**Arquivo:** `src/collectors/cvm_collector.py`

**Modificar:**

```python
def download_period(self, start_year: int, start_month: int,
                   end_year: int, end_month: int,
                   data_types: list[str] = ['informe_diario', 'cda', 'cadastro'],
                   check_availability: bool = True):
    """
    Baixa dados para um período completo

    Args:
        start_year, start_month: Período inicial
        end_year, end_month: Período final
        data_types: Tipos de dados para baixar
        check_availability: Se True, verifica disponibilidade antes de baixar
    """
    results = []

    # Baixar Cadastro (arquivo único, não mensal)
    if 'cadastro' in data_types:
        print("\n=== Baixando Cadastro (arquivo único) ===")
        path = self.download_cadastro(use_current=True)
        if path:
            results.append(('cadastro', None, None, path))

    # Para dados mensais (Informe Diário e CDA)
    current_year = start_year
    current_month = start_month

    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        print(f"\n=== Baixando dados de {current_year}-{current_month:02d} ===")

        if 'informe_diario' in data_types:
            # Verificar disponibilidade
            url = self.get_informe_diario_url(current_year, current_month)
            if check_availability and not self.check_file_exists(url):
                print(f"⚠️  Arquivo não disponível: {url}")
            else:
                path = self.download_informe_diario(current_year, current_month)
                if path:
                    results.append(('informe_diario', current_year, current_month, path))

        if 'cda' in data_types:
            # CDA só disponível a partir de 2023-01
            if current_year >= 2023:
                url = self.get_cda_url(current_year, current_month)
                if check_availability and not self.check_file_exists(url):
                    print(f"⚠️  Arquivo não disponível: {url}")
                else:
                    path = self.download_cda(current_year, current_month)
                    if path:
                        results.append(('cda', current_year, current_month, path))

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return results
```

**Impacto:** Processo de download mais robusto e informativo.

---

### Fase 2: Atualizar Configurações

#### ✅ Task 2.1: Atualizar `config/settings.py`

**Adicionar:**

```python
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
```

---

#### ✅ Task 2.2: Atualizar Notebooks

**Arquivo:** `notebooks/01_data_collection.ipynb`

**Mudanças:**

```python
# Cell de configuração - ANTES:
START_YEAR = 2024
START_MONTH = 1
END_YEAR = 2025
END_MONTH = 12

# Cell de configuração - DEPOIS:
from config.settings import Config

config = Config()
collector = CVMCollector(config)

# Usar período com dados disponíveis
START_YEAR = config.DEFAULT_START_YEAR
START_MONTH = config.DEFAULT_START_MONTH
END_YEAR = config.DEFAULT_END_YEAR
END_MONTH = config.DEFAULT_END_MONTH

print(f"Período de análise: {START_YEAR}-{START_MONTH:02d} a {END_YEAR}-{END_MONTH:02d}")

# Verificar disponibilidade antes de baixar
print("\nVerificando disponibilidade de dados...")
available_informe = collector.get_available_months('informe_diario', START_YEAR, END_YEAR)
available_cda = collector.get_available_months('cda', START_YEAR, END_YEAR)

print(f"✅ Informe Diário: {len(available_informe)} meses disponíveis")
print(f"✅ CDA: {len(available_cda)} meses disponíveis")
```

---

### Fase 3: Testes e Validação

#### ✅ Task 3.1: Atualizar Testes

**Arquivo:** `tests/test_cvm_collector.py`

**Adicionar Testes:**

```python
def test_check_file_exists():
    """Testa verificação de existência de arquivo"""
    collector = CVMCollector()

    # Arquivo que deve existir (Jan/2024)
    url_exists = collector.get_informe_diario_url(2024, 1)
    assert collector.check_file_exists(url_exists) == True

    # Arquivo que não deve existir (futuro)
    url_not_exists = collector.get_informe_diario_url(2030, 12)
    assert collector.check_file_exists(url_not_exists) == False

def test_get_available_months():
    """Testa listagem de meses disponíveis"""
    collector = CVMCollector()

    available = collector.get_available_months('informe_diario', 2024, 2024)

    # Deve ter pelo menos alguns meses de 2024
    assert len(available) > 0
    assert all(isinstance(item, tuple) for item in available)
    assert all(len(item) == 2 for item in available)

def test_download_cadastro_new_format():
    """Testa download do Cadastro no novo formato"""
    collector = CVMCollector()

    path = collector.download_cadastro(use_current=True)

    assert path is not None
    assert path.exists()
    assert path.name == 'cad_fi.csv'

def test_retry_logic():
    """Testa retry logic com mock de falha transitória"""
    # Implementar teste com mock de requests
    pass
```

---

#### ✅ Task 3.2: Script de Validação

**Novo arquivo:** `scripts/validate_data_collection.py`

```python
#!/usr/bin/env python
"""
Script para validar coleta de dados da CVM
"""
import sys
sys.path.append('..')

from src.collectors.cvm_collector import CVMCollector
from config.settings import Config

def main():
    print("="*60)
    print("VALIDAÇÃO DE COLETA DE DADOS - CVM")
    print("="*60)

    config = Config()
    collector = CVMCollector(config)

    # 1. Verificar conectividade
    print("\n1. Verificando conectividade com CVM...")
    test_url = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
    if collector.check_file_exists(test_url):
        print("✅ Conexão com CVM: OK")
    else:
        print("❌ Conexão com CVM: FALHOU")
        return

    # 2. Testar Cadastro
    print("\n2. Testando download de Cadastro...")
    try:
        path = collector.download_cadastro(use_current=True)
        if path and path.exists():
            print(f"✅ Cadastro baixado: {path}")
            print(f"   Tamanho: {path.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("❌ Falha no download de Cadastro")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # 3. Testar Informe Diário
    print("\n3. Testando download de Informe Diário (Jan/2024)...")
    try:
        path = collector.download_informe_diario(2024, 1)
        if path and path.exists():
            print(f"✅ Informe Diário baixado: {path}")
            print(f"   Tamanho: {path.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("❌ Falha no download de Informe Diário")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # 4. Testar CDA
    print("\n4. Testando download de CDA (Jan/2024)...")
    try:
        path = collector.download_cda(2024, 1)
        if path and path.exists():
            print(f"✅ CDA baixado: {path}")
            print(f"   Tamanho: {path.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print("❌ Falha no download de CDA")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # 5. Listar meses disponíveis
    print("\n5. Listando meses disponíveis...")
    try:
        available_informe = collector.get_available_months('informe_diario', 2024, 2024)
        print(f"✅ Informe Diário 2024: {len(available_informe)} meses")
        print(f"   Meses: {available_informe}")

        available_cda = collector.get_available_months('cda', 2024, 2024)
        print(f"✅ CDA 2024: {len(available_cda)} meses")
        print(f"   Meses: {available_cda}")
    except Exception as e:
        print(f"❌ Erro: {e}")

    print("\n" + "="*60)
    print("VALIDAÇÃO CONCLUÍDA")
    print("="*60)

if __name__ == '__main__':
    main()
```

**Uso:**
```bash
python scripts/validate_data_collection.py
```

---

## 📋 Checklist de Implementação

### Fase 1: Código Core
- [ ] Modificar `download_cadastro()` para novo formato
- [ ] Adicionar `check_file_exists()`
- [ ] Adicionar `get_available_months()`
- [ ] Modificar `download_file()` com retry logic
- [ ] Atualizar `download_period()`

### Fase 2: Configuração
- [ ] Adicionar constantes em `config/settings.py`
- [ ] Atualizar notebook `01_data_collection.ipynb`
- [ ] Atualizar notebook `02_identify_reag_funds.ipynb` (se necessário)

### Fase 3: Testes
- [ ] Adicionar novos testes unitários
- [ ] Criar script de validação
- [ ] Executar testes: `pytest tests/ -v`
- [ ] Executar validação: `python scripts/validate_data_collection.py`

### Fase 4: Documentação
- [ ] Atualizar README.md
- [ ] Adicionar seção "Disponibilidade de Dados"
- [ ] Documentar limitações conhecidas

### Fase 5: Validação Final
- [ ] Executar pipeline completo end-to-end
- [ ] Verificar que dados são baixados corretamente
- [ ] Confirmar que notebooks funcionam
- [ ] Validar análise de anomalias

---

## 🎯 Critérios de Sucesso

1. ✅ Todos os downloads funcionam sem erros 403/404
2. ✅ Verificação de disponibilidade previne tentativas inúteis
3. ✅ Retry logic resolve problemas transitórios
4. ✅ Cadastro é baixado corretamente (arquivo único)
5. ✅ Notebooks executam sem erros
6. ✅ Pipeline end-to-end funcional
7. ✅ Testes passam com 100% de sucesso

---

## 📊 Métricas de Validação

Após implementação, validar:

```python
# Informe Diário
- Disponibilidade: 2021-01 a 2026-01 (✓)
- Arquivos baixados: 12 meses de 2024 (✓)
- Taxa de sucesso: 100% (✓)

# CDA
- Disponibilidade: 2023-01 a 2025-12 (✓)
- Arquivos baixados: 12 meses de 2024 (✓)
- Taxa de sucesso: 100% (✓)

# Cadastro
- Arquivo: cad_fi.csv (✓)
- Tamanho: ~17 MB (✓)
- Atualização: 2026-01-16 (✓)
```

---

## 🚨 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| CVM muda estrutura novamente | Média | Alto | Monitorar site, criar alertas |
| Dados atrasados | Alta | Médio | Aceitar delay de 30 dias |
| Download interrompido | Baixa | Médio | Retry logic implementado |
| Arquivo corrompido | Baixa | Alto | Validar checksums (futuro) |

---

## 📅 Timeline Estimado

**Total: 4-6 horas**

- Fase 1 (Código): 2 horas
- Fase 2 (Config): 30 minutos
- Fase 3 (Testes): 1 hora
- Fase 4 (Docs): 30 minutos
- Fase 5 (Validação): 1 hora

---

## 🔄 Próximos Passos Após Correção

Uma vez que a coleta de dados esteja funcional:

1. **Executar pipeline completo**
   - Baixar dados de 2024
   - Identificar fundos REAG
   - Analisar fluxos
   - Detectar anomalias

2. **Implementar melhorias de Fase 2**
   - Benford's Law
   - Window dressing detection
   - Integrated analysis

3. **Criar dashboard**
   - Streamlit app
   - Visualizações interativas

---

**Documento criado por:** Claude Code Analysis
**Próxima ação:** Implementar modificações em `src/collectors/cvm_collector.py`
