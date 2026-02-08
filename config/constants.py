"""
Constants and thresholds for fraud detection.

This module centralizes all magic numbers and thresholds used across analyzers.
"""

# =============================================================================
# Statistical Analysis Thresholds
# =============================================================================

# Z-score threshold for outlier detection
ZSCORE_THRESHOLD = 3.0

# Z-score for moderate concern
ZSCORE_WARNING = 2.0

# Minimum observations required for statistical analysis
MIN_OBSERVATIONS = 20

# =============================================================================
# Concentration Limits (CVM Regulatory)
# =============================================================================

# Maximum percentage a single asset can represent (10%)
CONCENTRATION_LIMIT_SINGLE_ASSET = 0.10

# Maximum percentage a single issuer can represent (20%)
CONCENTRATION_LIMIT_SINGLE_ISSUER = 0.20

# Herfindahl-Hirschman Index (HHI) thresholds
HHI_LOW = 0.10  # Low concentration
HHI_MODERATE = 0.18  # Moderate concentration
HHI_HIGH = 0.25  # High concentration (warning)
HHI_CRITICAL = 0.40  # Critical concentration

# =============================================================================
# Ponzi Scheme Detection
# =============================================================================

# Sharpe ratio too good to be true threshold
PONZI_SHARPE_THRESHOLD = 5.0

# Volatility suspiciously low (< 0.5% daily, expressed as decimal)
PONZI_LOW_VOLATILITY = 0.005

# Volatility suspiciously low (percentage form, for use with pct_change * 100)
PONZI_LOW_VOLATILITY_PCT = 0.05

# Percentage of positive return days indicating smoothing
PONZI_POSITIVE_DAYS_PCT = 90.0

# Minimum return for Ponzi detection
PONZI_MIN_RETURN = 0.01  # 1% average daily return

# =============================================================================
# Price Manipulation
# =============================================================================

# Price divergence threshold (percentage)
PRICE_DIVERGENCE_THRESHOLD = 10.0

# Severe price divergence
PRICE_DIVERGENCE_SEVERE = 30.0

# =============================================================================
# Flow Anomalies
# =============================================================================

# PL drop percentage indicating crisis
PL_DROP_CRITICAL = 20.0

# PL drop percentage indicating concern
PL_DROP_WARNING = 10.0

# Consecutive redemption days indicating run
REDEMPTION_RUN_DAYS = 5

# =============================================================================
# Fraud Scheme Detection (Banco Master Patterns)
# =============================================================================

# Minimum circular flow value to flag (R$ millions)
CIRCULAR_FLOW_MIN_VALUE = 1_000_000  # R$ 1M

# Maximum percentage of PL that can be in circular flow
CIRCULAR_FLOW_MAX_PCT = 0.05  # 5%

# Minimum number of shell companies to flag network
SHELL_NETWORK_MIN_COUNT = 5

# Percentage of illiquid assets indicating inflation scheme
ASSET_INFLATION_ILLIQUID_PCT = 70.0

# Minimum return on inflated assets to flag (decimal form)
ASSET_INFLATION_MIN_RETURN = 0.005  # 0.5% daily

# Minimum return on inflated assets to flag (percentage form, for use with pct_change * 100)
ASSET_INFLATION_MIN_RETURN_PCT = 0.5  # 0.5% daily

# =============================================================================
# Data Quality
# =============================================================================

# Maximum allowed missing values percentage
MAX_MISSING_PCT = 10.0

# Minimum data completeness percentage
MIN_DATA_COMPLETENESS = 80.0

# =============================================================================
# Cache and Performance
# =============================================================================

# Cache expiration (days)
CACHE_EXPIRATION_DAYS = 7

# Maximum number of assets to validate in parallel
MAX_PARALLEL_VALIDATION = 100

# API rate limiting (requests per second)
API_RATE_LIMIT = 5

# =============================================================================
# Reporting
# =============================================================================

# Fraud risk levels
FRAUD_RISK_CRITICAL = 'CRITICAL'
FRAUD_RISK_HIGH = 'HIGH'
FRAUD_RISK_MEDIUM = 'MEDIUM'
FRAUD_RISK_LOW = 'LOW'

# Severity levels
SEVERITY_CRITICAL = 'CRITICAL'
SEVERITY_HIGH = 'HIGH'
SEVERITY_MEDIUM = 'MEDIUM'
SEVERITY_LOW = 'LOW'

# =============================================================================
# Asset Classification
# =============================================================================

# Shell company indicators
SHELL_COMPANY_PATTERNS = [
    'LTDA ME',
    'LTDA-ME',
    'EIRELI',
    'LTDA EPP',
    'MICRO',
    'MICROEMPRESA'
]

# Banco Master related entities
BANCO_MASTER_ENTITIES = [
    'MASTER',
    'REAG',
    'CBSF',
    'D MAIS',
    'BRAVO'
]

# =============================================================================
# Date Ranges (CVM Data Availability)
# =============================================================================

# CDA only available from 2023
CDA_START_YEAR = 2023
CDA_START_MONTH = 1

# Informe Diário available from 2021
INFORME_START_YEAR = 2021
INFORME_START_MONTH = 1

# =============================================================================
# File Size Limits
# =============================================================================

# Maximum file size for processing (MB)
MAX_FILE_SIZE_MB = 1000

# Maximum memory usage percentage
MAX_MEMORY_PCT = 80.0
