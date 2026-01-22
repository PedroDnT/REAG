"""
Fraud Detection Analyzers

Main analyzers for detecting various types of fraud patterns in investment funds.
"""

from .anomaly_detector import AnomalyDetector
from .enhanced_phantom_assets import EnhancedPhantomAssetDetector
from .fraud_schemes import FraudSchemeDetector
from .peer_comparison import PeerComparisonAnalyzer
from .concentration import ConcentrationAnalyzer
from .market_data import MarketDataValidator

__all__ = [
    'AnomalyDetector',
    'EnhancedPhantomAssetDetector',
    'FraudSchemeDetector',
    'PeerComparisonAnalyzer',
    'ConcentrationAnalyzer',
    'MarketDataValidator',
]

# Deprecated - Use EnhancedPhantomAssetDetector instead
# PhantomAssetDetector has been removed in favor of the enhanced version
# that properly distinguishes between public and private assets
