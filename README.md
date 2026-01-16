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
