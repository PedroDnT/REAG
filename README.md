# Brazilian Fund Fraud Investigation Tools

Ferramentas flexíveis para análise de fraudes em fundos de investimento brasileiros usando dados públicos da CVM.

**Exemplo de Uso:** Originalmente desenvolvido para investigar fundos da REAG (administradora investigada por fraude junto ao Banco Master), mas funciona com qualquer fundo ou administradora.

# MASTER 😉 Objective

Prova C*ncpect, or MVS. Sim, sloppy code, CVM Dados Abertos não tratados e baixo rigor estatístico. Mas será que, mesmo assim, em quanto tempo eu conseguiria, se em uma semana com um iphone no LN de SP consegui levantar suspeitas, por que tantos anos para agirem ? 

Está aí o resultado. Talvez tenhamos um pouco a melhorar.

## 🎯 Objetivo

Identificar irregularidades e padrões suspeitos em fundos de investimento através de:

1. **Análise de fluxos**: Captação/resgate anormais
2. **Análise de carteira**: Concentração e mudanças bruscas
3. **Detecção de anomalias**: Z-scores, runs, divergências
4. **Visualizações**: Gráficos temporais e distribuições

**Flexibilidade:** Analise fundos por:
- Administradora (ex: "REAG DTVM", "XYZ Administradora")
- Gestora (ex: "ABC Gestora")
- Lista específica de CNPJs
- Todo o mercado (comparação de pares)

## 📊 Fontes de Dados

- **CVM Dados Abertos**: Informe Diário, CDA, Cadastro
- **Formato**: ZIP comprimido (desde maio/2022)
- **Período**: Últimos 12 meses disponíveis no portal
- **Atualização**: Diária (meses corrente e anterior), semanal (demais meses)
- **Histórico**: Dados anteriores a 12 meses devem ser baixados do arquivo histórico

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

### Modo Rápido: Interface Interativa

```bash
# Assistente interativo no terminal
python scripts/investigation_tui.py
```

O assistente guia você através de:
1. Escolha do foco de investigação (fluxos, carteira, networks, completo)
2. Seleção de fundos (por nome, CNPJ, administradora, etc.)
3. Execução do pipeline de análise
4. Geração opcional de relatórios

### Modo Avançado: Passo a Passo

### 1. Coletar Dados

```bash
jupyter lab notebooks/01_data_collection.ipynb
```

Baixa dados da CVM (Informe Diário, CDA, Cadastro) para o período configurado.

### 2. Identificar Fundos Alvo

```bash
jupyter lab notebooks/02_identify_target_funds.ipynb
```

Identifica fundos para investigação através do cadastro da CVM. Suporta:
- Busca por administradora (ex: "REAG", "XYZ DTVM")
- Busca por gestora
- Lista explícita de CNPJs
- Todos os fundos (para benchmarking)

**Configuração:** Edite `config/settings.py` para definir:
- `TARGET_FUND_MODE`: "administrator", "manager", "fund_list", "all"
- `TARGET_IDENTIFIER`: Nome da administradora/gestora
- `INVESTIGATION_NAME`: Nome para relatórios (ex: "REAG", "MyFund")

### 3. Análise de Fluxos

```bash
jupyter lab notebooks/03_flow_analysis.ipynb
```

Analisa captação, resgate e fluxo líquido dos fundos selecionados.

### 4. Detecção de Anomalias

```bash
jupyter lab notebooks/04_anomaly_detection.ipynb
```

Identifica padrões suspeitos:
- Anomalias de fluxo (Z-score > 3)
- Quedas bruscas de PL (> 20%)
- Runs de resgates consecutivos (5+ dias)
- Divergências fluxo vs. performance

### 5. Geração de Relatório Público

```bash
# Gerar relatório em Markdown
python scripts/generate_public_report.py --format markdown

# Gerar relatório em HTML
python scripts/generate_public_report.py --format html

# Gerar relatório em JSON
python scripts/generate_public_report.py --format json

# Especificar arquivo de saída
python scripts/generate_public_report.py --format html --output meu_relatorio.html
```

Gera um relatório público agregando todas as anomalias detectadas:
- Página HTML simples com métodos e resultados obtidos
- Saída anonimizada para compartilhamento público

SUGERIDO:
git stash 
git reset --hard
git filter-branch --force 

git clean -fdx:

### 6. Assistente interativo no terminal

```bash
python scripts/investigation_tui.py
```

O assistente em modo texto guia a escolha do foco da investigação, permite usar
os caminhos padrão ou arquivos customizados, permite buscar fundos listados por
nome/CNPJ e selecionar 1+ fundos, executa o pipeline correspondente e faz uma
pergunta final para gerar (ou não) o relatório.

## 🔁 CI/CD

- **CI**: pipeline automático para instalar dependências e rodar testes (`pytest`)
- **CD**: pipeline para gerar relatório público HTML e publicar como artifact

### 7. Automação de fluxo com Playwright

Para automatizar um fluxo de navegador com Playwright, configure as variáveis de
ambiente e execute:

```bash
python scripts/playwright_workflow.py
```

Consulte `docs/playwright_workflow.md` para os detalhes de configuração.

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
├── scripts/              # Scripts utilitáriosç
│   └── generate_public_report.py
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

### 5. 🆕 Benford's Law Analysis

- **Método**: Análise de distribuição de primeiro dígito
- **Threshold**: MAD > 0.015 ou p-value < 0.05
- **Detecta**: Números fabricados/manipulados
- **Sucesso**: Usado em casos Enron, Madoff
- **Guia completo**: Ver `BENFORD_LAW_USAGE_GUIDE.md`

### 6. 🆕 Benchmark de Métodos

Para comparação detalhada de todos os métodos de detecção:
- **Documento**: `FRAUD_INVESTIGATION_BENCHMARK.md`
- **Compara**: Precisão, Recall, Velocidade de cada método
- **Recomenda**: Métodos adicionais (ML, Network Analysis)

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
- `reports/public_report.[md|html|json]`: Relatório público agregado



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
6. Stash * vorcarro.

## 📄 Licença

MIT License - veja LICENSE para detalhes

## 🔗 Referências

- [CVM Dados Abertos](https://dados.cvm.gov.br/)
- [Resolução CVM 175](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html)
- [Caso Banco Master/REAG](https://www.bcb.gov.br/)

---

**⚠️ Disclaimer**: Esta ferramenta é para fins educacionais e de pesquisa. Não constitui assessoria jurídica ou financeira.
