# Análise dos resultados (notebooks executados)

**Repositório:** REAG Fraud Investigation Tools

## 1) Objetivo do repositório (em uma frase)
Ferramenta de triagem (“screening”) para identificar, via dados públicos da CVM, padrões e eventos estatisticamente anômalos em fundos ligados à REAG, priorizando sinais consistentes com estresse de liquidez, descontinuidade operacional (liquidação), e possíveis inconsistências entre fluxo, patrimônio e performance.

Baseado no `README.md`, o pipeline operacional é:
1. Coletar dados CVM (Informe Diário + Cadastro + CDA)
2. Identificar fundos administrados/geridos pela REAG
3. Medir fluxos (captação/resgate), PL e retornos
4. Detectar anomalias (outliers de fluxo, quedas bruscas de PL, runs de resgates, divergências fluxo vs performance)

## 2) O que existe de “resultado” rodado agora
Os notebooks já produziram saídas em:
- `data/processed/reag_fund_list.csv`: lista de fundos atribuídos à REAG (por `CNPJ_ADMIN`)
- `data/processed/reag_informe_diario_processed.csv`: série temporal consolidada (fluxo líquido/dia + PL + quota)
- `data/processed/reag_summary_by_fund.csv`: agregados por fundo (somas de captação/resgate/fluxo e PL)
- `reports/*.csv`: listas de eventos/anomalias

Observação importante: os relatórios em `reports/` contêm datas em 2024 e também em 2025 (ex.: 2025-12-31). Isso sugere que a coleta/análise foi feita com janela que inclui 2025 ou com dados mais recentes do que “apenas 2024”. Para interpretação, vale confirmar o período configurado no momento da execução.

## 3) Visão geral quantitativa (screening)
### Universo REAG encontrado
- Fundos na lista processada: **22** (arquivo `data/processed/reag_summary_by_fund.csv`).

### Anomalias de fluxo (Z-score)
- Eventos: **52**
- Fundos impactados: **17**
- Concentração dos eventos (top):
  - `48.963.233/0001-16`: **17** eventos
  - `36.886.028/0001-15`: **12** eventos
  - `32.313.878/0001-73`: **4** eventos
- Intensidade (Z-score de fluxo):
  - máximo observado: **22.38**
  - mediana: **6.76**
  - há eventos negativos relevantes (mínimo **-15.49**)

Interpretação: Z-scores tão altos normalmente indicam dias “fora de escala” para aquele fundo (captação/resgate muito acima do padrão histórico do próprio fundo). Isso é útil para triagem, mas precisa de leitura contextual (ex.: início/encerramento de fundo, migração de cotistas, eventos corporativos).

### Quedas bruscas de PL
- Eventos: **56**
- Fundos impactados: **13**
- Concentração dos eventos (top):
  - `42.584.801/0001-91`: **17** eventos
  - `51.079.517/0001-59`: **8** eventos
  - `32.313.878/0001-73`: **8** eventos
- Magnitude (`PL_VAR_PCT`):
  - mínimo: **-385%**
  - mediana: **-50.75%**
  - p90 ~ **-21%** (o arquivo parece conter apenas quedas abaixo do threshold, então percentis ficam todos “perto do corte”)

Interpretação: quedas inferiores a -100% (e PL negativo em alguns registros do CSV) são fortes sinais de **problema de dados/qualidade** (ex.: base com PL anterior muito pequeno, registros zerados em liquidação, ou erros/ajustes contábeis extremos). Ainda assim, mesmo como “dado sujo”, esses pontos marcam datas para investigação: geralmente são dias de transição operacional (liquidação/cancelamento, eventos extraordinários) ou inconsistências que merecem reconciliação.

### Runs de resgates (sequências)
- Runs detectadas: **7**
- Fundos com runs: **2**
- Destaque absoluto:
  - `41.751.844/0001-51` com sequências de **134 dias** (resgates acumulados **-R$ 5,72 bi**) e **125 dias** (**-R$ 5,33 bi**)

Interpretação: “runs” longas e bilionárias apontam para **estresse de liquidez/saída coordenada** ou **processo prolongado de desmonte/encerramento**. Quando isso coincide com PL final próximo de zero (ver sumário abaixo), o cenário de liquidação/descontinuidade fica mais plausível.

### Divergências fluxo vs performance
- Eventos: **10**
- Fundos impactados: **6**
- Top evento (por `DIVERGENCE_SCORE`):
  - `48.963.233/0001-16` em 2024-12-11: fluxo **+655k** com retorno **-1,67%** (score **30,99**)

Interpretação: divergência alta tipicamente sinaliza dias em que o fundo recebe entradas em dia muito ruim (ou tem saídas em dia muito bom). Isso pode ser normal (aportes “programados”, cotistas institucionais, cotização D+N), mas também é um bom detector de eventos “estranhos” para priorizar leitura.

## 4) “Quem” são os fundos críticos (triagem por intensidade)
Usando `data/processed/reag_summary_by_fund.csv` como agregação, os maiores por volume (captação + resgates) e por fluxo líquido absoluto são:

### Maiores por volume total
1. `41.751.844/0001-51`: volume ~ **R$ 14,58 bi**, fluxo líquido ~ **-R$ 14,55 bi**, **PL ~ 0**
2. `36.886.028/0001-15`: volume ~ **R$ 5,22 bi**, fluxo líquido ~ **+R$ 5,11 bi**, PL ~ **R$ 7,54 bi**
3. `32.313.878/0001-73`: volume ~ **R$ 2,88 bi**, fluxo líquido ~ **+R$ 0,70 bi**, PL ~ **R$ 0,10 bi**
4. `45.616.130/0001-91`: volume ~ **R$ 1,013 bi**, fluxo líquido ~ **+R$ 1,013 bi**, PL ~ **R$ 1,10 bi**
5. `36.896.886/0001-40`: volume ~ **R$ 0,21 bi**, fluxo líquido ~ **+R$ 0,21 bi**, PL ~ **R$ 0,16 bi**

Leituras iniciais:
- **`41.751.844/0001-51`** combina: volume extremo, **fluxo líquido fortemente negativo** e **PL final ~0**, além das maiores “runs” de resgate. Isso é o candidato #1 para narrativa de “desmonte/encerramento/saída em massa”.
- **`36.886.028/0001-15`** concentra muitos eventos de anomalia de fluxo (12) e grande captação líquida. Pode ser fundo “recebedor” (migração de recursos) ou com fluxo irregular.
- **`48.963.233/0001-16`** é o fundo com mais outliers de fluxo (17) e também aparece na divergência mais alta (2024-12-11). Prioridade #2 para leitura detalhada de calendário de aportes/resgates.

## 5) Pontos de atenção de qualidade/consistência dos dados
Antes de inferir “fraude”, os outputs sugerem alguns itens para checagem:
- **PL negativo / variação < -100%** em `reports/quedas_pl.csv`: isso quase sempre indica efeitos de divisão por base muito pequena, registros zerados/ajustes, ou problemas de parsing/normalização.
- **Duplicidade**: em `reports/anomalias_fluxo.csv` há pelo menos um evento duplicado idêntico (ex.: `33.521.273/0001-30` em 2024-04-02 aparece repetido). Vale deduplicar por (CNPJ, data) antes de contar eventos.
- **Janelas temporais**: existem registros em 2025 nos relatórios. Se a intenção era “últimos 12 meses” em uma data específica, vale congelar/registrar a janela para reprodutibilidade.

## 6) Interpretação investigativa (o que esses sinais podem significar)
### Cenário A — “Estresse de liquidez e encerramento”
Sinais compatíveis:
- Runs longas de resgate (dias consecutivos) + grande volume total
- PL convergindo para 0
- Quedas bruscas de PL em datas-chave

O caso `41.751.844/0001-51` é o exemplo mais forte.

### Cenário B — “Migração/realocação coordenada”
Sinais compatíveis:
- Muitos outliers de captação (z-score alto) em poucos fundos
- Ao mesmo tempo, fundos com outliers negativos (resgates) e quedas de PL

`48.963.233/0001-16` e `36.886.028/0001-15` aparecem como possíveis “pólos” de fluxo.

### Cenário C — “Inconsistência fluxo vs retorno”
Sinais compatíveis:
- `DIVERGENCE_SCORE` alto repetido
- Entradas em dias muito ruins (ou saídas em dias muito bons)

Sozinho, isso não prova irregularidade; mas define datas para cruzar com:
- eventos de cota (cotização D+),
- fatos relevantes,
- mudanças de administrador/gestor,
- alterações na carteira (via CDA).

## 7) Próximas análises recomendadas (com base no que já saiu)
1. **Enriquecer com nomes/classes**: fazer join de CNPJ → denominação/situação/classe (de `reag_fund_list.csv`) para transformar a análise em algo legível para stakeholders.
2. **Linha do tempo por fundo (top 3)**: gerar para `41.751.844/0001-51`, `48.963.233/0001-16`, `36.886.028/0001-15`:
   - PL, captação, resgate, fluxo líquido, retorno diário
   - marcar (pontos) datas com anomalia/run/quebra de PL/divergência
3. **Checagem de consistência contábil**: em datas com PL “bizarro”, verificar se:
   - PL anterior era ~0 (efeito de base)
   - houve liquidação/cancelamento (campo SIT no cadastro)
4. **Cruzamento com CDA (carteira)**: para eventos de resgate/queda de PL, verificar se a carteira era ilíquida/concentrada (indicativo de fragilidade de liquidez e/ou marcação agressiva).

---

## Referências diretas de arquivos
- `README.md`
- `data/processed/reag_summary_by_fund.csv`
- `reports/anomalias_fluxo.csv`
- `reports/quedas_pl.csv`
- `reports/runs_resgate.csv`
- `reports/divergencias_flow_performance.csv`
