# Top 10 fundos REAG mais relevantes (camada 2)

Critério: ranking heurístico combinando escala (volume/fluxo) + sinais de estresse (runs) + contagens de eventos (anomalias de fluxo, quedas de PL, divergências).

Fontes: `data/processed/reag_fund_list.csv`, `data/processed/reag_summary_by_fund.csv`, `reports/*.csv`.

## 1. 41.751.844/0001-51
- Denominação: MARSELHA FUNDO DE  INVESTIMENTO FINANCEIRO CRÉDITO PRIVADO RESPONSABILIDADE LIMITADA
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 14,581,025,985.97; FLUXO_LIQ (abs) ≈ R$ 14,554,625,985.97; PL final ≈ R$ 0.00
- Runs de resgate: maior sequência = 134 dias; |resgates acumulados (runs)| ≈ R$ 14,039,687,279.53
- Anomalias de fluxo: 0 eventos; max Z ≈ n/a
- Quedas bruscas de PL: 4 eventos; pior PL_VAR_PCT ≈ -100.00%
- Divergências fluxo vs retorno: 3 eventos; max score ≈ 10.63
- Leitura inicial: sequências longas de resgate (estresse prolongado); fluxo agregado na casa de bilhões; divergências recorrentes fluxo/performance.

## 2. 36.886.028/0001-15
- Denominação: ALEPO FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS NÃO PADRONIZADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 5,218,711,855.23; FLUXO_LIQ (abs) ≈ R$ 5,106,449,851.49; PL final ≈ R$ 7,542,495,525.43
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 12 eventos; max Z ≈ 7.67
- Quedas bruscas de PL: 1 eventos; pior PL_VAR_PCT ≈ -52.44%
- Divergências fluxo vs retorno: 1 eventos; max score ≈ 3.49
- Leitura inicial: fluxo agregado na casa de bilhões; muitos outliers de fluxo (z-score alto recorrente).

## 3. 32.313.878/0001-73
- Denominação: REAG MASTER FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 2,884,791,739.26; FLUXO_LIQ (abs) ≈ R$ 695,453,329.76; PL final ≈ R$ 103,274,123.40
- Runs de resgate: maior sequência = 6 dias; |resgates acumulados (runs)| ≈ R$ 75,165,497.27
- Anomalias de fluxo: 4 eventos; max Z ≈ 13.06
- Quedas bruscas de PL: 8 eventos; pior PL_VAR_PCT ≈ -100.00%
- Divergências fluxo vs retorno: 2 eventos; max score ≈ 10.12
- Leitura inicial: muitas quedas de PL (datas para reconciliação); divergências recorrentes fluxo/performance.

## 4. 45.616.130/0001-91
- Denominação: CREDIT OPS FUNDO DE INVESTIMENTO MULTIMERCADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 1,013,000,000.00; FLUXO_LIQ (abs) ≈ R$ 1,013,000,000.00; PL final ≈ R$ 1,097,805,268.31
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 1 eventos; max Z ≈ 12.29
- Quedas bruscas de PL: 2 eventos; pior PL_VAR_PCT ≈ -36.38%
- Divergências fluxo vs retorno: 0 eventos; max score ≈ n/a
- Leitura inicial: fluxo agregado na casa de bilhões.

## 5. 36.896.886/0001-40
- Denominação: ARC I FUNDO DE INVESTIMENTO EM COTAS DE FUNDOS DE INVESTIMENTO EM DIREITOS CREDITÓRIOS
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 209,687,413.52; FLUXO_LIQ (abs) ≈ R$ 209,687,413.52; PL final ≈ R$ 161,693,678.24
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 2 eventos; max Z ≈ 6.65
- Quedas bruscas de PL: 3 eventos; pior PL_VAR_PCT ≈ -56.03%
- Divergências fluxo vs retorno: 0 eventos; max score ≈ n/a

## 6. 48.963.233/0001-16
- Denominação: CIB-P FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 17,461,486.88; FLUXO_LIQ (abs) ≈ R$ 17,461,486.88; PL final ≈ R$ 42,265,626.66
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 17 eventos; max Z ≈ 6.84
- Quedas bruscas de PL: 0 eventos; pior PL_VAR_PCT ≈ n/a
- Divergências fluxo vs retorno: 2 eventos; max score ≈ 30.99
- Leitura inicial: muitos outliers de fluxo (z-score alto recorrente); divergências recorrentes fluxo/performance.

## 7. 36.935.858/0001-95
- Denominação: ZEFIROS FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 20,309,287.27; FLUXO_LIQ (abs) ≈ R$ 20,013,145.39; PL final ≈ R$ 21,188,795.59
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 1 eventos; max Z ≈ 22.38
- Quedas bruscas de PL: 4 eventos; pior PL_VAR_PCT ≈ -385.19%
- Divergências fluxo vs retorno: 0 eventos; max score ≈ n/a

## 8. 21.596.695/0001-96
- Denominação: HELVETIA FUNDO DE INVESTIMENTO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro): LIQUIDAÇÃO
- Escala: VOLUME_TOTAL ≈ R$ 12,731,002.60; FLUXO_LIQ (abs) ≈ R$ 12,731,002.60; PL final ≈ R$ 0.00
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 1 eventos; max Z ≈ -15.49
- Quedas bruscas de PL: 2 eventos; pior PL_VAR_PCT ≈ -100.00%
- Divergências fluxo vs retorno: 0 eventos; max score ≈ n/a

## 9. 46.879.122/0001-09
- Denominação: BOJNICE 421 FUNDO DE INVESTIMENTO IMOBILIÁRIO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 13,000,000.00; FLUXO_LIQ (abs) ≈ R$ 13,000,000.00; PL final ≈ R$ 14,156,726.41
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 1 eventos; max Z ≈ 9.38
- Quedas bruscas de PL: 0 eventos; pior PL_VAR_PCT ≈ n/a
- Divergências fluxo vs retorno: 1 eventos; max score ≈ 7.99

## 10. 33.521.273/0001-30
- Denominação: FERA12 95 FUNDO DE INVESTIMENTO EM COTAS DE FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO
- Situação (cadastro): CANCELADA
- Escala: VOLUME_TOTAL ≈ R$ 10,000,000.00; FLUXO_LIQ (abs) ≈ R$ 10,000,000.00; PL final ≈ R$ 822,339,021.84
- Runs de resgate: não apareceu nos relatórios de runs (threshold 5+ dias).
- Anomalias de fluxo: 2 eventos; max Z ≈ 16.96
- Quedas bruscas de PL: 0 eventos; pior PL_VAR_PCT ≈ n/a
- Divergências fluxo vs retorno: 0 eventos; max score ≈ n/a

---
## Próximos passos (para transformar em narrativa)
- Para cada fundo do top 10: gerar linha do tempo (PL, CAPTC_DIA, RESG_DIA, retorno diário) e marcar as datas presentes nos CSVs de anomalia/run/queda/divergência.
- Fazer join com classe/subclasse e filtrar eventos que ocorrem após mudança de status (ex.: LIQUIDAÇÃO/CANCELADA) para reduzir falso positivo.
- Deduplicar eventos por (CNPJ, DT_COMPTC) antes de métricas agregadas.