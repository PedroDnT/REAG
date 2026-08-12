# Fund Selection Guide

## Overview

The Brazilian Fund Fraud Investigation Tools now support flexible fund selection, allowing you to investigate any fund, administrator, manager, or custom fund list - not just REAG-specific funds.

## Quick Start

### Interactive Mode (Recommended)

The easiest way to start an investigation is using the interactive terminal interface:

```bash
python scripts/investigation_tui.py
```

The wizard will guide you through:
1. Investigation focus selection (flows, portfolio, networks, full)
2. Fund selection (by name, CNPJ, administrator, manager)
3. Pipeline execution
4. Report generation

### Configuration File Mode

For repeatable investigations, configure your selection in `config/settings.py`:

```python
# Fund selection mode
TARGET_FUND_MODE = "administrator"  # or "manager", "fund_list", "all", "legacy_reag"

# Target identifier (administrator/manager name)
TARGET_IDENTIFIER = "XYZ DTVM"

# Investigation name for reports
INVESTIGATION_NAME = "XYZ"

# Disable legacy REAG mode
LEGACY_REAG_MODE = False
```

## Fund Selection Modes

### 1. Administrator Mode

Investigate all funds managed by a specific administrator.

**Configuration:**
```python
TARGET_FUND_MODE = "administrator"
TARGET_IDENTIFIER = "REAG DTVM"  # or any administrator name
INVESTIGATION_NAME = "REAG"
```

**Programmatic Usage:**
```python
from src.utils.fund_selector import select_funds_by_administrator
from pathlib import Path

from src.processors.data_processor import DataProcessor

processor = DataProcessor()
cadastro_df = processor.read_registro_fundo_classe(Path("data/raw"))

funds = select_funds_by_administrator(
    cadastro_df=cadastro_df,
    admin_name="REAG DTVM",
    active_only=True
)

print(f"Selected {len(funds)} funds")
```

**Use Cases:**
- Investigate all funds from a suspect administrator
- Compare administrator's funds to market
- Track administrator reputation over time

### 2. Manager Mode

Investigate all funds managed by a specific fund manager.

**Configuration:**
```python
TARGET_FUND_MODE = "manager"
TARGET_IDENTIFIER = "ABC Gestora"
INVESTIGATION_NAME = "ABC"
```

**Programmatic Usage:**
```python
from src.utils.fund_selector import select_funds_by_manager

funds = select_funds_by_manager(
    cadastro_df=cadastro_df,
    manager_name="ABC Gestora",
    active_only=True
)
```

**Use Cases:**
- Track specific manager's performance
- Detect manager-level fraud patterns
- Compare manager strategies

### 3. Fund List Mode

Investigate specific funds by CNPJ.

**Configuration:**
```python
TARGET_FUND_MODE = "fund_list"
TARGET_FUND_CNPJS = [
    "12345678901234",
    "23456789012345",
    "34567890123456"
]
INVESTIGATION_NAME = "CustomSelection"
```

**Programmatic Usage:**
```python
from src.utils.fund_selector import select_funds_by_cnpj_list

cnpjs = ["12345678901234", "23456789012345"]
funds = select_funds_by_cnpj_list(cadastro_df, cnpjs)
```

**Use Cases:**
- Investigate funds flagged by external sources
- Deep dive into specific funds of interest
- Compare specific fund group

### 4. All Funds Mode

Analyze entire market for anomaly screening.

**Configuration:**
```python
TARGET_FUND_MODE = "all"
TARGET_IDENTIFIER = None
INVESTIGATION_NAME = "MarketScan"
```

**Programmatic Usage:**
```python
from src.utils.fund_selector import select_all_funds

all_funds = select_all_funds(cadastro_df, active_only=True)
```

**Use Cases:**
- Market-wide anomaly screening
- Identify outliers across all funds
- Benchmark against universe

### 5. Legacy REAG Mode

Maintains backwards compatibility with original REAG-specific workflows.

**Configuration:**
```python
LEGACY_REAG_MODE = True  # Default
```

This mode automatically:
- Sets `TARGET_FUND_MODE = "administrator"`
- Searches for REAG, CBSF, Banco Master
- Uses "REAG" as investigation name

## Fund Selector API

### FundSelector Class

The `FundSelector` class provides the core selection functionality:

```python
from src.utils.fund_selector import FundSelector
from pathlib import Path

from src.processors.data_processor import DataProcessor

# Load cadastro data
processor = DataProcessor()
cadastro_df = processor.read_registro_fundo_classe(Path("data/raw"))

# Initialize selector
selector = FundSelector(cadastro_df)

# Select by administrator
funds = selector.select_by_administrator("XYZ DTVM")

# Select by manager
funds = selector.select_by_manager("ABC Gestora")

# Select by CNPJ list
cnpjs = ["12345678901234", "23456789012345"]
funds = selector.select_by_cnpj_list(cnpjs)

# Select all funds
all_funds = selector.select_all()

# Filter to active only
active_funds = selector.select_active_only(funds)

# Get selection summary
summary = selector.get_selection_summary(funds)
print(f"Total funds: {summary['total_funds']}")
print(f"Active funds: {summary['active_funds']}")
print(f"Unique administrators: {summary['unique_administrators']}")
```

### Selection Summary

Get detailed statistics about your fund selection:

```python
from src.utils.fund_selector import get_fund_selection_summary

summary = get_fund_selection_summary(cadastro_df, selected_funds)

# Available metrics:
# - total_funds: Total number of funds selected
# - unique_cnpjs: Number of unique CNPJs
# - unique_administrators: Number of different administrators
# - unique_managers: Number of different managers
# - active_funds: Number of active funds
# - status_breakdown: Distribution by fund status
# - top_administrators: Top 5 administrators by fund count
# - selection_percentage: Percentage of total market selected
```

## Peer Comparison Configuration

Configure how your target funds are compared to peers:

```python
# Enable peer comparison
COMPARISON_MODE = True

# Peer selection strategy
PEER_SELECTION_MODE = "all_others"  # Options below

# Custom peer CNPJs (if using "custom" mode)
PEER_FUND_CNPJS = ["11111111111111", "22222222222222"]

# Include target funds in comparison universe
INCLUDE_TARGET_IN_UNIVERSE = False
```

**Peer Selection Modes:**
- `"same_category"`: Compare to funds in same category
- `"similar_size"`: Compare to funds of similar AUM
- `"all_others"`: Compare to all other funds
- `"custom"`: Use explicit peer CNPJ list

## Complete Workflow Examples

### Example 1: Investigate Specific Administrator

```python
from config.settings import Config
from pathlib import Path

from src.processors.data_processor import DataProcessor
from src.utils.fund_selector import FundSelector

# Configure investigation
config = Config()
config.TARGET_FUND_MODE = "administrator"
config.TARGET_IDENTIFIER = "XYZ DTVM"
config.INVESTIGATION_NAME = "XYZ"
config.LEGACY_REAG_MODE = False

# Load data
processor = DataProcessor(config)
cadastro_df = processor.read_registro_fundo_classe(Path("data/raw"))

# Select funds
selector = FundSelector(cadastro_df)
target_funds = selector.select_by_administrator("XYZ DTVM")
active_funds = selector.select_active_only(target_funds)

# Get summary
summary = selector.get_selection_summary(active_funds)
print(f"Investigating {summary['active_funds']} active funds from XYZ DTVM")

# Save fund list
cnpjs = active_funds['CNPJ_FUNDO'].tolist()
processor.save_processed(
    active_funds[['CNPJ_FUNDO', 'DENOM_SOCIAL', 'SIT']],
    f"{config.INVESTIGATION_NAME}_fund_list.csv"
)

# Continue with analysis...
# 1. Load informe diário data
# 2. Filter to selected funds
# 3. Run anomaly detection
# 4. Generate reports
```

### Example 2: Compare Two Managers

```python
# Select funds from two managers
selector = FundSelector(cadastro_df)

manager_a_funds = selector.select_by_manager("Manager A")
manager_b_funds = selector.select_by_manager("Manager B")

print(f"Manager A: {len(manager_a_funds)} funds")
print(f"Manager B: {len(manager_b_funds)} funds")

# Get summaries
summary_a = selector.get_selection_summary(manager_a_funds)
summary_b = selector.get_selection_summary(manager_b_funds)

# Compare metrics
print(f"\nActive Funds:")
print(f"  Manager A: {summary_a['active_funds']}")
print(f"  Manager B: {summary_b['active_funds']}")
```

### Example 3: Market-Wide Screening

```python
# Select all active funds
selector = FundSelector(cadastro_df)
all_funds = selector.select_all()
active_funds = selector.select_active_only(all_funds)

print(f"Screening {len(active_funds)} active funds across market")

# Run anomaly detection on entire market
# Flag top outliers for further investigation
```

## Tips and Best Practices

### 1. Start with Active Funds Only

Unless investigating historical issues, filter to active funds:

```python
active_funds = selector.select_active_only(selected_funds)
```

### 2. Validate Your Selection

Always check the selection summary before proceeding:

```python
summary = selector.get_selection_summary(funds)
print(f"Selected {summary['total_funds']} funds")
print(f"Active: {summary['active_funds']}")
print(f"Status breakdown: {summary['status_breakdown']}")
```

### 3. Use Consistent Investigation Names

Choose clear, descriptive investigation names:
- ✅ `"REAG"`, `"BTGAdmin"`, `"SuspectManager"`
- ❌ `"test"`, `"fund1"`, `"investigation"`

### 4. Save Fund Lists

Always save your fund selection for reproducibility:

```python
processor.save_processed(
    selected_funds[['CNPJ_FUNDO', 'DENOM_SOCIAL', 'SIT', 'ADMIN']],
    f"{config.INVESTIGATION_NAME}_fund_list.csv"
)
```

### 5. Configure Peer Comparison Carefully

Choose peer comparison mode based on your investigation goal:
- For administrator fraud: Compare to `"all_others"`
- For performance analysis: Compare to `"same_category"` or `"similar_size"`
- For specific comparison: Use `"custom"` with explicit peer list

## Troubleshooting

### No Funds Found

If your selection returns no funds:

1. Check administrator/manager name spelling
2. Try partial name matching (case-insensitive by default)
3. Verify cadastro data is loaded correctly
4. Check for recent administrator name changes

```python
# Debug: List all unique administrators
print(cadastro_df['ADMIN'].value_counts().head(20))
```

### CNPJs Not Matching

If CNPJs in your list aren't found:

1. Ensure CNPJs are 14-digit strings
2. Check for leading zeros
3. Verify CNPJs exist in cadastro

```python
# The selector automatically normalizes CNPJs
# But you can verify manually:
from src.utils.cnpj_utils import normalize_cnpj
normalized = normalize_cnpj("1234567890123")  # Pads to 14 digits
```

### Performance with Large Selections

For market-wide analysis:

1. Use `active_only=True` to reduce dataset size
2. Process data in chunks if memory is limited
3. Consider using `COMPARISON_MODE = False` to skip peer comparison

## Next Steps

After selecting your funds:

1. **Load Informe Diário Data**: `processor.read_informe_diario()`
2. **Filter to Selected Funds**: `processor.filter_by_cnpj(df, cnpjs)`
3. **Run Anomaly Detection**: Use analyzer modules
4. **Generate Reports**: `scripts/generate_public_report.py`

See the main README for detailed workflow instructions.

## Reference

### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `TARGET_FUND_MODE` | str | Selection mode: "administrator", "manager", "fund_list", "all", "legacy_reag" |
| `TARGET_IDENTIFIER` | str\|None | Target name (administrator/manager) |
| `TARGET_FUND_CNPJS` | List[str] | Explicit CNPJ list (for "fund_list" mode) |
| `INVESTIGATION_NAME` | str | Name for reports and outputs |
| `COMPARISON_MODE` | bool | Enable peer comparison |
| `PEER_SELECTION_MODE` | str | Peer selection strategy |
| `PEER_FUND_CNPJS` | List[str] | Custom peer CNPJs |
| `INCLUDE_TARGET_IN_UNIVERSE` | bool | Include targets in comparison |
| `LEGACY_REAG_MODE` | bool | Use legacy REAG-specific mode |
| `REAG_SEARCH_TERMS` | List[str] | Search terms for legacy mode |

### FundSelector Methods

| Method | Description |
|--------|-------------|
| `select_by_administrator(name)` | Select by administrator name |
| `select_by_administrator_cnpj(cnpjs)` | Select by administrator CNPJ |
| `select_by_manager(name)` | Select by manager name |
| `select_by_cnpj_list(cnpjs)` | Select by fund CNPJ list |
| `select_all()` | Select all funds |
| `select_active_only(df)` | Filter to active funds only |
| `get_selection_summary(df)` | Get selection statistics |

### Convenience Functions

| Function | Description |
|----------|-------------|
| `select_funds_by_administrator(cadastro_df, name, active_only)` | Quick administrator selection |
| `select_funds_by_manager(cadastro_df, name, active_only)` | Quick manager selection |
| `select_funds_by_cnpj_list(cadastro_df, cnpjs)` | Quick CNPJ list selection |
| `select_all_funds(cadastro_df, active_only)` | Quick all funds selection |
| `get_fund_selection_summary(cadastro_df, selected)` | Get summary with percentage |
