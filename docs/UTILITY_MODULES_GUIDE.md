# Utility Modules Quick Reference Guide

## Overview

This guide provides quick examples for using the new utility modules created during the Phase 1 refactoring.

## CNPJ Utilities (`src/utils/cnpj_utils.py`)

### Basic Usage

```python
from src.utils.cnpj_utils import normalize_cnpj, normalize_cnpj_series, format_cnpj

# Normalize single CNPJ
cnpj = "12.345.678/0001-90"
normalized = normalize_cnpj(cnpj)  # "12345678000190"

# Normalize pandas Series
import pandas as pd
df = pd.DataFrame({'cnpj': ["12.345.678/0001-90", "98765432000100"]})
df['cnpj_normalized'] = normalize_cnpj_series(df['cnpj'])

# Format CNPJ with punctuation
formatted = format_cnpj("12345678000190")  # "12.345.678/0001-90"
```

### Filtering DataFrames by CNPJ

```python
from src.utils.cnpj_utils import normalize_cnpj_list

# Filter by list of CNPJs
target_cnpjs = ["12.345.678/0001-90", "98.765.432/0001-00"]
normalized_list = normalize_cnpj_list(target_cnpjs)

df_filtered = df[df['cnpj_normalized'].isin(normalized_list)]
```

## Statistics Utilities (`src/utils/statistics.py`)

### Z-Score Calculations

```python
from src.utils.statistics import calculate_z_scores, detect_outliers_zscore

# Standard Z-scores
z_scores = calculate_z_scores(df['value'])

# Robust Z-scores (using median and MAD)
robust_z = calculate_z_scores(df['value'], robust=True)

# Detect outliers
outliers = detect_outliers_zscore(df['value'], threshold=3.0)
df_outliers = df[outliers]
```

### Outlier Detection

```python
from src.utils.statistics import detect_outliers_iqr

# IQR-based outlier detection
outliers = detect_outliers_iqr(df['value'], multiplier=1.5)

# Extreme outliers
extreme_outliers = detect_outliers_iqr(df['value'], multiplier=3.0)
```

### Rolling Statistics

```python
from src.utils.statistics import calculate_rolling_stats

# Rolling mean
df['rolling_mean'] = calculate_rolling_stats(df['value'], window=30, stat='mean')

# Rolling standard deviation
df['rolling_std'] = calculate_rolling_stats(df['value'], window=30, stat='std')
```

### Percentage Changes

```python
from src.utils.statistics import calculate_pct_change

# Simple percentage change
df['pct_change'] = calculate_pct_change(df['value'], periods=1)

# With forward fill for NaN values
df['pct_change_filled'] = calculate_pct_change(df['value'], periods=1, fill_method='ffill')
```

### Winsorization

```python
from src.utils.statistics import winsorize

# Cap extreme values at 5th and 95th percentiles
df['value_winsorized'] = winsorize(df['value'], lower_percentile=0.05, upper_percentile=0.95)
```

## Severity Classification (`src/utils/severity.py`)

### Basic Severity Classification

```python
from src.utils.severity import SeverityLevel, SeverityClassifier

# Classify by threshold
severity = SeverityClassifier.classify_by_threshold(
    value=12.5,
    thresholds={'critical': 10, 'high': 5, 'medium': 2, 'low': 1},
    higher_is_worse=True
)
# Returns: SeverityLevel.CRITICAL

# Classify Z-score
severity = SeverityClassifier.classify_z_score(z_score=4.2)
# Returns: SeverityLevel.HIGH

# Classify percentage change
severity = SeverityClassifier.classify_percentage_change(pct_change=-35.0)
# Returns: SeverityLevel.HIGH

# Classify concentration
severity = SeverityClassifier.classify_concentration(concentration_pct=85.0)
# Returns: SeverityLevel.CRITICAL
```

### Working with Severity Levels

```python
from src.utils.severity import SeverityLevel, compare_severity, max_severity

# Compare severities
result = compare_severity(SeverityLevel.HIGH, SeverityLevel.MEDIUM)
# Returns: 1 (HIGH > MEDIUM)

# Get maximum severity
severities = [SeverityLevel.LOW, SeverityLevel.HIGH, SeverityLevel.MEDIUM]
max_sev = max_severity(*severities)
# Returns: SeverityLevel.HIGH
```

### Visualization Helpers

```python
from src.utils.severity import SeverityClassifier

# Get color for visualization
color = SeverityClassifier.get_severity_color(SeverityLevel.CRITICAL)
# Returns: "#DC2626" (red)

# Get emoji representation
emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.HIGH)
# Returns: "🟠"
```

### Using in DataFrames

```python
from src.utils.severity import SeverityClassifier, SeverityLevel

# Classify entire column
df['severity'] = df['z_score'].apply(
    lambda z: SeverityClassifier.classify_z_score(z)
)

# Filter by severity
critical_cases = df[df['severity'] == SeverityLevel.CRITICAL]

# Sort by severity
df['severity_rank'] = df['severity'].map({
    SeverityLevel.CRITICAL: 4,
    SeverityLevel.HIGH: 3,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.LOW: 1,
    SeverityLevel.INFO: 0
})
df_sorted = df.sort_values('severity_rank', ascending=False)
```

## Complete Example: Anomaly Detection Pipeline

```python
import pandas as pd
from src.utils.statistics import calculate_z_scores, detect_outliers_zscore
from src.utils.severity import SeverityClassifier, SeverityLevel
from src.utils.cnpj_utils import normalize_cnpj_series

# Load data
df = pd.read_csv('data.csv')

# Normalize CNPJs
df['cnpj'] = normalize_cnpj_series(df['cnpj'])

# Calculate Z-scores
df['z_score'] = df.groupby('cnpj')['value'].transform(
    lambda x: calculate_z_scores(x, robust=True)
)

# Detect outliers
df['is_outlier'] = detect_outliers_zscore(df['z_score'], threshold=3.0)

# Classify severity
df['severity'] = df['z_score'].apply(
    lambda z: SeverityClassifier.classify_z_score(z)
)

# Add visualization helpers
df['severity_color'] = df['severity'].apply(
    lambda s: SeverityClassifier.get_severity_color(s)
)
df['severity_emoji'] = df['severity'].apply(
    lambda s: SeverityClassifier.get_severity_emoji(s)
)

# Filter critical cases
critical_anomalies = df[
    (df['is_outlier']) & 
    (df['severity'] == SeverityLevel.CRITICAL)
]

print(f"Found {len(critical_anomalies)} critical anomalies")
```

## Migration from Old Code

### Before: Manual CNPJ Normalization
```python
# Old way (scattered across multiple files)
def normalize_cnpj_old(cnpj):
    digits = "".join(ch for ch in str(cnpj) if ch.isdigit())
    if len(digits) < 14:
        digits = digits.zfill(14)
    return digits[:14]
```

### After: Use Utility
```python
from src.utils.cnpj_utils import normalize_cnpj

normalized = normalize_cnpj(cnpj)
```

### Before: Manual Z-Score Calculation
```python
# Old way (duplicated in multiple analyzers)
mean = series.mean()
std = series.std()
if std == 0:
    z_scores = pd.Series(0, index=series.index)
else:
    z_scores = (series - mean) / std
```

### After: Use Utility
```python
from src.utils.statistics import calculate_z_scores

z_scores = calculate_z_scores(series)
```

### Before: Manual Severity Classification
```python
# Old way (inconsistent thresholds across files)
if abs_value >= 10:
    severity = "CRITICAL"
elif abs_value >= 5:
    severity = "HIGH"
elif abs_value >= 2:
    severity = "MEDIUM"
else:
    severity = "LOW"
```

### After: Use Utility
```python
from src.utils.severity import SeverityClassifier

severity = SeverityClassifier.classify_by_threshold(
    value=abs_value,
    thresholds={'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
)
```

## Best Practices

1. **Always use utilities for common operations** - Don't reimplement
2. **Import at module level** - Not inside functions
3. **Use type hints** - Utilities have full type annotations
4. **Check docstrings** - All utilities are well-documented
5. **Contribute improvements** - If you enhance a utility, update it for everyone

## Testing Utilities

```python
# Test CNPJ normalization
from src.utils.cnpj_utils import normalize_cnpj
assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"

# Test Z-score calculation
from src.utils.statistics import calculate_z_scores
import pandas as pd
series = pd.Series([1, 2, 3, 4, 5])
z_scores = calculate_z_scores(series)
assert abs(z_scores.mean()) < 0.01  # Mean should be ~0

# Test severity classification
from src.utils.severity import SeverityClassifier, SeverityLevel
severity = SeverityClassifier.classify_z_score(4.0)
assert severity == SeverityLevel.HIGH
```

## Performance Tips

1. **Vectorize operations** - Use pandas Series methods when possible
2. **Avoid loops** - Utilities are optimized for pandas operations
3. **Cache results** - Don't recalculate Z-scores multiple times
4. **Use robust methods** - For data with outliers, use `robust=True`

## Getting Help

- Check function docstrings: `help(normalize_cnpj)`
- Read source code: All utilities are in `src/utils/`
- Ask team members: Utilities are shared knowledge
- Update this guide: If you find better patterns

---

**Last Updated**: 2026-03-12
**Version**: 1.0
