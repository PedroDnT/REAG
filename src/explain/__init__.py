"""
Human-readable explanation layer for investigation outputs.
"""

from .explainer import Explainer
from .signal_registry import SIGNAL_REGISTRY, SignalDefinition

__all__ = [
    "Explainer",
    "SIGNAL_REGISTRY",
    "SignalDefinition",
]

