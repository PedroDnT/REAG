"""
Severity classification utilities for fraud detection.

Provides consistent severity levels and classification logic across analyzers.
"""
from enum import Enum
from typing import Dict, Any, Optional


class SeverityLevel(str, Enum):
    """Severity levels for fraud indicators."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# Severity ranking for sorting/comparison
SEVERITY_RANK = {
    SeverityLevel.CRITICAL: 4,
    SeverityLevel.HIGH: 3,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.LOW: 1,
    SeverityLevel.INFO: 0,
}


class SeverityClassifier:
    """
    Classifies metrics into severity levels based on thresholds.
    
    Provides consistent severity classification across different fraud indicators.
    """
    
    @staticmethod
    def classify_by_threshold(value: float,
                             thresholds: Dict[str, float],
                             higher_is_worse: bool = True) -> SeverityLevel:
        """
        Classify severity based on threshold ranges.
        
        Args:
            value: Metric value to classify
            thresholds: Dict with keys 'critical', 'high', 'medium', 'low'
            higher_is_worse: If True, higher values = higher severity
            
        Returns:
            SeverityLevel enum
            
        Example:
            >>> thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
            >>> classify_by_threshold(12, thresholds)
            SeverityLevel.CRITICAL
        """
        if higher_is_worse:
            if value >= thresholds.get('critical', float('inf')):
                return SeverityLevel.CRITICAL
            elif value >= thresholds.get('high', float('inf')):
                return SeverityLevel.HIGH
            elif value >= thresholds.get('medium', float('inf')):
                return SeverityLevel.MEDIUM
            elif value >= thresholds.get('low', float('inf')):
                return SeverityLevel.LOW
            else:
                return SeverityLevel.INFO
        else:
            if value <= thresholds.get('critical', float('-inf')):
                return SeverityLevel.CRITICAL
            elif value <= thresholds.get('high', float('-inf')):
                return SeverityLevel.HIGH
            elif value <= thresholds.get('medium', float('-inf')):
                return SeverityLevel.MEDIUM
            elif value <= thresholds.get('low', float('-inf')):
                return SeverityLevel.LOW
            else:
                return SeverityLevel.INFO
    
    @staticmethod
    def classify_z_score(z_score: float) -> SeverityLevel:
        """
        Classify severity based on Z-score magnitude.
        
        Args:
            z_score: Z-score value (can be negative)
            
        Returns:
            SeverityLevel based on absolute Z-score
        """
        abs_z = abs(z_score)
        
        if abs_z >= 5.0:
            return SeverityLevel.CRITICAL
        elif abs_z >= 3.5:
            return SeverityLevel.HIGH
        elif abs_z >= 2.5:
            return SeverityLevel.MEDIUM
        elif abs_z >= 1.5:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFO
    
    @staticmethod
    def classify_percentage_change(pct_change: float,
                                  critical: float = 50.0,
                                  high: float = 30.0,
                                  medium: float = 15.0,
                                  low: float = 5.0) -> SeverityLevel:
        """
        Classify severity based on percentage change.
        
        Args:
            pct_change: Percentage change value
            critical: Threshold for critical severity
            high: Threshold for high severity
            medium: Threshold for medium severity
            low: Threshold for low severity
            
        Returns:
            SeverityLevel
        """
        abs_pct = abs(pct_change)
        
        if abs_pct >= critical:
            return SeverityLevel.CRITICAL
        elif abs_pct >= high:
            return SeverityLevel.HIGH
        elif abs_pct >= medium:
            return SeverityLevel.MEDIUM
        elif abs_pct >= low:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFO
    
    @staticmethod
    def classify_concentration(concentration_pct: float) -> SeverityLevel:
        """
        Classify severity based on concentration percentage.
        
        High concentration = higher risk.
        
        Args:
            concentration_pct: Concentration percentage (0-100)
            
        Returns:
            SeverityLevel
        """
        if concentration_pct >= 80:
            return SeverityLevel.CRITICAL
        elif concentration_pct >= 60:
            return SeverityLevel.HIGH
        elif concentration_pct >= 40:
            return SeverityLevel.MEDIUM
        elif concentration_pct >= 20:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFO
    
    @staticmethod
    def get_severity_color(severity: SeverityLevel) -> str:
        """
        Get color code for severity level (for visualization).
        
        Args:
            severity: SeverityLevel enum
            
        Returns:
            Hex color code
        """
        colors = {
            SeverityLevel.CRITICAL: "#DC2626",  # Red
            SeverityLevel.HIGH: "#EA580C",      # Orange
            SeverityLevel.MEDIUM: "#F59E0B",    # Amber
            SeverityLevel.LOW: "#10B981",       # Green
            SeverityLevel.INFO: "#6B7280",      # Gray
        }
        return colors.get(severity, "#6B7280")
    
    @staticmethod
    def get_severity_emoji(severity: SeverityLevel) -> str:
        """
        Get emoji representation for severity level.
        
        Args:
            severity: SeverityLevel enum
            
        Returns:
            Emoji string
        """
        emojis = {
            SeverityLevel.CRITICAL: "🔴",
            SeverityLevel.HIGH: "🟠",
            SeverityLevel.MEDIUM: "🟡",
            SeverityLevel.LOW: "🟢",
            SeverityLevel.INFO: "⚪",
        }
        return emojis.get(severity, "⚪")


def compare_severity(sev1: SeverityLevel, sev2: SeverityLevel) -> int:
    """
    Compare two severity levels.
    
    Args:
        sev1: First severity level
        sev2: Second severity level
        
    Returns:
        -1 if sev1 < sev2, 0 if equal, 1 if sev1 > sev2
    """
    rank1 = SEVERITY_RANK.get(sev1, 0)
    rank2 = SEVERITY_RANK.get(sev2, 0)
    
    if rank1 < rank2:
        return -1
    elif rank1 > rank2:
        return 1
    else:
        return 0


def max_severity(*severities: SeverityLevel) -> SeverityLevel:
    """
    Get the maximum (most severe) severity level from a list.
    
    Args:
        *severities: Variable number of SeverityLevel values
        
    Returns:
        Most severe SeverityLevel
    """
    if not severities:
        return SeverityLevel.INFO
    
    return max(severities, key=lambda s: SEVERITY_RANK.get(s, 0))
