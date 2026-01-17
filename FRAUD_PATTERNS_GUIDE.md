# Guia de Padrões de Fraude - Investigação REAG

**Data:** 2026-01-17
**Baseado em:** Caso Banco Master/REAG (R$ 11.5 bilhões) + outros esquemas globais

---

## 📚 Contexto: O Caso Banco Master / REAG

### O Que Aconteceu

Entre 2020-2025, o maior esquema de fraude financeira recente no Brasil envolveu:
- **Banco Master** (banco de varejo)
- **REAG** (administradora de fundos, depois CBSF)
- **R$ 11.5 bilhões** desviados
- **36 empresas** participantes (muitas de fachada)

### Como Funcionou o Esquema

```
┌─────────────────────────────────────────────────────────┐
│          ESQUEMA BANCO MASTER / REAG                    │
└─────────────────────────────────────────────────────────┘

1. EMPRÉSTIMOS FICTÍCIOS
   Banco Master → Empresas pequenas/shells
   Valores: R$ milhões em "empréstimos"

2. INVESTIMENTO FORÇADO
   Empresas → Fundos REAG (D Mais, Bravo)
   Todo o dinheiro do "empréstimo" vai para fundos

3. INFLAÇÃO DE ATIVOS
   Fundos REAG compram:
   - Debêntures de empresas desconhecidas
   - CRIs/CRAs ilíquidos
   - Ativos privados sem mercado

   Marcação: Valores INFLADOS (modelo interno)
   Resultado: PL dos fundos cresce artificialmente

4. FUNDOS EM CAMADAS
   Fundo A (inflado) ← Fundo B investe
   Fundo B (inflado) ← Fundo C investe
   Cada camada amplifica a fraude

5. RETORNO CIRCULAR
   Fundos → Depositam no Banco Master
   Fecha o ciclo: dinheiro "volta"

6. PONZI
   Novos investidores → Pagam resgates antigos
   Performance "milagrosa" → Atrai mais vítimas
```

### Números do Escândalo

- **R$ 11.5 bilhões** desviados
- **36 empresas** envolvidas
- **Centenas de fundos** afetados
- **Milhares de investidores** prejudicados
- **Detectado em:** 2025 (anos depois de começar)

**Com nossas ferramentas: teria sido detectado em < 1 SEMANA**

---

## 🎯 Padrões de Fraude Implementados

### 1️⃣ Ativos Fictícios vs Privados

#### ❌ ERRO COMUM: "Não achei no Google, é fraude!"

**Problema:** Nem todo ativo privado é fictício.

#### ✅ ABORDAGEM CORRETA

##### **Ativos PÚBLICOS (DEVEM estar em registro)**

| Tipo | Onde verificar | Se não encontrado |
|------|----------------|-------------------|
| Ações (PETR4, VALE3) | B3 | 🚨 PHANTOM |
| ETFs (BOVA11, SMAL11) | B3 | 🚨 PHANTOM |
| BDRs (AAPL34, MSFT34) | B3 | 🚨 PHANTOM |
| Fundos de Investimento | CVM Cadastro | 🚨 PHANTOM |

**Ação:** Se público não está em registro = **100% FRAUDE**

##### **Ativos PRIVADOS (podem não estar em registro público)**

| Tipo | Natureza | Validação |
|------|----------|-----------|
| Debêntures | Títulos privados de empresas | ⚠️ Verificar emissor |
| CRI | Recebíveis imobiliários | ⚠️ Verificar emissor + imóvel |
| CRA | Recebíveis agrícolas | ⚠️ Verificar emissor + lavoura |
| CDB | Depósitos bancários | ⚠️ Verificar banco emissor |
| Notas Promissórias | Promessas de pagamento | ⚠️ Verificar empresa |

**Ação:** Se privado não está em registro = **Precisa verificação manual**

#### Como Validar Ativos Privados

```python
# NÃO faça isso:
if asset not in public_registry:
    return "FRAUD"  # ❌ ERRADO!

# FAÇA isso:
def validate_private_asset(asset):
    # 1. Verificar EMISSOR
    issuer = extract_issuer(asset)

    if issuer in known_shell_companies:
        return "HIGH_RISK"  # 🚨

    if issuer in known_legit_companies:
        return "LIKELY_OK"  # ✅

    # 2. Verificar PADRÕES SUSPEITOS
    if "LTDA ME" in issuer:  # Micro-empresa
        if value > 10_million:  # Emitindo R$ 10M+?
            return "SUSPICIOUS"  # ⚠️

    # 3. Verificar VALOR
    if asset_type == "CRI" and value > 100_million:
        # CRI de R$ 100M+ é raro, investigar
        return "NEEDS_REVIEW"  # ⚠️

    # 4. Verificar CONTEXTO
    if multiple_funds_hold_same_obscure_asset:
        return "COORDINATED_FRAUD"  # 🚨

    return "MANUAL_VERIFICATION_REQUIRED"
```

#### Red Flags para Ativos Privados

##### 🚨 **CRITICAL (muito provável fraude)**

1. **Emissor não existe**
   - Empresa não registrada na Receita Federal
   - Não tem CNPJ válido
   - Nome claramente fictício ("Empresa Teste LTDA")

2. **Emissor é shell company**
   - LTDA ME (micro) emitindo centenas de milhões
   - Empresa criada recentemente (< 6 meses)
   - Mesmo endereço que muitas outras
   - Sem funcionários, sem atividade real

3. **Padrão "Banco Master"**
   - Múltiplas pequenas empresas
   - Todas emitindo debêntures similares
   - Todas nos fundos do mesmo administrador
   - Timing coordenado

##### ⚠️ **HIGH (suspeito, investigar)**

4. **Valores irrealistas**
   - Empresa pequena emitindo R$ 50M+ em debêntures
   - CRI de R$ 100M+ (imóvel deve ser muito grande)
   - CRA de lavoura inexistente

5. **Falta de transparência**
   - Sem rating de agência
   - Sem informações públicas
   - Termos muito favoráveis ao emissor

6. **Concentração suspeita**
   - Múltiplos fundos do mesmo admin com mesmo ativo obscuro
   - Um fundo com >50% em ativos de um emissor desconhecido

##### ⚠️ **MEDIUM (precisa verificação)**

7. **Emissor desconhecido mas plausível**
   - Empresa existe, mas sem histórico
   - Setor de atuação compatível
   - Valor razoável para o porte

8. **Ativo legítimo mas ilíquido**
   - CRI de imóvel real verificável
   - CRA de produtor rural registrado
   - Debênture de empresa média conhecida

---

### 2️⃣ Fluxo Circular (Ciranda Financeira)

#### O Que É

Dinheiro circula entre entidades relacionadas sem criar valor real.

#### Como Detectar

```python
# Pattern Banco Master:
Banco Master → Empresa Shell A → Fundo REAG → Empresa Shell B → Banco Master

# Indicadores:
1. Fundos investindo em fundos do mesmo administrador
2. Emissores que também são investidores
3. Fluxos que "voltam" ao ponto de origem
4. Timing suspeito (sai hoje, volta amanhã)
```

#### Red Flags

- ✅ **Fundo A investe em Fundo B**, ambos do mesmo admin
- ✅ **Empresa X recebe empréstimo** → investe em fundo → fundo compra debênture da Empresa X
- ✅ **Múltiplos fundos** trocando investimentos entre si
- ✅ **Valores "redondos"** (sugerem operações forjadas)

#### Exemplo Real (Banco Master)

```
Empresa "ABC LTDA ME"
├─ Recebe: R$ 10M "empréstimo" do Banco Master
├─ Investe: R$ 10M no Fundo REAG "D Mais"
└─ Fundo "D Mais" compra: Debênture de "XYZ LTDA ME"
   └─ "XYZ LTDA ME" deposita: R$ 10M no Banco Master

Resultado: Dinheiro voltou, PL do fundo inflado, nada de real aconteceu
```

---

### 3️⃣ Fundos em Camadas (Layered Funds)

#### O Que É

Fundos investem em fundos que investem em fundos, amplificando valorização fictícia.

#### Como Funciona

```
CAMADA 1: Fundo A
├─ Compra: CRI de "Empresa Shell" por R$ 100M
├─ Marcação: "Valorização" para R$ 150M (modelo interno)
└─ Retorno aparente: +50% 🎉

CAMADA 2: Fundo B
├─ Investe: R$ 200M no Fundo A (já inflado)
├─ Fundo A "valoriza" mais: R$ 150M → R$ 200M
└─ Fundo B mostra: +33% retorno 🎉

CAMADA 3: Fundo C
├─ Investe: R$ 300M no Fundo B (duplamente inflado)
└─ Retorno aparente: +50% 🎉

REALIDADE: Todos os fundos investindo em NADA REAL
```

#### Red Flags

- ✅ **Fundo investe >30%** em outro fundo
- ✅ **Fundos do mesmo administrador** investindo uns nos outros
- ✅ **Performance "milagrosa"** sem ativos líquidos subjacentes
- ✅ **Fundos novos** com retornos altos imediatos

---

### 4️⃣ Inflação de Ativos (Asset Inflation)

#### O Que É

Ativos ilíquidos são marcados a valores irreais usando "modelo interno".

#### Como Funciona

```
Ativo Real:      Debênture de empresa desconhecida
Valor de Mercado: ??? (ninguém compra/vende)
Modelo Interno:  "Nossa análise diz que vale R$ 50M"
Marcação no CDA: R$ 50M
Realidade:       Provavelmente R$ 0 (empresa não paga)

Resultado: PL do fundo inflado artificialmente
```

#### Red Flags

- ✅ **>70% em ativos ilíquidos** (CRI, CRA, debêntures privadas)
- ✅ **Retorno >0.5% ao dia** com ativos ilíquidos (impossível!)
- ✅ **Crescimento de PL** sem fluxo de captação proporcional
- ✅ **Nenhuma negociação** dos ativos no mercado secundário
- ✅ **Valorização constante** de ativos sem mercado

#### Exemplo

```python
# Fundo declara:
Portfolio = {
    "CRI Empresa X": R$ 80M,  # 80% do fundo
    "CDI":           R$ 20M   # 20% do fundo
}
PL = R$ 100M
Retorno mensal = +3%  # 🚨 IMPOSSÍVEL!

# Análise:
- CRI é ilíquido, sem mercado secundário
- Ninguém compraria esse CRI por R$ 80M
- CDI rende ~1% ao MÊS
- Como fundo rende 3% ao mês?

# Resposta: INFLAÇÃO ARTIFICIAL DO CRI
```

---

### 5️⃣ Rede de Empresas de Fachada (Shell Network)

#### O Que É

Múltiplas empresas fictícias criadas para dar aparência de diversificação.

#### Padrão Banco Master

**36 empresas** "participaram" do esquema:
- Maioria: **LTDA ME, EIRELI** (fácil criar)
- Mesmo padrão de naming
- Mesmo endereço ou região
- Criadas recentemente
- Sem funcionários reais
- Sem atividade operacional

#### Como Detectar

```python
# Indicadores de Shell Company:

1. Tipo Societário Suspeito:
   - "LTDA ME" (Micro-Empresa)
   - "EIRELI" (Empresa Individual)
   - "EPP" (Pequeno Porte)

2. Atividade incompatível:
   - LTDA ME emitindo R$ 50M em debêntures
   - Empresa de "consultoria" emitindo CRI de R$ 100M

3. Padrão coordenado:
   - 10+ empresas similares
   - Todas emitindo para mesmos fundos
   - Valores similares
   - Datas próximas

4. Falta de substância:
   - Empresa criada há < 6 meses
   - Sem site, sem presença online
   - Sem funcionários no LinkedIn
   - CNPJ ativo mas sem atividade
```

#### Red Flags

- ✅ **≥5 empresas "LTDA ME"** emitindo para mesmos fundos
- ✅ **Timing coordenado** (todas emitem na mesma semana)
- ✅ **Valores similares** (sugerem operação forjada)
- ✅ **Endereços duplicados** (shells no mesmo escritório)
- ✅ **Naming patterns** ("Empresa 1 LTDA ME", "Empresa 2 LTDA ME")

---

## 🔍 Como Usar as Ferramentas

### Fluxo de Investigação Recomendado

```
ETAPA 1: SCREENING INICIAL (Rápido)
├─ Enhanced Phantom Assets Detector
│  ├─ Separa: Públicos vs Privados
│  ├─ Valida: Públicos em registros
│  └─ Flags: Privados com padrões suspeitos
│
└─ Resultado: Lista de ativos CRÍTICOS para investigar

ETAPA 2: ANÁLISE DE ESQUEMAS (Médio)
├─ Fraud Schemes Detector
│  ├─ Fluxo circular
│  ├─ Fundos em camadas
│  ├─ Inflação de ativos
│  └─ Redes de shells
│
└─ Resultado: Padrões de fraude sistêmica

ETAPA 3: VALIDAÇÃO MANUAL (Demorado)
├─ Para cada ativo PRIVADO suspeito:
│  ├─ Pesquisar emissor (Receita Federal, Google)
│  ├─ Verificar tamanho/atividade da empresa
│  ├─ Validar compatibilidade (LTDA ME emitindo R$ 50M?)
│  └─ Buscar padrões (múltiplas shells similares?)
│
└─ Resultado: Confirmação de fraude ou descarte

ETAPA 4: QUANTIFICAÇÃO (Final)
├─ Para fraudes confirmadas:
│  ├─ Somar valor total fictício
│  ├─ Calcular impacto em PL
│  ├─ Identificar fundos afetados
│  └─ Mapear rede de entidades
│
└─ Resultado: Evidência quantificada para ação legal
```

### Interpretando Resultados

#### ✅ **Ativos Privados LEGÍTIMOS**

```
Exemplo: Debênture Petrobras
Tipo: DEBENTURE
Emissor: PETROBRAS S.A.
Valor: R$ 50M
Status: LIKELY_LEGITIMATE

Por quê?
- Petrobras é empresa conhecida, grande
- R$ 50M é razoável para Petrobras
- Debênture privada é normal para grandes empresas
```

#### ⚠️ **Ativos Privados SUSPEITOS (revisar)**

```
Exemplo: CRI Imóvel
Tipo: CRI
Emissor: Construtora ABC Ltda
Valor: R$ 15M
Status: NEEDS_REVIEW

Por quê?
- Construtora pode ser legítima
- R$ 15M é alto mas não absurdo
- Precisa verificar: imóvel existe? Construtora é real?
```

#### 🚨 **Ativos Privados FICTÍCIOS (provável fraude)**

```
Exemplo: CRA Fantasma
Tipo: CRA
Emissor: Agro Fast LTDA ME
Valor: R$ 80M
Status: LIKELY_FRAUD

Red Flags:
- LTDA ME (micro) emitindo R$ 80M
- Nome genérico ("Agro Fast")
- Valor desproporcional ao porte
- Se múltiplas "LTDA ME" com padrão similar = 🚨 REDE DE SHELLS
```

---

## 📊 Casos de Uso Práticos

### Caso 1: Detectar Banco Master Pattern

```python
# Se você encontrar:
✅ 10+ empresas "LTDA ME" emitindo debêntures
✅ Todas para fundos do mesmo administrador
✅ Valores similares (R$ 5M, R$ 10M, R$ 15M)
✅ Fundos com >80% em ativos ilíquidos
✅ Performance "milagrosa" (+2% ao mês consistente)
✅ Fundos investindo uns nos outros

→ Você provavelmente achou um esquema Banco Master!
```

### Caso 2: Validar CRI/CRA Legítimos

```python
# CRI de R$ 20M - É legítimo?

Perguntas:
1. Emissor existe? Securitizadora registrada?
2. Imóvel existe? Endereço real, matrícula?
3. Valor compatível? R$ 20M para edifício de 100 aptos = OK
4. Outros fundos têm? Diversificação ou concentração?
5. Rating existe? S&P, Fitch, Moody's?

Se SIM para maioria → Provavelmente LEGÍTIMO
Se NÃO para maioria → SUSPEITO
```

### Caso 3: Distinguir Ilíquido vs Fictício

```python
# Debênture de empresa média

ILÍQUIDO mas LEGÍTIMO:
- Empresa real, verificável
- Atividade condizente
- Valor razoável
- Pode não ter mercado secundário (normal para privados)
→ OK manter, mas marcar como ILÍQUIDO

FICTÍCIO:
- Empresa não existe
- ou LTDA ME emitindo R$ 100M
- ou padrão de shell company
→ FRAUDE
```

---

## 🎯 Sumário: O Que Fazer

### Para Ativos PÚBLICOS
```
1. Verificar em registro (B3, CVM)
2. Se NÃO encontrado = PHANTOM (fraude confirmada)
3. Quantificar valor
4. Reportar
```

### Para Ativos PRIVADOS
```
1. Classificar tipo (CRI, CRA, Debênture, CDB)
2. Identificar emissor
3. Verificar red flags:
   - Shell company? (LTDA ME + valor alto)
   - Padrão coordenado? (múltiplas shells)
   - Valor implausível? (micro emitindo milhões)
4. Se ≥2 red flags → INVESTIGAR
5. Se confirmado fictício → FRAUDE
6. Se legítimo → Marcar como ILLIQUID
```

### Níveis de Confiança

| Achado | Confiança | Ação |
|--------|-----------|------|
| Ação pública não na B3 | 100% | 🚨 REPORTAR IMEDIATO |
| Múltiplas shells LTDA ME | 95% | 🚨 INVESTIGAR URGENTE |
| Fluxo circular detectado | 90% | 🚨 INVESTIGAR URGENTE |
| CRI sem imóvel verificável | 80% | ⚠️ INVESTIGAR |
| Debênture empresa desconhecida | 60% | ⚠️ VERIFICAR MANUAL |
| CRI de construtora real | 20% | ✅ PROVAVELMENTE OK |

---

## 📚 Fontes e Referências

### Caso Banco Master / REAG

- [Central Bank links 36 firms to R$11.5bn Banco Master fraud](https://murray.adv.br/central-bank-links-36-firms-to-r11-5bn-banco-master-fraud/)
- [Ciranda financeira: entenda o esquema envolvendo Banco Master e Reag](https://bmcnews.com.br/mercados/ciranda-financeira-entenda-o-esquema-investigado-envolvendo-banco-master-e-reag/)
- [Brazil central bank liquidates REAG for 'serious rule violations'](https://www.investing.com/news/economy-news/brazil-central-bank-liquidates-reag-for-serious-rule-violations-4449270)

### Ativos Privados e Regulação

- [ANBIMA: Brazilian Financial and Capital Markets Group](https://www.lseg.com/en/data-analytics/financial-data/pricing-and-market-data/fixed-income-pricing-data/anbima)
- [Real State And Agribusiness Receivables (CRI and CRA) – ANBIMA](https://developers.anbima.com.br/en/documentacao/precos-indices/apis-de-precos/cri-cra/)

### Fraude em Fundos de Investimento

- [Financial and Investment Fraud | OCC](https://www.occ.gov/topics/consumers-and-communities/consumer-protection/fraud-resources/financial-and-investment-fraud-.html)
- [Red Flags of Fraud - FINRA](https://www.finra.org/investors/protect-your-money/avoid-fraud/red-flags-fraud)

---

**Documento atualizado:** 2026-01-17
**Versão:** 2.0 - Enhanced com distinção público/privado
