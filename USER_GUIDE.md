# REAG Fraud Investigation Toolkit - User Guide

**Version:** 1.0
**Last Updated:** 2026-01-17

Complete guide for investigating investment fraud using the REAG toolkit.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Overview](#system-overview)
3. [Data Collection](#data-collection)
4. [Fraud Detection Workflow](#fraud-detection-workflow)
5. [Advanced Analysis](#advanced-analysis)
6. [Interpreting Results](#interpreting-results)
7. [Case Studies](#case-studies)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import pandas, numpy, yfinance; print('✅ Dependencies OK')"
```

### 5-Minute Demo

```python
# Run the integration test to see the system in action
python tests/test_integration_workflow.py
```

This will:
- Create a realistic fraud scenario (10 fraudulent funds)
- Run all fraud detection analyzers
- Display comprehensive results
- Show what fraud patterns look like

---

## System Overview

### What This Toolkit Does

The REAG Fraud Investigation Toolkit analyzes Brazilian investment funds to detect:

1. **Phantom Assets** - Assets that don't exist or are overvalued
2. **Circular Flow** - Money cycling between related entities (circular-flow pattern)
3. **Ponzi Schemes** - Unrealistic, smoothed returns
4. **Regulatory Violations** - Excessive concentration, compliance issues
5. **Market Manipulation** - Price discrepancies vs real market data

### Architecture

```
REAG Toolkit
│
├── Data Collection (src/collectors/)
│   └── CVM downloader (cadastro, informe, CDA)
│
├── Data Processing (src/processors/)
│   └── Data cleaning and transformation
│
└── Fraud Detection (src/analyzers/)
    ├── Enhanced Phantom Assets
    ├── Fraud Schemes (circular-flow patterns)
    ├── Peer Comparison
    ├── Concentration Analysis
    └── Market Data Validation
```

---

## Data Collection

### Step 1: Download CVM Data

```python
from pathlib import Path
from src.collectors.cvm_collector import CVMCollector

# Initialize collector
collector = CVMCollector(output_dir=Path('data/raw'))

# Download data for specific period
collector.download_period(
    start_year=2024,
    start_month=1,
    end_year=2024,
    end_month=12,
    download_cadastro=True,
    download_informe=True,
    download_cda=True
)
```

**Expected Output:**
```
📥 Downloading: Cadastro
✅ Downloaded: data/raw/registro_classe.csv, registro_fundo.csv

📥 Downloading: Informe Diário (2024-01)
✅ Downloaded: data/raw/informe/inf_diario_fi_202401.csv (45.8 MB)
...
```

### Step 2: Load Data

```python
from src.processors.data_loader import DataLoader

loader = DataLoader(data_dir=Path('data/raw'))

# Load all data
cadastro_df = loader.load_cadastro()
informe_df = loader.load_informe_period(2024, 1, 2024, 12)
cda_df = loader.load_cda_period(2024, 1, 2024, 12)

print(f"✅ Loaded:")
print(f"   Cadastro: {len(cadastro_df):,} funds")
print(f"   Informe: {len(informe_df):,} daily records")
print(f"   CDA: {len(cda_df):,} portfolio positions")
```

---

## Fraud Detection Workflow

### Complete Investigation Example

```python
from pathlib import Path
import pandas as pd

# Assuming you've loaded data (see above)
# Let's investigate funds from administrator CNPJ 11.111.111/0001-01

target_admin = '11.111.111/0001-01'
output_dir = Path('results/investigation_20240117')

print("🔍 Starting fraud investigation...")
print(f"Target: Administrator {target_admin}")
print("="*70)
```

### Analysis 1: Enhanced Phantom Assets Detection

**Purpose:** Identify fictitious or suspicious assets in portfolios

```python
from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector

# Initialize detector
detector = EnhancedPhantomAssetDetector()

# Update registries with known valid assets
detector.update_registries()

# Optional: Load valid funds from CVM cadastro
detector.load_funds_from_cadastro(Path('data/raw/registro_classe.csv'))

# Detect suspicious assets
print("\n🔍 ENHANCED PHANTOM ASSETS DETECTION")
print("-"*70)

results = detector.detect_enhanced_phantom_assets(cda_df)

# Filter by administrator
admin_funds = cadastro_df[cadastro_df['CNPJ_ADMIN'] == target_admin]['CNPJ_FUNDO']
admin_results = results[results['asset_code'].isin(cda_df[cda_df['CNPJ_FUNDO'].isin(admin_funds)]['CD_ATIVO'])]

print(f"\n📊 Results for administrator {target_admin}:")
print(admin_results[['asset_code', 'asset_type', 'status', 'fraud_risk', 'total_value']].to_string(index=False))

# Save results
output_dir.mkdir(parents=True, exist_ok=True)
admin_results.to_csv(output_dir / 'phantom_assets.csv', index=False)
print(f"\n💾 Results saved to: {output_dir / 'phantom_assets.csv'}")
```

**What to look for:**
- `status = 'PHANTOM'` → Asset doesn't exist (CRITICAL)
- `fraud_risk = 'CRITICAL'` or 'HIGH' → Suspicious private asset
- High `total_value` → Larger impact
- Multiple `red_flags` → Systematic fraud

**Example Output:**
```
asset_code     asset_type  status             fraud_risk  total_value
FAKE4          STOCK       PHANTOM            CRITICAL    15000000.00
90.000.001/... FUND        PHANTOM            CRITICAL    25000000.00
DEB_SHELL_2024 DEBENTURE   NEEDS_MANUAL_RE... HIGH        50000000.00
```

### Analysis 2: Fraud Schemes Detection

**Purpose:** Detect specific patterns from documented Brazilian fraud cases

```python
from src.analyzers.fraud_schemes import FraudSchemeDetector

print("\n🚨 FRAUD SCHEMES DETECTION (Circular-Flow Patterns)")
print("-"*70)

scheme_detector = FraudSchemeDetector()

# Run all fraud scheme detections
schemes = scheme_detector.generate_fraud_scheme_report(
    informe_df=informe_df,
    cda_df=cda_df,
    cadastro_df=cadastro_df,
    output_path=output_dir / 'fraud_schemes'
)

# Analyze results
print("\n📊 Detected Schemes:")
for scheme_type, df in schemes.items():
    if not df.empty:
        # Filter by administrator
        if 'admin_cnpj' in df.columns:
            admin_schemes = df[df['admin_cnpj'] == target_admin]
            if not admin_schemes.empty:
                print(f"\n⚠️  {scheme_type.upper()}: {len(admin_schemes)} cases")
                print(admin_schemes.head(3).to_string(index=False))
```

**What to look for:**

1. **Circular Flow** → Funds investing in each other (same admin)
   - High `banco_master_similarity` = Very suspicious
   - Multiple circular connections = Systematic fraud

2. **Layered Funds** → Fund-of-funds amplifying fake valuations
   - High `holder_avg_daily_return` + `held_avg_daily_return` = Inflated returns

3. **Asset Inflation** → Illiquid assets with unrealistic returns
   - `illiquid_pct > 85%` + `avg_daily_return > 0.5%` = Red flag

4. **Shell Networks** → Multiple micro-companies as issuers
   - `num_suspicious_issuers > 20` = Organized fraud network

### Analysis 3: Peer Comparison & Outlier Detection

**Purpose:** Find funds with statistically impossible returns

```python
from src.analyzers.peer_comparison import PeerComparisonAnalyzer

print("\n📊 PEER COMPARISON & OUTLIER DETECTION")
print("-"*70)

peer_analyzer = PeerComparisonAnalyzer()

# Load fund categories
peer_analyzer.load_fund_categories(cadastro_df)

# Calculate metrics for all funds
metrics = peer_analyzer.calculate_fund_metrics(informe_df)

# Get funds from target administrator
target_funds = cadastro_df[cadastro_df['CNPJ_ADMIN'] == target_admin]['CNPJ_FUNDO'].tolist()

# Compare with peers
comparison = peer_analyzer.compare_with_peers(target_funds, metrics)

if not comparison.empty:
    print("\n📈 Peer Comparison Results:")
    print(comparison[['CNPJ_FUNDO', 'fund_return', 'peer_avg_return',
                      'return_zscore', 'is_outlier', 'fraud_flag']].to_string(index=False))

    # Save results
    comparison.to_csv(output_dir / 'peer_comparison.csv', index=False)

    # Highlight outliers
    outliers = comparison[comparison['is_outlier']]
    if not outliers.empty:
        print(f"\n🚨 {len(outliers)} OUTLIER FUNDS DETECTED!")
        print("\nFraud Flags:")
        print(outliers['fraud_flag'].value_counts())

# Detect Ponzi-like smoothed returns
smoothed = peer_analyzer.detect_smoothed_returns(informe_df, target_funds)

if not smoothed.empty:
    print(f"\n⚠️  {len(smoothed)} funds with Ponzi-like smoothed returns")
    print(smoothed[['CNPJ_FUNDO', 'avg_return', 'volatility',
                    'sharpe_ratio', 'positive_days_pct']].head(5).to_string(index=False))
    smoothed.to_csv(output_dir / 'ponzi_detection.csv', index=False)
```

**What to look for:**
- `|return_zscore| > 3` → Outlier (too high or too low)
- `fraud_flag = 'RETURNS_TOO_HIGH'` → Unrealistic gains (Ponzi)
- `fraud_flag = 'HIDDEN_LOSSES'` → Hiding losses
- `sharpe_ratio > 5` → Too good to be true
- `positive_days_pct > 90%` → Artificially smoothed
- `volatility < 0.05` with `avg_return > 0.01` → Ponzi pattern

### Analysis 4: Concentration & Regulatory Compliance

**Purpose:** Detect excessive concentration and regulatory violations

```python
from src.analyzers.concentration import ConcentrationAnalyzer

print("\n📈 CONCENTRATION & REGULATORY ANALYSIS")
print("-"*70)

conc_analyzer = ConcentrationAnalyzer()

# Detect excessive concentration
violations = conc_analyzer.detect_excessive_concentration(cda_df, cadastro_df)

# Filter by administrator
admin_violations = violations[violations['CNPJ_ADMIN'] == target_admin]

if not admin_violations.empty:
    print(f"\n⚠️  {len(admin_violations)} concentration violations found!")
    print("\nTop 5 violations:")
    print(admin_violations.nlargest(5, 'max_single_asset_pct')[
        ['CNPJ_FUNDO', 'hhi', 'max_single_asset_pct', 'max_single_issuer_pct']
    ].to_string(index=False))

    admin_violations.to_csv(output_dir / 'concentration_violations.csv', index=False)
else:
    print("✅ No concentration violations detected")
```

**What to look for:**
- `hhi > 0.25` → Highly concentrated (risky)
- `max_single_asset_pct > 10%` → Regulatory violation
- `max_single_issuer_pct > 20%` → Regulatory violation
- Combined with phantom assets → Concentrated fraud

### Analysis 5: Market Data Validation

**Purpose:** Compare declared prices vs real market prices

```python
from src.analyzers.market_data import MarketDataValidator

print("\n💰 MARKET PRICE VALIDATION")
print("-"*70)

validator = MarketDataValidator()

# Validate prices (sample to avoid rate limiting)
# For production, you might want to validate all positions
admin_cda = cda_df[cda_df['CNPJ_FUNDO'].isin(admin_funds)]

price_validation = validator.validate_portfolio_prices(
    admin_cda,
    sample_size=100  # Adjust based on portfolio size
)

# Detect manipulation
manipulation = validator.detect_price_manipulation(
    price_validation,
    threshold_pct=10.0  # 10% divergence threshold
)

if not manipulation.empty:
    print(f"\n⚠️  {len(manipulation)} price manipulation cases detected!")

    print("\n🔝 Top 5 Overvaluations:")
    overval = manipulation[manipulation['FRAUD_FLAG'] == 'OVERVALUATION'].head(5)
    print(overval[['CD_ATIVO', 'DIVERGENCE_PCT', 'POSITION_VALUE']].to_string(index=False))

    print("\n🔽 Top 5 Undervaluations:")
    underval = manipulation[manipulation['FRAUD_FLAG'] == 'UNDERVALUATION'].head(5)
    print(underval[['CD_ATIVO', 'DIVERGENCE_PCT', 'POSITION_VALUE']].to_string(index=False))

    manipulation.to_csv(output_dir / 'price_manipulation.csv', index=False)
else:
    print("✅ No significant price manipulation detected")
```

**What to look for:**
- `DIVERGENCE_PCT > 20%` → Significant overvaluation/undervaluation
- `FRAUD_FLAG = 'OVERVALUATION'` → Inflating asset values
- High `POSITION_VALUE` → Larger impact on fund NAV
- Pattern across multiple assets → Systematic manipulation

---

## Advanced Analysis

### Multi-Administrator Comparison

Compare fraud indicators across multiple administrators:

```python
# Analyze top 10 administrators by AUM
top_admins = cadastro_df.groupby('CNPJ_ADMIN')['CNPJ_FUNDO'].count().nlargest(10).index

results_summary = []

for admin_cnpj in top_admins:
    admin_funds = cadastro_df[cadastro_df['CNPJ_ADMIN'] == admin_cnpj]['CNPJ_FUNDO']

    # Run all detections (simplified)
    phantom_count = len(detector.detect_enhanced_phantom_assets(
        cda_df[cda_df['CNPJ_FUNDO'].isin(admin_funds)]
    ))

    results_summary.append({
        'admin_cnpj': admin_cnpj,
        'num_funds': len(admin_funds),
        'phantom_assets': phantom_count,
        # Add other metrics...
    })

summary_df = pd.DataFrame(results_summary).sort_values('phantom_assets', ascending=False)
print("\n📊 Administrator Risk Ranking:")
print(summary_df.head(10).to_string(index=False))
```

### Time Series Analysis

Track fraud indicators over time:

```python
# Analyze monthly trends
months = pd.date_range('2024-01-01', '2024-12-31', freq='M')

trends = []
for month_end in months:
    month_cda = cda_df[cda_df['DT_COMPTC'].dt.to_period('M') == month_end.to_period('M')]
    phantom_count = len(detector.detect_enhanced_phantom_assets(month_cda))

    trends.append({
        'month': month_end,
        'phantom_assets': phantom_count,
        # Add other metrics...
    })

trends_df = pd.DataFrame(trends)

# Plot (if matplotlib available)
import matplotlib.pyplot as plt
trends_df.plot(x='month', y='phantom_assets', marker='o')
plt.title('Phantom Assets Over Time')
plt.savefig(output_dir / 'trends.png')
```

---

## Interpreting Results

### Fraud Severity Matrix

| Pattern | Severity | Action Required |
|---------|----------|----------------|
| 10+ Phantom Assets | 🔴 CRITICAL | Immediate investigation, notify CVM |
| 5+ Circular Flow Cases | 🔴 CRITICAL | Circular-flow fraud, freeze assets |
| Z-score > 5 (returns) | 🔴 CRITICAL | Likely Ponzi, stop redemptions |
| 3+ Shell Networks | 🟠 HIGH | Investigate issuer legitimacy |
| HHI > 0.5 + Phantom Assets | 🟠 HIGH | Concentrated fraud risk |
| Price Divergence > 30% | 🟠 HIGH | Systematic price manipulation |
| 1-2 Phantom Assets | 🟡 MEDIUM | Verify individually |
| Z-score 3-5 | 🟡 MEDIUM | Monitor closely |

### Red Flag Combinations

**CRITICAL - Circular-Flow Pattern:**
```
✅ Circular Flow Detected
✅ Shell Company Network
✅ Asset Inflation
✅ High Returns (Z > 3)
→ 95%+ probability of systematic fraud
```

**HIGH - Ponzi Scheme:**
```
✅ Smoothed Returns (volatility < 0.05, return > 1%)
✅ Positive Days > 90%
✅ High Capital Inflows
✅ Sharpe Ratio > 5
→ 80%+ probability of Ponzi
```

**MEDIUM - Data Quality Issues:**
```
❌ No Circular Flow
❌ No Phantom Assets
✅ Missing EMISSOR fields
✅ Unusual concentration
→ Likely data quality issue, not fraud
```

---

## Case Studies

### Case Study 1: Circular flow through shell entities (documented Brazilian case, R$ 11.5 bn)

**What happened:**
- A single administrator managed multiple related funds
- Circular flow: bank → shell companies → affiliated funds → back to the bank
- 36 shell companies participated
- Inflated illiquid asset values

**How this toolkit would detect it:**

1. **Circular Flow Detection** ✅
   ```python
   schemes['circular_flow']
   # Would show: Multiple funds investing in each other
   # banco_master_similarity: VERY_HIGH
   ```

2. **Shell Network Detection** ✅
   ```python
   schemes['shell_networks']
   # Would identify: 36 LTDA ME / EIRELI companies
   # num_suspicious_issuers: 36
   ```

3. **Asset Inflation Detection** ✅
   ```python
   schemes['asset_inflation']
   # Would flag: >85% illiquid with unrealistic returns
   ```

### Case Study 2: Bernie Madoff ($65 billion Ponzi)

**What happened:**
- Consistent positive returns (smooth line)
- Returns independent of market conditions
- Fake trading records

**How this toolkit would detect it:**

1. **Peer Comparison** ✅
   ```python
   comparison[comparison['is_outlier']]
   # return_zscore > 5
   # fraud_flag: RETURNS_TOO_HIGH
   ```

2. **Smoothed Returns** ✅
   ```python
   smoothed_returns
   # volatility: 0.02 (extremely low)
   # positive_days_pct: 95%
   # sharpe_ratio: 8.5 (impossible)
   ```

---

## Troubleshooting

### Common Issues

#### Issue: "Colunas faltando: ['EMISSOR']"

**Cause:** CDA data doesn't have EMISSOR column
**Solution:**
```python
# Check available columns
print(cda_df.columns.tolist())

# If EMISSOR missing, some analyses will skip
# Add dummy column if needed:
if 'EMISSOR' not in cda_df.columns:
    cda_df['EMISSOR'] = 'UNKNOWN'
```

#### Issue: "Nenhum fundo com peers suficientes"

**Cause:** Not enough funds in same category for comparison
**Solution:**
```python
# Check category distribution
print(cadastro_df['CLASSE'].value_counts())

# Need at least 6 funds per category
# If insufficient, compare across all categories:
metrics_all = analyzer.calculate_fund_metrics(informe_df)
```

#### Issue: "⚠️  yfinance não instalado"

**Cause:** Market data validator requires yfinance
**Solution:**
```bash
pip install yfinance
```

#### Issue: Too many API rate limit errors

**Cause:** Yahoo Finance rate limiting
**Solution:**
```python
# Use smaller sample size
validation = validator.validate_portfolio_prices(
    cda_df,
    sample_size=50  # Reduce from default 1000
)

# Or use cached results
validator._load_cache()  # Reuse previous fetches
```

---

## Best Practices

### 1. Start Broad, Then Focus

```python
# Step 1: Run all detections on all funds
all_results = run_all_analyzers(cadastro_df, informe_df, cda_df)

# Step 2: Identify high-risk administrators
risky_admins = identify_risky_admins(all_results)

# Step 3: Deep dive on top 3 riskiest
for admin in risky_admins[:3]:
    detailed_investigation(admin)
```

### 2. Validate Findings

Don't rely on a single indicator:

```python
# Good: Multiple confirmations
if (phantom_count > 5 and
    circular_flow_detected and
    returns_zscore > 3):
    print("🔴 HIGH CONFIDENCE FRAUD")

# Bad: Single indicator
if phantom_count > 0:
    print("FRAUD!")  # Could be data quality issue
```

### 3. Document Everything

```python
# Create investigation report
report = {
    'date': datetime.now(),
    'administrator': target_admin,
    'analyst': 'Your Name',
    'findings': {
        'phantom_assets': len(phantom_results),
        'circular_flow': len(circular_flow),
        'confidence': 'HIGH'
    },
    'recommendation': 'Immediate CVM notification'
}

with open(output_dir / 'investigation_report.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)
```

### 4. Monitor Changes

```python
# Run monthly and compare
current_results = run_analysis(current_month_data)
previous_results = load_results('previous_month')

delta = compare_results(current_results, previous_results)

if delta['phantom_assets'] > 5:
    print("⚠️  ALERT: 5+ new phantom assets detected!")
```

---

## Next Steps

1. **Run Test Suite** - Verify system working
   ```bash
   python tests/test_advanced_analyzers.py
   python tests/test_integration_workflow.py
   ```

2. **Download Real Data** - Get CVM data for investigation period
   ```python
   collector.download_period(2024, 1, 2024, 12, ...)
   ```

3. **Run Investigation** - Follow workflow above

4. **Review Results** - Use interpretation guide

5. **Report Findings** - Document and notify authorities

---

## Support & Resources

- **Documentation:** See `FRAUD_PATTERNS_GUIDE.md` for pattern details
- **Testing:** See `TESTING_RESULTS.md` for validation
- **Code Examples:** Check `notebooks/05_advanced_market_analysis.ipynb`

---

## Appendix: Quick Reference

### Essential Commands

```python
# Complete investigation in one script
from pathlib import Path
from src.analyzers import *

# 1. Load data
loader = DataLoader(Path('data/raw'))
cadastro = loader.load_cadastro()
informe = loader.load_informe_period(2024, 1, 2024, 12)
cda = loader.load_cda_period(2024, 1, 2024, 12)

# 2. Run all analyzers
phantom = EnhancedPhantomAssetDetector().detect_enhanced_phantom_assets(cda)
schemes = FraudSchemeDetector().generate_fraud_scheme_report(informe, cda, cadastro)
peer = PeerComparisonAnalyzer()
peer.load_fund_categories(cadastro)
comparison = peer.compare_with_peers(target_funds, peer.calculate_fund_metrics(informe))

# 3. Review results
print(f"Phantom: {len(phantom)}")
print(f"Schemes: {sum(len(df) for df in schemes.values())}")
print(f"Outliers: {len(comparison[comparison['is_outlier']])}")
```

---

*User Guide v1.0 - 2026-01-17*
