"""
Fraud Detection Analyzers.

Main analyzers for detecting various types of fraud patterns in investment funds.
"""

from .anomaly_detector import AnomalyDetector
from .benford_law import BenfordLawAnalyzer
from .concentration import ConcentrationAnalyzer
from .enhanced_phantom_assets import EnhancedPhantomAssetDetector
from .fraud_schemes import FraudSchemeDetector
from .market_data import MarketDataValidator
from .peer_comparison import PeerComparisonAnalyzer

__all__ = [
    "AnomalyDetector",
    "BenfordLawAnalyzer",
    "ConcentrationAnalyzer",
    "EnhancedPhantomAssetDetector",
    "FraudSchemeDetector",
    "MarketDataValidator",
    "PeerComparisonAnalyzer",
]

# NOTE: PhantomAssetDetector (basic) has been removed in favor of the enhanced
# version that properly distinguishes between public and private assets.
