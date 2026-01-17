# Análise Avançada com Dados de Mercado - REAG Investigation

**Data:** 2026-01-17
**Objetivo:** Enriquecer investigação de fraude com dados externos de mercado

---

## 📊 Visão Geral

Atualmente você tem **dados da CVM** (Informe Diário, CDA, Cadastro). Com **dados de mercado externos**, você pode:

1. ✅ **Validar** se os valores declarados são reais
2. 🔍 **Detectar** manipulações que não aparecem em dados isolados
3. 📈 **Comparar** performance real vs declarada
4. 🎯 **Identificar** ativos fictícios ou sobrevalorizados
5. 🌐 **Contextualizar** anomalias com eventos de mercado

---

## 🎯 Top 10 Análises com Dados de Mercado

### 1️⃣ **Validação de Preços de Ativos (Mark-to-Market Verification)**

#### 🎯 Objetivo
Verificar se os preços dos ativos declarados no CDA correspondem aos preços reais de mercado.

#### 📊 Dados Necessários
- **B3 (Bolsa):** Preços diários de ações, ETFs, BDRs
- **ANBIMA:** Preços de títulos públicos e privados (debêntures, CRIs, CRAs)
- **CETIP/B3:** Preços de CDBs, LCIs, LCAs

#### 🔍 Como Fazer

```python
# Pseudo-código
import pandas as pd
import requests

class MarketDataValidator:
    def __init__(self):
        self.b3_prices = self.load_b3_prices()  # Ações, ETFs
        self.anbima_prices = self.load_anbima_prices()  # Bonds

    def validate_portfolio_prices(self, cda_df):
        """
        Compara preços declarados no CDA com preços de mercado

        Red flags:
        - Divergência > 5% do preço de mercado
        - Ativos "ilíquidos" com preços muito otimistas
        - Ativos inexistentes no mercado
        """
        results = []

        for idx, row in cda_df.iterrows():
            ticker = row['CD_ATIVO']
            declared_price = row['VL_MERCADO'] / row['QT_POS']
            date = row['DT_COMPTC']

            # Buscar preço real
            market_price = self.get_market_price(ticker, date)

            if market_price:
                divergence = (declared_price - market_price) / market_price * 100

                if abs(divergence) > 5:
                    results.append({
                        'fund': row['CNPJ_FUNDO'],
                        'asset': ticker,
                        'date': date,
                        'declared_price': declared_price,
                        'market_price': market_price,
                        'divergence_pct': divergence,
                        'fraud_flag': 'OVERVALUATION' if divergence > 0 else 'UNDERVALUATION'
                    })

        return pd.DataFrame(results)

# Uso
validator = MarketDataValidator()
price_anomalies = validator.validate_portfolio_prices(cda_df)

# Fundos com overvaluation suspeito
suspicious = price_anomalies[price_anomalies['divergence_pct'] > 10]
print(f"Ativos sobrevalorizados: {len(suspicious)}")
```

#### 🚨 Red Flags Específicos
- **Overvaluation > 10%:** Ativo declarado muito acima do mercado
- **Ativos sem preço de mercado:** Possível ativo fictício
- **Divergência sistemática:** Sempre otimista = manipulação
- **"Marcação na curva" suspeita:** Títulos privados com preços irreais

#### 💰 Impacto
**CRÍTICO** - Detecção direta de manipulação de patrimônio líquido.

---

### 2️⃣ **Detecção de Ativos Fictícios (Phantom Assets)**

#### 🎯 Objetivo
Identificar ativos que NÃO EXISTEM no mercado mas aparecem no CDA.

#### 📊 Dados Necessários
- **B3:** Lista completa de ativos negociados (ações, debêntures, ETFs)
- **ANBIMA:** Registro de todos os títulos privados
- **CVM:** Registro de emissores

#### 🔍 Como Fazer

```python
class PhantomAssetDetector:
    def __init__(self):
        # Carregar universo de ativos reais
        self.valid_stocks = self.load_b3_universe()
        self.valid_bonds = self.load_anbima_universe()
        self.valid_issuers = self.load_cvm_issuers()

    def find_phantom_assets(self, cda_df):
        """
        Procura ativos que não existem em nenhum registro oficial
        """
        phantom_assets = []

        for asset in cda_df['CD_ATIVO'].unique():
            asset_type = self.classify_asset(asset)

            is_valid = False

            if asset_type == 'STOCK':
                is_valid = asset in self.valid_stocks
            elif asset_type == 'BOND':
                is_valid = self.validate_bond(asset)
            elif asset_type == 'FUND':
                is_valid = self.validate_fund_cnpj(asset)

            if not is_valid:
                # Ativo fantasma!
                holdings = cda_df[cda_df['CD_ATIVO'] == asset]
                phantom_assets.append({
                    'asset': asset,
                    'asset_type': asset_type,
                    'total_value': holdings['VL_MERCADO'].sum(),
                    'funds_holding': holdings['CNPJ_FUNDO'].nunique(),
                    'fraud_severity': 'CRITICAL'
                })

        return pd.DataFrame(phantom_assets)

    def validate_bond(self, bond_code):
        """
        Valida se debênture/CRI/CRA existe

        Verifica:
        - Código na ANBIMA
        - Emissor registrado na CVM
        - Data de emissão coerente
        """
        if bond_code not in self.valid_bonds:
            # Verificar se emissor existe
            issuer = self.extract_issuer(bond_code)
            if issuer not in self.valid_issuers:
                return False  # Emissor fictício!

        return True

# Uso
detector = PhantomAssetDetector()
phantoms = detector.find_phantom_assets(cda_df)

if not phantoms.empty:
    print("⚠️ ATIVOS FICTÍCIOS DETECTADOS!")
    print(phantoms[['asset', 'total_value', 'funds_holding']])
```

#### 🚨 Red Flags
- **Ativo não existe em nenhum registro:** 100% fraude
- **Emissor não registrado na CVM:** Ativo inválido
- **Código de ativo malformado:** Possível inventado
- **Múltiplos fundos com mesmo ativo fictício:** Esquema coordenado

#### 💡 Caso Real: Banco Master
No escândalo do Banco Master, fundos tinham:
- Debêntures de empresas inexistentes
- CDBs de bancos não registrados
- Ativos com códigos inventados

Esta análise teria detectado IMEDIATAMENTE.

---

### 3️⃣ **Análise de Liquidez vs Resgates (Liquidity Mismatch)**

#### 🎯 Objetivo
Detectar fundos que permitem resgates incompatíveis com liquidez dos ativos.

#### 📊 Dados Necessários
- **B3:** Volume diário de negociação de cada ativo
- **ANBIMA:** Liquidez de títulos privados (bid-ask spreads)
- **CDA:** Composição de carteira
- **Informe Diário:** Resgates diários

#### 🔍 Como Fazer

```python
class LiquidityAnalyzer:
    def __init__(self):
        self.trading_volumes = self.load_b3_volumes()  # Volume diário
        self.bid_ask_spreads = self.load_anbima_liquidity()

    def calculate_portfolio_liquidity(self, cda_df, fund_cnpj):
        """
        Calcula quanto tempo levaria para liquidar carteira
        sem impactar preço
        """
        portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]

        liquidity_metrics = []

        for idx, position in portfolio.iterrows():
            ticker = position['CD_ATIVO']
            position_value = position['VL_MERCADO']

            # Volume médio diário
            avg_daily_volume = self.trading_volumes.get(ticker, 0)

            # Assumir que pode vender 10% do volume diário sem impacto
            liquidation_capacity_per_day = avg_daily_volume * 0.10

            # Dias para liquidar posição
            days_to_liquidate = position_value / liquidation_capacity_per_day if liquidation_capacity_per_day > 0 else 999

            liquidity_metrics.append({
                'asset': ticker,
                'position_value': position_value,
                'daily_volume': avg_daily_volume,
                'days_to_liquidate': days_to_liquidate,
                'liquidity_class': self.classify_liquidity(days_to_liquidate)
            })

        return pd.DataFrame(liquidity_metrics)

    def detect_liquidity_fraud(self, informe_df, cda_df):
        """
        Compara resgates permitidos vs liquidez real da carteira

        Red flag: Fundo permite resgate D+0 mas tem ativos ilíquidos
        """
        results = []

        for fund_cnpj in informe_df['CNPJ_FUNDO'].unique():
            # Resgates recentes
            fund_flows = informe_df[informe_df['CNPJ_FUNDO'] == fund_cnpj]
            max_daily_redemption = fund_flows['RESG_DIA'].max()

            # Liquidez da carteira
            liquidity = self.calculate_portfolio_liquidity(cda_df, fund_cnpj)

            # Quanto pode ser liquidado em 1 dia?
            daily_liquidity = liquidity[liquidity['days_to_liquidate'] <= 1]['position_value'].sum()

            # Porcentagem de ativos ilíquidos
            illiquid_pct = liquidity[liquidity['days_to_liquidate'] > 30]['position_value'].sum() / liquidity['position_value'].sum() * 100

            if illiquid_pct > 50 and max_daily_redemption > daily_liquidity:
                results.append({
                    'fund': fund_cnpj,
                    'illiquid_assets_pct': illiquid_pct,
                    'max_redemption': max_daily_redemption,
                    'daily_liquidity': daily_liquidity,
                    'mismatch_ratio': max_daily_redemption / daily_liquidity,
                    'fraud_flag': 'LIQUIDITY_MISMATCH'
                })

        return pd.DataFrame(results)

# Uso
analyzer = LiquidityAnalyzer()
liquidity_frauds = analyzer.detect_liquidity_fraud(informe_df, cda_df)

print(f"Fundos com descasamento de liquidez: {len(liquidity_frauds)}")
```

#### 🚨 Red Flags
- **>50% em ativos ilíquidos** mas permite resgate D+0
- **Resgates > capacidade de liquidação** em 1 semana
- **Fundos de "crédito privado"** com liquidez diária (impossível!)
- **Small caps ilíquidas** em fundos de resgate imediato

#### 💡 Exemplo Real
Fundo declara:
- 70% em debêntures de pequenas empresas (liquidez ~30 dias)
- 20% em CRIs (liquidez ~60 dias)
- 10% em CDI

Mas permite: **Resgate D+0**

**Impossível sem fraude!** Alguém está subsidiando resgates (Ponzi) ou os ativos são fictícios.

---

### 4️⃣ **Performance Attribution Analysis**

#### 🎯 Objetivo
Verificar se o retorno declarado é consistente com a carteira e mercado.

#### 📊 Dados Necessários
- **B3:** Retornos diários de cada ativo
- **ANBIMA:** Retornos de índices (IMA, IDKA, etc.)
- **CDA:** Composição de carteira
- **Informe Diário:** Retorno declarado (variação de cota)

#### 🔍 Como Fazer

```python
class PerformanceAttributor:
    def __init__(self):
        self.asset_returns = self.load_market_returns()
        self.benchmark_returns = self.load_benchmarks()

    def calculate_expected_return(self, cda_df, fund_cnpj, date):
        """
        Calcula retorno esperado baseado na carteira e mercado
        """
        portfolio = cda_df[(cda_df['CNPJ_FUNDO'] == fund_cnpj) &
                          (cda_df['DT_COMPTC'] == date)]

        expected_return = 0
        total_value = portfolio['VL_MERCADO'].sum()

        for idx, position in portfolio.iterrows():
            ticker = position['CD_ATIVO']
            weight = position['VL_MERCADO'] / total_value

            # Retorno do ativo no período
            asset_return = self.asset_returns.get((ticker, date), 0)

            expected_return += weight * asset_return

        return expected_return

    def detect_performance_fabrication(self, informe_df, cda_df):
        """
        Compara retorno declarado vs retorno esperado da carteira

        Red flag: Retorno declarado muito diferente do calculado
        """
        results = []

        for idx, row in informe_df.iterrows():
            fund_cnpj = row['CNPJ_FUNDO']
            date = row['DT_COMPTC']

            # Retorno declarado (variação da cota)
            declared_return = row['RETORNO_DIA']  # % ao dia

            # Retorno esperado (baseado em carteira + mercado)
            expected_return = self.calculate_expected_return(cda_df, fund_cnpj, date)

            # Divergência
            divergence = declared_return - expected_return

            if abs(divergence) > 0.5:  # Divergência > 0.5% ao dia
                results.append({
                    'fund': fund_cnpj,
                    'date': date,
                    'declared_return': declared_return,
                    'expected_return': expected_return,
                    'divergence': divergence,
                    'fraud_flag': 'FABRICATED_RETURN' if divergence > 0 else 'HIDDEN_LOSS'
                })

        return pd.DataFrame(results)

    def detect_smooth_returns(self, informe_df):
        """
        Detecta retornos "suavizados" artificialmente

        Ponzi schemes e fraudes frequentemente mostram:
        - Retornos muito estáveis (baixa volatilidade)
        - Retornos positivos consistentes
        - Sem correlação com mercado
        """
        results = []

        for fund_cnpj in informe_df['CNPJ_FUNDO'].unique():
            fund_returns = informe_df[informe_df['CNPJ_FUNDO'] == fund_cnpj]['RETORNO_DIA']

            # Volatilidade
            volatility = fund_returns.std()

            # % de dias positivos
            positive_days_pct = (fund_returns > 0).sum() / len(fund_returns) * 100

            # Correlação com CDI
            cdi_returns = self.benchmark_returns['CDI']
            correlation = fund_returns.corr(cdi_returns)

            # Sharpe ratio "bom demais"
            sharpe = fund_returns.mean() / volatility if volatility > 0 else 0

            if volatility < 0.01 and positive_days_pct > 95:
                results.append({
                    'fund': fund_cnpj,
                    'volatility': volatility,
                    'positive_days_pct': positive_days_pct,
                    'sharpe_ratio': sharpe,
                    'correlation_cdi': correlation,
                    'fraud_flag': 'SMOOTHED_RETURNS'
                })

        return pd.DataFrame(results)

# Uso
attributor = PerformanceAttributor()

# Fabricação de retornos
fabricated = attributor.detect_performance_fabrication(informe_df, cda_df)
print(f"Casos de fabricação: {len(fabricated)}")

# Retornos suavizados (Ponzi-like)
smoothed = attributor.detect_smooth_returns(informe_df)
print(f"Fundos com retornos suspeitos: {len(smoothed)}")
```

#### 🚨 Red Flags
- **Divergência > 1% ao dia** entre declarado e calculado
- **Volatilidade < 0.01%** (impossível em fundos de renda variável)
- **>95% dias positivos** (característica de Ponzi)
- **Sharpe > 3** sustentado (bom demais para ser verdade)
- **Correlação zero** com ativos que deveria ter

---

### 5️⃣ **Circular Trading Detection (Operações Casadas)**

#### 🎯 Objetivo
Detectar negociações artificiais entre fundos REAG para inflar volumes/preços.

#### 📊 Dados Necessários
- **B3:** Book de ofertas (ordens de compra/venda)
- **B3:** Dados de negociação intraday (comprador/vendedor)
- **CDA:** Movimentações de carteira
- **Cadastro:** Rede de fundos do mesmo administrador

#### 🔍 Como Fazer

```python
class CircularTradingDetector:
    def __init__(self):
        self.trade_data = self.load_b3_trades()  # Negociações detalhadas
        self.reag_funds = self.load_reag_fund_universe()

    def detect_wash_trades(self, trade_data, reag_funds):
        """
        Detecta "wash trading" - compra e venda do mesmo ativo
        entre fundos relacionados

        Padrão suspeito:
        - Fundo A vende ativo X para Fundo B
        - Fundo B vende ativo X de volta para Fundo A
        - Preço inflado artificialmente
        """
        suspicious_pairs = []

        for asset in trade_data['ticker'].unique():
            asset_trades = trade_data[trade_data['ticker'] == asset]

            # Agrupar por dia
            for date in asset_trades['date'].unique():
                daily_trades = asset_trades[asset_trades['date'] == date]

                # Identificar fundos REAG envolvidos
                buyers = daily_trades[daily_trades['side'] == 'BUY']['fund_cnpj']
                sellers = daily_trades[daily_trades['side'] == 'SELL']['fund_cnpj']

                # Fundos REAG comprando e vendendo entre si?
                reag_buyers = set(buyers) & set(self.reag_funds)
                reag_sellers = set(sellers) & set(self.reag_funds)

                if reag_buyers and reag_sellers:
                    # Possível wash trading
                    suspicious_pairs.append({
                        'date': date,
                        'asset': asset,
                        'buyers': list(reag_buyers),
                        'sellers': list(reag_sellers),
                        'volume': daily_trades['volume'].sum(),
                        'avg_price': daily_trades['price'].mean(),
                        'fraud_flag': 'WASH_TRADING'
                    })

        return pd.DataFrame(suspicious_pairs)

    def detect_price_manipulation(self, trade_data, cda_df):
        """
        Detecta manipulação de preço de fechamento

        Padrão:
        - Trade pequeno no final do dia
        - Preço muito acima/abaixo do dia
        - Usado para "marcar" carteira a preço favorável
        """
        manipulation_cases = []

        for asset in trade_data['ticker'].unique():
            asset_trades = trade_data[trade_data['ticker'] == asset]

            for date in asset_trades['date'].unique():
                daily_trades = asset_trades[asset_trades['date'] == date].sort_values('time')

                # Último trade do dia
                last_trade = daily_trades.iloc[-1]

                # Preço médio do dia
                avg_price = daily_trades['price'].mean()

                # Volume do último trade
                last_trade_volume = last_trade['volume']
                total_volume = daily_trades['volume'].sum()

                # Red flags:
                # 1. Último trade é < 1% do volume
                # 2. Preço > 5% diferente da média
                if (last_trade_volume / total_volume < 0.01 and
                    abs(last_trade['price'] - avg_price) / avg_price > 0.05):

                    # Verificar se fundos REAG usam esse preço
                    funds_holding = cda_df[(cda_df['CD_ATIVO'] == asset) &
                                          (cda_df['DT_COMPTC'] == date)]

                    if not funds_holding.empty:
                        manipulation_cases.append({
                            'date': date,
                            'asset': asset,
                            'last_trade_price': last_trade['price'],
                            'avg_daily_price': avg_price,
                            'divergence_pct': (last_trade['price'] - avg_price) / avg_price * 100,
                            'last_trade_volume_pct': last_trade_volume / total_volume * 100,
                            'funds_affected': funds_holding['CNPJ_FUNDO'].tolist(),
                            'fraud_flag': 'MARKING_THE_CLOSE'
                        })

        return pd.DataFrame(manipulation_cases)

# Uso
detector = CircularTradingDetector()

wash_trades = detector.detect_wash_trades(trade_data, reag_funds_list)
print(f"Casos de wash trading: {len(wash_trades)}")

price_manip = detector.detect_price_manipulation(trade_data, cda_df)
print(f"Casos de marking the close: {len(price_manip)}")
```

#### 🚨 Red Flags
- **Mesmo ativo** negociado entre fundos REAG múltiplas vezes
- **Volume pequeno** com preço muito diferente (marcar carteira)
- **Padrão circular:** A→B→C→A em curto período
- **Último trade do dia** sempre favorável aos fundos REAG

---

### 6️⃣ **Evento-Based Analysis (Notícias e Regulação)**

#### 🎯 Objetivo
Correlacionar anomalias com eventos externos (notícias, investigações, crises).

#### 📊 Dados Necessários
- **CVM:** Comunicados, sanções, processos administrativos
- **News APIs:** Notícias sobre REAG, Banco Master
- **Macro data:** Eventos de mercado (crises, mudanças regulatórias)
- **Informe Diário:** Fluxos e resgates

#### 🔍 Como Fazer

```python
class EventAnalyzer:
    def __init__(self):
        self.cvm_sanctions = self.load_cvm_sanctions()
        self.news_data = self.load_news_data()
        self.market_events = self.load_market_events()

    def detect_informed_redemptions(self, informe_df, news_df):
        """
        Detecta resgates que precedem notícias negativas

        Insider trading: Cotistas privilegiados resgatam ANTES
        da notícia ruim se tornar pública
        """
        suspicious_redemptions = []

        for idx, news in news_df.iterrows():
            news_date = news['date']
            sentiment = news['sentiment']  # Positivo/Negativo

            if sentiment == 'NEGATIVE':
                # Olhar resgates nos 30 dias ANTES da notícia
                window_start = news_date - pd.Timedelta(days=30)

                redemptions = informe_df[
                    (informe_df['DT_COMPTC'] >= window_start) &
                    (informe_df['DT_COMPTC'] < news_date) &
                    (informe_df['RESG_DIA'] > 0)
                ]

                # Verificar se houve spike de resgates
                avg_redemption = redemptions['RESG_DIA'].mean()
                peak_redemption = redemptions['RESG_DIA'].max()

                if peak_redemption > avg_redemption * 3:
                    suspicious_redemptions.append({
                        'news_date': news_date,
                        'news_headline': news['headline'],
                        'redemption_spike_date': redemptions.loc[redemptions['RESG_DIA'].idxmax(), 'DT_COMPTC'],
                        'days_before_news': (news_date - redemptions.loc[redemptions['RESG_DIA'].idxmax(), 'DT_COMPTC']).days,
                        'redemption_amount': peak_redemption,
                        'avg_redemption': avg_redemption,
                        'fraud_flag': 'INFORMED_TRADING'
                    })

        return pd.DataFrame(suspicious_redemptions)

    def correlate_sanctions_with_flows(self, informe_df, sanctions_df):
        """
        Verifica se sanções da CVM causaram corrida bancária
        """
        correlations = []

        for idx, sanction in sanctions_df.iterrows():
            sanction_date = sanction['date']
            entity = sanction['entity']

            # 30 dias após sanção
            window_end = sanction_date + pd.Timedelta(days=30)

            flows = informe_df[
                (informe_df['DT_COMPTC'] >= sanction_date) &
                (informe_df['DT_COMPTC'] <= window_end)
            ]

            # Calcular fluxo líquido
            total_redemptions = flows['RESG_DIA'].sum()
            total_subscriptions = flows['CAPTC_DIA'].sum()
            net_flow = total_subscriptions - total_redemptions

            correlations.append({
                'sanction_date': sanction_date,
                'entity': entity,
                'sanction_type': sanction['type'],
                'net_flow_30d': net_flow,
                'total_redemptions': total_redemptions,
                'bank_run': net_flow < -total_subscriptions * 0.5  # Resgate > 50% de captação
            })

        return pd.DataFrame(correlations)

# Uso
analyzer = EventAnalyzer()

# Detectar insider trading
insiders = analyzer.detect_informed_redemptions(informe_df, news_df)
print(f"Casos de possível insider trading: {len(insiders)}")

# Impacto de sanções
sanctions_impact = analyzer.correlate_sanctions_with_flows(informe_df, sanctions_df)
print(sanctions_impact[sanctions_impact['bank_run'] == True])
```

#### 🚨 Red Flags
- **Resgates massivos 1-7 dias antes** de notícia negativa
- **Fluxo positivo durante crise** (todos fogem, mas fundos REAG captam?)
- **Sem reação a sanção CVM** (cotistas não sabem ou não conseguem resgatar?)

---

### 7️⃣ **Peer Comparison & Outlier Detection**

#### 🎯 Objetivo
Comparar fundos REAG com fundos similares (mesma categoria, tamanho).

#### 📊 Dados Necessários
- **CVM:** Dados de TODOS os fundos (não só REAG)
- **ANBIMA:** Classificação de fundos por categoria
- **Informe Diário:** Performance de peers

#### 🔍 Como Fazer

```python
class PeerAnalyzer:
    def __init__(self):
        self.all_funds = self.load_all_funds_data()
        self.fund_categories = self.load_anbima_categories()

    def compare_with_peers(self, reag_funds_df, all_funds_df):
        """
        Compara fundos REAG com peers de mesma categoria

        Red flags:
        - Performance muito melhor que peers (impossível)
        - Volatilidade muito menor (retornos suavizados)
        - Fluxos descorrelacionados (mercado foge, mas REAG capta)
        """
        results = []

        for reag_fund in reag_funds_df['CNPJ_FUNDO'].unique():
            # Categoria do fundo REAG
            category = self.fund_categories.get(reag_fund, 'Unknown')

            # Peers (mesma categoria, tamanho similar)
            peers = all_funds_df[
                (all_funds_df['category'] == category) &
                (all_funds_df['CNPJ_FUNDO'] != reag_fund)
            ]

            # Métricas REAG
            reag_metrics = reag_funds_df[reag_funds_df['CNPJ_FUNDO'] == reag_fund]
            reag_return = reag_metrics['RETORNO_DIA'].mean()
            reag_volatility = reag_metrics['RETORNO_DIA'].std()
            reag_sharpe = reag_return / reag_volatility if reag_volatility > 0 else 0

            # Métricas peers
            peer_return = peers['RETORNO_DIA'].mean()
            peer_volatility = peers['RETORNO_DIA'].std()
            peer_sharpe = peer_return / peer_volatility if peer_volatility > 0 else 0

            # Z-score (distância dos peers)
            return_zscore = (reag_return - peer_return) / peers['RETORNO_DIA'].std() if peers['RETORNO_DIA'].std() > 0 else 0

            if abs(return_zscore) > 3:
                results.append({
                    'fund': reag_fund,
                    'category': category,
                    'reag_return': reag_return,
                    'peer_avg_return': peer_return,
                    'reag_sharpe': reag_sharpe,
                    'peer_avg_sharpe': peer_sharpe,
                    'z_score': return_zscore,
                    'fraud_flag': 'OUTLIER_PERFORMANCE' if return_zscore > 0 else 'HIDDEN_LOSSES'
                })

        return pd.DataFrame(results)

    def detect_category_mismatch(self, cda_df, fund_categories):
        """
        Detecta fundos classificados errado (para enganar investidores)

        Exemplo:
        - Classificado como "Renda Fixa" mas 80% em ações
        - Classificado como "Conservador" mas 100% em CRIs
        """
        mismatches = []

        for fund_cnpj in cda_df['CNPJ_FUNDO'].unique():
            declared_category = fund_categories.get(fund_cnpj, 'Unknown')
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]

            # Classificar ativos
            equity_pct = self.calculate_equity_exposure(portfolio)
            fixed_income_pct = self.calculate_fixed_income_exposure(portfolio)

            # Verificar consistência
            if declared_category == 'Renda Fixa' and equity_pct > 20:
                mismatches.append({
                    'fund': fund_cnpj,
                    'declared_category': declared_category,
                    'actual_equity_pct': equity_pct,
                    'fraud_flag': 'CATEGORY_MISMATCH'
                })

        return pd.DataFrame(mismatches)

# Uso
peer_analyzer = PeerAnalyzer()

outliers = peer_analyzer.compare_with_peers(reag_df, all_funds_df)
print(f"Fundos outliers: {len(outliers)}")

mismatches = peer_analyzer.detect_category_mismatch(cda_df, categories)
print(f"Fundos mal classificados: {len(mismatches)}")
```

#### 🚨 Red Flags
- **Z-score > 3:** Retorno muito acima de peers (impossível sustentar)
- **Sharpe 2x melhor** que categoria (manipulação)
- **Volatilidade 50% menor** que peers (suavização)
- **Classificação errada** para atrair investidores conservadores

---

### 8️⃣ **Concentration & Diversification Analysis**

#### 🎯 Objetivo
Detectar concentração excessiva em poucos ativos (risco ou manipulação).

#### 📊 Dados Necessários
- **CDA:** Composição de carteira
- **B3:** Market cap de ativos
- **Regulação:** Limites de concentração por tipo de fundo

#### 🔍 Como Fazer

```python
class ConcentrationAnalyzer:
    def __init__(self):
        self.concentration_limits = {
            'Renda Fixa': 0.20,  # Max 20% em um emissor
            'Multimercado': 0.25,
            'Ações': 0.30
        }

    def calculate_herfindahl_index(self, portfolio_df):
        """
        Calcula índice Herfindahl-Hirschman (concentração)

        HHI = sum(peso_i^2)
        - HHI próximo de 1 = muito concentrado
        - HHI próximo de 0 = muito diversificado
        """
        total_value = portfolio_df['VL_MERCADO'].sum()
        weights = portfolio_df['VL_MERCADO'] / total_value
        hhi = (weights ** 2).sum()

        return hhi

    def detect_excessive_concentration(self, cda_df, fund_categories):
        """
        Detecta concentração que viola regulação ou é suspeita
        """
        violations = []

        for fund_cnpj in cda_df['CNPJ_FUNDO'].unique():
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]
            category = fund_categories.get(fund_cnpj, 'Unknown')

            total_value = portfolio['VL_MERCADO'].sum()

            # Top 5 posições
            top5 = portfolio.nlargest(5, 'VL_MERCADO')
            top5_concentration = top5['VL_MERCADO'].sum() / total_value

            # Maior posição individual
            max_position = portfolio['VL_MERCADO'].max() / total_value

            # HHI
            hhi = self.calculate_herfindahl_index(portfolio)

            # Limite regulatório
            limit = self.concentration_limits.get(category, 0.25)

            if max_position > limit or top5_concentration > 0.70:
                violations.append({
                    'fund': fund_cnpj,
                    'category': category,
                    'max_position_pct': max_position * 100,
                    'top5_concentration': top5_concentration * 100,
                    'hhi': hhi,
                    'regulatory_limit': limit * 100,
                    'fraud_flag': 'EXCESSIVE_CONCENTRATION'
                })

        return pd.DataFrame(violations)

    def detect_related_party_concentration(self, cda_df, related_issuers):
        """
        Detecta concentração em emissores relacionados ao administrador

        Red flag: 50% da carteira em debêntures de empresas ligadas
        """
        related_concentration = []

        for fund_cnpj in cda_df['CNPJ_FUNDO'].unique():
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]

            # Identificar ativos de partes relacionadas
            related_assets = portfolio[portfolio['EMISSOR'].isin(related_issuers)]

            if not related_assets.empty:
                total_value = portfolio['VL_MERCADO'].sum()
                related_value = related_assets['VL_MERCADO'].sum()
                related_pct = related_value / total_value * 100

                if related_pct > 30:  # Mais de 30% em relacionadas
                    related_concentration.append({
                        'fund': fund_cnpj,
                        'related_party_pct': related_pct,
                        'related_issuers': related_assets['EMISSOR'].unique().tolist(),
                        'fraud_flag': 'RELATED_PARTY_CONCENTRATION'
                    })

        return pd.DataFrame(related_concentration)

# Uso
conc_analyzer = ConcentrationAnalyzer()

violations = conc_analyzer.detect_excessive_concentration(cda_df, categories)
print(f"Violações de concentração: {len(violations)}")

related_party = conc_analyzer.detect_related_party_concentration(cda_df, related_issuers_list)
print(f"Concentração em partes relacionadas: {len(related_party)}")
```

#### 🚨 Red Flags
- **>25% em uma posição:** Risco excessivo ou manipulação
- **HHI > 0.25:** Carteira muito concentrada
- **>50% em empresas relacionadas:** Conflito de interesse
- **"Fundo diversificado"** mas 80% em 3 ativos

---

### 9️⃣ **Tax Loss Harvesting & Timing Irregularities**

#### 🎯 Objetivo
Detectar padrões suspeitos de realização de perdas/ganhos (manipulação fiscal).

#### 📊 Dados Necessários
- **CDA:** Mudanças em carteira mês a mês
- **B3:** Preços históricos
- **Informe Diário:** Performance

#### 🔍 Como Fazer

```python
class TaxAnalyzer:
    def detect_year_end_manipulation(self, cda_df):
        """
        Detecta venda de perdedores em dezembro e recompra em janeiro

        Objetivo: Realizar perda fiscal sem mudar exposição real
        """
        year_end_trades = []

        # Comparar carteira dezembro vs janeiro
        december = cda_df[cda_df['DT_COMPTC'].dt.month == 12]
        january = cda_df[cda_df['DT_COMPTC'].dt.month == 1]

        for fund_cnpj in december['CNPJ_FUNDO'].unique():
            dec_portfolio = set(december[december['CNPJ_FUNDO'] == fund_cnpj]['CD_ATIVO'])
            jan_portfolio = set(january[january['CNPJ_FUNDO'] == fund_cnpj]['CD_ATIVO'])

            # Ativos vendidos em dez e recomprados em jan
            sold_and_rebought = (dec_portfolio - jan_portfolio) & jan_portfolio

            if sold_and_rebought:
                year_end_trades.append({
                    'fund': fund_cnpj,
                    'assets_churned': list(sold_and_rebought),
                    'fraud_flag': 'TAX_LOSS_HARVESTING'
                })

        return pd.DataFrame(year_end_trades)
```

---

### 🔟 **Credit Risk Analysis (Análise de Risco de Crédito)**

#### 🎯 Objetivo
Avaliar qualidade dos emissores de títulos privados em carteira.

#### 📊 Dados Necessários
- **CDA:** Holdings de debêntures, CRIs, CRAs
- **Ratings agencies:** Fitch, Moody's, S&P ratings
- **Financial statements:** Balanços de empresas emissoras
- **CVM:** Defaults históricos

#### 🔍 Como Fazer

```python
class CreditRiskAnalyzer:
    def __init__(self):
        self.ratings_data = self.load_ratings()
        self.default_history = self.load_default_history()

    def assess_portfolio_credit_quality(self, cda_df):
        """
        Avalia qualidade de crédito da carteira

        Red flags:
        - Muitos emissores sem rating
        - Concentração em high-yield (junk bonds)
        - Emissores em default ainda na carteira
        """
        credit_analysis = []

        for fund_cnpj in cda_df['CNPJ_FUNDO'].unique():
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]

            # Filtrar títulos privados
            private_debt = portfolio[portfolio['TIPO_ATIVO'].isin(['Debênture', 'CRI', 'CRA'])]

            if private_debt.empty:
                continue

            total_debt_value = private_debt['VL_MERCADO'].sum()

            # Classificar por rating
            unrated_value = 0
            junk_value = 0
            default_value = 0

            for idx, bond in private_debt.iterrows():
                issuer = bond['EMISSOR']
                value = bond['VL_MERCADO']

                rating = self.ratings_data.get(issuer, 'NR')
                is_default = issuer in self.default_history

                if rating == 'NR':
                    unrated_value += value
                elif rating in ['CCC', 'CC', 'C', 'D']:
                    junk_value += value

                if is_default:
                    default_value += value

            unrated_pct = unrated_value / total_debt_value * 100
            junk_pct = junk_value / total_debt_value * 100
            default_pct = default_value / total_debt_value * 100

            if unrated_pct > 50 or junk_pct > 30 or default_pct > 0:
                credit_analysis.append({
                    'fund': fund_cnpj,
                    'total_private_debt': total_debt_value,
                    'unrated_pct': unrated_pct,
                    'junk_pct': junk_pct,
                    'default_pct': default_pct,
                    'fraud_flag': 'POOR_CREDIT_QUALITY'
                })

        return pd.DataFrame(credit_analysis)

# Uso
credit_analyzer = CreditRiskAnalyzer()
credit_issues = credit_analyzer.assess_portfolio_credit_quality(cda_df)
print(f"Fundos com problemas de crédito: {len(credit_issues)}")
```

#### 🚨 Red Flags
- **>50% sem rating:** Impossível avaliar risco
- **>30% em junk bonds:** "Renda fixa" de altíssimo risco
- **Ativos em default na carteira:** Valor zero mascarado
- **Emissores falidos:** Ativos sem valor real

---

## 📊 Matriz de Priorização

| # | Análise | Dados Necessários | Dificuldade | Impacto | Prioridade |
|---|---------|------------------|------------|---------|------------|
| 1 | Validação de Preços | B3, ANBIMA | Média | 🔴 Muito Alto | 🔴 CRÍTICA |
| 2 | Ativos Fictícios | B3, ANBIMA, CVM | Baixa | 🔴 Muito Alto | 🔴 CRÍTICA |
| 3 | Liquidez vs Resgates | B3 volumes | Média | 🟡 Alto | 🟡 ALTA |
| 4 | Performance Attribution | B3, ANBIMA | Alta | 🟡 Alto | 🟡 ALTA |
| 5 | Circular Trading | B3 intraday | Muito Alta | 🟡 Alto | 🟢 MÉDIA |
| 6 | Event Analysis | News APIs, CVM | Média | 🟡 Médio | 🟢 MÉDIA |
| 7 | Peer Comparison | CVM all funds | Baixa | 🟡 Médio | 🟡 ALTA |
| 8 | Concentration | CDA | Baixa | 🟡 Médio | 🟢 MÉDIA |
| 9 | Tax Irregularities | CDA temporal | Baixa | 🔵 Baixo | 🔵 BAIXA |
| 10 | Credit Risk | Ratings agencies | Alta | 🟡 Médio | 🟢 MÉDIA |

---

## 🎯 Recomendação de Implementação

### Fase 1: Quick Wins (1-2 semanas)
**Implementar análises com dados públicos gratuitos:**

1. ✅ **Ativos Fictícios** (Análise #2)
   - Dados: B3 ticker list (grátis)
   - Implementação: 4 horas
   - Impacto: Detecta fraude direta

2. ✅ **Peer Comparison** (Análise #7)
   - Dados: Já tem (CVM)
   - Implementação: 6 horas
   - Impacto: Identifica outliers

3. ✅ **Concentration Analysis** (Análise #8)
   - Dados: Já tem (CDA)
   - Implementação: 4 horas
   - Impacto: Detecta violações regulatórias

**Total Fase 1:** 14 horas, 3 análises, 0 custo adicional

---

### Fase 2: Alto Impacto (2-4 semanas)
**Análises que requerem dados de mercado:**

4. ✅ **Validação de Preços** (Análise #1)
   - Dados: B3 API (pode ter custo) ou Yahoo Finance (grátis mas limitado)
   - Implementação: 2 semanas
   - Impacto: CRÍTICO - detecta overvaluation

5. ✅ **Liquidez vs Resgates** (Análise #3)
   - Dados: B3 volumes (grátis com delay)
   - Implementação: 1 semana
   - Impacto: Detecta Ponzi schemes

6. ✅ **Event Analysis** (Análise #6)
   - Dados: CVM comunicados (grátis) + Google News API
   - Implementação: 1 semana
   - Impacto: Detecta insider trading

---

### Fase 3: Avançado (1-2 meses)
**Análises sofisticadas:**

7. ✅ **Performance Attribution** (Análise #4)
8. ✅ **Circular Trading** (Análise #5) - requer dados premium
9. ✅ **Credit Risk** (Análise #10)

---

## 📚 Fontes de Dados Recomendadas

### 🆓 Gratuitas

1. **B3 - Bolsa de Valores**
   - URL: http://www.b3.com.br/pt_br/market-data-e-indices/
   - Dados: Cotações (delay 15min), volumes, lista de ativos
   - Formato: CSV, API REST

2. **ANBIMA**
   - URL: https://www.anbima.com.br/
   - Dados: Índices, preços de títulos públicos
   - Formato: Planilhas Excel

3. **Banco Central**
   - URL: https://www3.bcb.gov.br/sgspub/
   - Dados: CDI, Selic, inflação, câmbio
   - API: SGS (Sistema Gerenciador de Séries Temporais)

4. **CVM Dados Abertos**
   - URL: https://dados.cvm.gov.br/
   - Dados: Sanções, processos, comunicados
   - Formato: CSV

5. **Yahoo Finance** (limitado)
   - API: yfinance (Python)
   - Dados: Preços de alguns ativos brasileiros
   - Limitação: Nem todos os tickers disponíveis

### 💰 Pagas (Profissionais)

1. **Bloomberg Terminal** ($$$)
   - Dados completos de mercado
   - Preço: ~$2,000/mês

2. **Refinitiv/Thomson Reuters** ($$$)
   - Dados de mercado + fundamentalistas
   - Preço: ~$1,500/mês

3. **Quantum Axis / Economatica** ($$)
   - Foco em Brasil
   - Preço: ~R$500-2000/mês
   - Dados: Fundamentalistas, cotações, ratings

4. **B3 Market Data Premium** ($$)
   - Dados intraday, book de ofertas
   - Preço: Negociável

---

## 💻 Implementação Prática - Exemplo Completo

### Código Starter: Validação de Preços com Yahoo Finance

```python
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

class MarketDataEnricher:
    """
    Enriquece análise CVM com dados de mercado
    Versão inicial: Yahoo Finance (grátis mas limitado)
    """

    def __init__(self):
        self.price_cache = {}

    def get_b3_price(self, ticker, date):
        """
        Busca preço de ação brasileira no Yahoo Finance

        Ticker B3: PETR4 -> Yahoo: PETR4.SA
        """
        yahoo_ticker = f"{ticker}.SA"

        try:
            stock = yf.Ticker(yahoo_ticker)
            hist = stock.history(start=date, end=date + timedelta(days=1))

            if not hist.empty:
                return hist['Close'].iloc[0]
        except:
            pass

        return None

    def enrich_cda_with_market_prices(self, cda_df):
        """
        Adiciona coluna com preço de mercado real
        """
        cda_enriched = cda_df.copy()
        cda_enriched['MARKET_PRICE'] = None
        cda_enriched['PRICE_DIVERGENCE_PCT'] = None

        for idx, row in cda_enriched.iterrows():
            ticker = row['CD_ATIVO']
            date = row['DT_COMPTC']
            declared_value = row['VL_MERCADO']
            quantity = row['QT_POS']

            # Preço declarado por ação
            declared_price = declared_value / quantity if quantity > 0 else 0

            # Buscar preço real
            market_price = self.get_b3_price(ticker, date)

            if market_price:
                divergence = (declared_price - market_price) / market_price * 100

                cda_enriched.at[idx, 'MARKET_PRICE'] = market_price
                cda_enriched.at[idx, 'PRICE_DIVERGENCE_PCT'] = divergence

        return cda_enriched

    def generate_price_fraud_report(self, cda_enriched):
        """
        Gera relatório de suspeitas de manipulação de preço
        """
        # Filtrar apenas ativos com preço de mercado
        with_prices = cda_enriched.dropna(subset=['MARKET_PRICE'])

        # Suspeitos: divergência > 10%
        suspicious = with_prices[abs(with_prices['PRICE_DIVERGENCE_PCT']) > 10]

        # Agrupar por fundo
        fraud_summary = suspicious.groupby('CNPJ_FUNDO').agg({
            'CD_ATIVO': 'count',
            'PRICE_DIVERGENCE_PCT': 'mean',
            'VL_MERCADO': 'sum'
        }).rename(columns={
            'CD_ATIVO': 'num_suspicious_assets',
            'PRICE_DIVERGENCE_PCT': 'avg_divergence_pct',
            'VL_MERCADO': 'total_suspicious_value'
        })

        return fraud_summary.sort_values('avg_divergence_pct', ascending=False)

# USO
enricher = MarketDataEnricher()

# Enriquecer CDA com preços de mercado
print("Buscando preços de mercado...")
cda_enriched = enricher.enrich_cda_with_market_prices(cda_df)

# Gerar relatório
fraud_report = enricher.generate_price_fraud_report(cda_enriched)

print("\n📊 RELATÓRIO DE MANIPULAÇÃO DE PREÇOS")
print("="*60)
print(fraud_report)

# Salvar
fraud_report.to_csv('reports/price_manipulation_report.csv')
print("\n✅ Relatório salvo em reports/price_manipulation_report.csv")
```

---

## 🎯 Próximos Passos Práticos

### Semana 1: Começar com Dados Gratuitos

```bash
# 1. Instalar bibliotecas
pip install yfinance requests beautifulsoup4

# 2. Criar novo notebook
notebooks/05_market_data_enrichment.ipynb

# 3. Implementar análises básicas:
#    - Peer comparison (dados CVM)
#    - Concentration analysis (dados CDA)
#    - Phantom assets (lista B3)
```

### Semana 2-3: Validação de Preços

```python
# 4. Coletar preços de mercado
#    - Yahoo Finance para ações
#    - ANBIMA para títulos públicos
#    - Scraping B3 para alguns dados

# 5. Cruzar com CDA
#    - Calcular divergências
#    - Gerar alertas
```

### Semana 4: Integração Completa

```python
# 6. Dashboard com market data
#    - Streamlit app
#    - Gráficos interativos
#    - Comparação declarado vs real
```

---

## 📖 Leitura Complementar

### Papers Acadêmicos

1. **"Detecting Asset Price Manipulation"** - Aggarwal & Wu (2006)
2. **"Ponzi Schemes in Financial Markets"** - Artzrouni (2009)
3. **"Mutual Fund Performance Manipulation"** - Carhart et al. (2002)

### Casos Reais de Fraude

1. **Bernie Madoff (2008)**
   - Ponzi scheme de $65 bilhões
   - Retornos consistentes impossíveis
   - Detecção teria sido trivial com performance attribution

2. **Banco Master / REAG (2020)**
   - CDBs de bancos inexistentes
   - Ativos fictícios
   - Overvaluation sistemático

3. **Wirecard (2020)**
   - €1.9 bilhões inexistentes
   - Ativos fantasmas
   - Auditoria falhou

---

## 🎓 Conclusão

### Impacto das Análises com Market Data

| Análise | Sem Market Data | Com Market Data | Ganho |
|---------|----------------|-----------------|-------|
| Detecção de overvaluation | ❌ Impossível | ✅ Direto | ∞ |
| Validação de performance | ⚠️ Limitado | ✅ Completo | 10x |
| Identificação de ativos fictícios | ⚠️ Manual | ✅ Automatizado | 5x |
| Liquidez vs resgates | ❌ Impossível | ✅ Preciso | ∞ |
| Peer comparison | ⚠️ Básico | ✅ Detalhado | 3x |

### Recomendação Final

**Comece com:**
1. ✅ Peer comparison (dados CVM apenas)
2. ✅ Phantom assets (lista B3 grátis)
3. ✅ Concentration analysis

**Depois expanda para:**
4. ✅ Price validation (Yahoo Finance grátis)
5. ✅ Liquidity analysis (B3 volumes)
6. ✅ Event correlation (CVM + news)

**Se budget permitir:**
7. ✅ Premium data (Bloomberg/Refinitiv)
8. ✅ Circular trading detection
9. ✅ Intraday analysis

---

**Com market data, sua investigação passa de "detectar anomalias" para "provar fraude".**

**Próximo passo:** Implementar análise de peer comparison e phantom assets esta semana!

---

**Documento criado por:** Claude Code Ultra Thinking
**Data:** 2026-01-17
**Versão:** 1.0
