# Top 10 fundos REAG (camada 2) — reconstruído

**Período: 2024-01-01 a 2025-12-31.** O documento original não registrava a
janela usada. Ela foi recuperada por checksum: `VOLUME_TOTAL` e `FLUXO_LIQ` são
agregações puras do informe diário, imunes a qualquer mudança de detector, e
esta é a única janela contígua em 2024–2025 na qual os **10 de 10** fundos
reproduzem os dois valores arquivados até o centavo.

Fonte: informe diário da CVM, 24 arquivos mensais. Reprocessado com o pipeline
atual — os números de detector abaixo **não** são os do arquivo original, e a
coluna de diferença é o ponto principal deste documento.

> Sinais estatísticos não provam irregularidade. Exigem corroboração contra
> registros que estes dados não contêm.

## O que mudou, e por quê

| Métrica | Arquivo | Agora | Leitura |
|---|---:|---:|---|
| Escala (VOLUME_TOTAL, FLUXO_LIQ) | — | — | **idêntica nos 10 fundos** — é o checksum que fixou o período |
| Runs de resgate (dias) | 140 | 140 | inalterado: o teste de magnitude adicionado não corta runs desta escala |
| Anomalias de fluxo | 41 | 41 | inalterado |
| Quedas bruscas de PL | 24 | 24 | inalterado |
| Divergências fluxo/retorno | 9 | 6 | **−3**: o limiar antigo era dimensionalmente incorreto e admitia movimentos de 1,5σ |

As três primeiras métricas reproduzem o arquivo exatamente, o que valida tanto a
janela recuperada quanto o pipeline. A quarta é a correção: três divergências
arquivadas eram falsos positivos do limiar antigo. O maior score sobrevivente
(30,99) coincide com o evento de maior score citado no documento original.

## Fundos

### 1. 41.751.844/0001-51
- Denominação: MARSELHA FUNDO DE INVESTIMENTO FINANCEIRO CRÉDITO PRIVADO RESPONSABILIDADE LIMITADA
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 488
- VOLUME_TOTAL: R$ 14,581,025,985.97; FLUXO_LIQ: R$ -14,554,625,985.97; PL final: R$ 0.00
- Runs de resgate — maior sequência: 134 dias (igual vs arquivo)
- Anomalias de fluxo: 0 (igual)
- Quedas bruscas de PL: 4 (igual)
- Divergências fluxo/retorno: 2 (**-1**)

### 2. 36.886.028/0001-15
- Denominação: ALEPO FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS NÃO PADRONIZADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 467
- VOLUME_TOTAL: R$ 5,218,711,855.23; FLUXO_LIQ: R$ 5,106,449,851.49; PL final: R$ 7,542,495,525.43
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 12 (igual)
- Quedas bruscas de PL: 1 (igual)
- Divergências fluxo/retorno: 0 (**-1**)

### 3. 32.313.878/0001-73
- Denominação: REAG MASTER FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 497
- VOLUME_TOTAL: R$ 2,884,791,739.26; FLUXO_LIQ: R$ 695,453,329.76; PL final: R$ 103,274,123.40
- Runs de resgate — maior sequência: 6 dias (igual vs arquivo)
- Anomalias de fluxo: 4 (igual)
- Quedas bruscas de PL: 8 (igual)
- Divergências fluxo/retorno: 2 (igual)

### 4. 45.616.130/0001-91
- Denominação: CREDIT OPS FUNDO DE INVESTIMENTO MULTIMERCADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 153
- VOLUME_TOTAL: R$ 1,013,000,000.00; FLUXO_LIQ: R$ 1,013,000,000.00; PL final: R$ 1,097,805,268.31
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 1 (igual)
- Quedas bruscas de PL: 2 (igual)
- Divergências fluxo/retorno: 0 (igual)

### 5. 36.896.886/0001-40
- Denominação: ARC I FUNDO DE INVESTIMENTO EM COTAS DE FUNDOS DE INVESTIMENTO EM DIREITOS CREDITÓRIOS
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 101
- VOLUME_TOTAL: R$ 209,687,413.52; FLUXO_LIQ: R$ 209,687,413.52; PL final: R$ 161,693,678.24
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 2 (igual)
- Quedas bruscas de PL: 3 (igual)
- Divergências fluxo/retorno: 0 (igual)

### 6. 48.963.233/0001-16
- Denominação: CIB-P FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 553
- VOLUME_TOTAL: R$ 17,461,486.88; FLUXO_LIQ: R$ 17,461,486.88; PL final: R$ 42,265,626.66
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 17 (igual)
- Quedas bruscas de PL: 0 (igual)
- Divergências fluxo/retorno: 1 (**-1**)

### 7. 36.935.858/0001-95
- Denominação: ZEFIROS FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 503
- VOLUME_TOTAL: R$ 20,309,287.27; FLUXO_LIQ: R$ 20,013,145.39; PL final: R$ 21,188,795.59
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 1 (igual)
- Quedas bruscas de PL: 4 (igual)
- Divergências fluxo/retorno: 0 (igual)

### 8. 21.596.695/0001-96
- Denominação: HELVETIA FUNDO DE INVESTIMENTO MULTIMERCADO CRÉDITO PRIVADO
- Situação (cadastro, snapshot 2026-06): LIQUIDAÇÃO
- Dias reportados na janela: 242
- VOLUME_TOTAL: R$ 12,731,002.60; FLUXO_LIQ: R$ -12,731,002.60; PL final: R$ 0.00
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 1 (igual)
- Quedas bruscas de PL: 2 (igual)
- Divergências fluxo/retorno: 0 (igual)

### 9. 46.879.122/0001-09
- Denominação: BOJNICE 421 FUNDO DE INVESTIMENTO IMOBILIÁRIO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 90
- VOLUME_TOTAL: R$ 13,000,000.00; FLUXO_LIQ: R$ 13,000,000.00; PL final: R$ 14,156,726.41
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 1 (igual)
- Quedas bruscas de PL: 0 (igual)
- Divergências fluxo/retorno: 1 (igual)

### 10. 33.521.273/0001-30
- Denominação: FERA12 95 FUNDO DE INVESTIMENTO EM COTAS DE FUNDO DE INVESTIMENTO FINANCEIRO MULTIMERCADO
- Situação (cadastro, snapshot 2026-06): CANCELADA
- Dias reportados na janela: 578
- VOLUME_TOTAL: R$ 10,000,000.00; FLUXO_LIQ: R$ 10,000,000.00; PL final: R$ 822,339,021.84
- Runs de resgate — maior sequência: 0 dias (igual vs arquivo)
- Anomalias de fluxo: 2 (igual)
- Quedas bruscas de PL: 0 (igual)
- Divergências fluxo/retorno: 0 (igual)

## Reprodução

```bash
python -c "from src.collectors.cvm_collector import CVMCollector; \
           CVMCollector().download_period(2024, 1, 2025, 12)"
python scripts/run_investigation.py --informe data/raw/inf_diario_fi_2024*.csv \
    --cadastro data/raw/registro_classe.csv --fund-mode cnpj_list \
    --fund-identifier "$(grep -oE '[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}' \
        docs/TOP10_REAG_LAYER2.md | paste -sd,)" --strict
```

O registro é um snapshot atual e o informe é histórico, então a coluna
*Situação* reflete 2026-06, não a janela analisada.
