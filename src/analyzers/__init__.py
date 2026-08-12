"""
Fraud Detection Analyzers.

Main analyzers for detecting various types of fraud patterns in investment funds.
"""

from .anomaly_detector import AnomalyDetector
from .benford_law import BenfordLawAnalyzer
from .concentration import ConcentrationAnalyzer
from .cost_basis_analyzer import CostBasisAnalyzer
from .cross_fund_issuer import CrossFundIssuerAnalyzer
from .enhanced_phantom_assets import EnhancedPhantomAssetDetector
from .fraud_schemes import FraudSchemeDetector
from .fund_lifecycle import FundLifecycleAnalyzer
from .manager_network import ManagerNetworkAnalyzer
from .market_data import MarketDataValidator
from .peer_comparison import PeerComparisonAnalyzer
from .portfolio_reconciliation import PortfolioReconciliationAnalyzer
from .price_divergence import CrossFundPriceDivergenceAnalyzer
from .quotaholder_analyzer import QuotaholderAnalyzer
from .valuation_smoothing import ValuationSmoothingAnalyzer
from .window_dressing import WindowDressingDetector

__all__ = [
    "AnomalyDetector",
    "BenfordLawAnalyzer",
    "ConcentrationAnalyzer",
    "CostBasisAnalyzer",
    "CrossFundIssuerAnalyzer",
    "CrossFundPriceDivergenceAnalyzer",
    "EnhancedPhantomAssetDetector",
    "FraudSchemeDetector",
    "FundLifecycleAnalyzer",
    "ManagerNetworkAnalyzer",
    "MarketDataValidator",
    "PeerComparisonAnalyzer",
    "PortfolioReconciliationAnalyzer",
    "QuotaholderAnalyzer",
    "ValuationSmoothingAnalyzer",
    "WindowDressingDetector",
]

# NOTE: PhantomAssetDetector (basic) has been removed in favor of the enhanced
# version that properly distinguishes between public and private assets.
