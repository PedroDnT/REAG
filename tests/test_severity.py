"""Tests for severity classification utilities."""
import pytest
from src.utils.severity import (
    SeverityLevel,
    SeverityClassifier,
    SEVERITY_RANK,
    compare_severity,
    max_severity,
)


class TestSeverityLevel:
    """Test SeverityLevel enum."""

    def test_severity_levels_exist(self):
        """Test that all severity levels exist."""
        assert SeverityLevel.CRITICAL == "CRITICAL"
        assert SeverityLevel.HIGH == "HIGH"
        assert SeverityLevel.MEDIUM == "MEDIUM"
        assert SeverityLevel.LOW == "LOW"
        assert SeverityLevel.INFO == "INFO"

    def test_severity_rank_mapping(self):
        """Test that severity ranks are correctly ordered."""
        assert SEVERITY_RANK[SeverityLevel.CRITICAL] > SEVERITY_RANK[SeverityLevel.HIGH]
        assert SEVERITY_RANK[SeverityLevel.HIGH] > SEVERITY_RANK[SeverityLevel.MEDIUM]
        assert SEVERITY_RANK[SeverityLevel.MEDIUM] > SEVERITY_RANK[SeverityLevel.LOW]
        assert SEVERITY_RANK[SeverityLevel.LOW] > SEVERITY_RANK[SeverityLevel.INFO]


class TestSeverityClassifierByThreshold:
    """Test classify_by_threshold method."""

    def test_classify_critical_higher_is_worse(self):
        """Test classification as CRITICAL when value exceeds critical threshold."""
        thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        result = SeverityClassifier.classify_by_threshold(15, thresholds, higher_is_worse=True)
        assert result == SeverityLevel.CRITICAL

    def test_classify_high_higher_is_worse(self):
        """Test classification as HIGH when value exceeds high threshold."""
        thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        result = SeverityClassifier.classify_by_threshold(7, thresholds, higher_is_worse=True)
        assert result == SeverityLevel.HIGH

    def test_classify_medium_higher_is_worse(self):
        """Test classification as MEDIUM when value exceeds medium threshold."""
        thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        result = SeverityClassifier.classify_by_threshold(3, thresholds, higher_is_worse=True)
        assert result == SeverityLevel.MEDIUM

    def test_classify_low_higher_is_worse(self):
        """Test classification as LOW when value exceeds low threshold."""
        thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        result = SeverityClassifier.classify_by_threshold(1.5, thresholds, higher_is_worse=True)
        assert result == SeverityLevel.LOW

    def test_classify_info_higher_is_worse(self):
        """Test classification as INFO when value below all thresholds."""
        thresholds = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        result = SeverityClassifier.classify_by_threshold(0.5, thresholds, higher_is_worse=True)
        assert result == SeverityLevel.INFO

    def test_classify_critical_lower_is_worse(self):
        """Test classification as CRITICAL when value below critical threshold."""
        thresholds = {'critical': 1, 'high': 2, 'medium': 5, 'low': 10}
        result = SeverityClassifier.classify_by_threshold(0.5, thresholds, higher_is_worse=False)
        assert result == SeverityLevel.CRITICAL

    def test_classify_high_lower_is_worse(self):
        """Test classification as HIGH when value below high threshold."""
        thresholds = {'critical': 1, 'high': 2, 'medium': 5, 'low': 10}
        result = SeverityClassifier.classify_by_threshold(1.5, thresholds, higher_is_worse=False)
        assert result == SeverityLevel.HIGH

    def test_classify_medium_lower_is_worse(self):
        """Test classification as MEDIUM when value below medium threshold."""
        thresholds = {'critical': 1, 'high': 2, 'medium': 5, 'low': 10}
        result = SeverityClassifier.classify_by_threshold(3, thresholds, higher_is_worse=False)
        assert result == SeverityLevel.MEDIUM

    def test_classify_low_lower_is_worse(self):
        """Test classification as LOW when value below low threshold."""
        thresholds = {'critical': 1, 'high': 2, 'medium': 5, 'low': 10}
        result = SeverityClassifier.classify_by_threshold(8, thresholds, higher_is_worse=False)
        assert result == SeverityLevel.LOW

    def test_classify_info_lower_is_worse(self):
        """Test classification as INFO when value above all thresholds."""
        thresholds = {'critical': 1, 'high': 2, 'medium': 5, 'low': 10}
        result = SeverityClassifier.classify_by_threshold(15, thresholds, higher_is_worse=False)
        assert result == SeverityLevel.INFO


class TestSeverityClassifierZScore:
    """Test classify_z_score method."""

    def test_classify_critical_z_score(self):
        """Test classification of critical Z-score (abs >= 5.0)."""
        assert SeverityClassifier.classify_z_score(5.5) == SeverityLevel.CRITICAL
        assert SeverityClassifier.classify_z_score(-5.5) == SeverityLevel.CRITICAL

    def test_classify_high_z_score(self):
        """Test classification of high Z-score (abs >= 3.5)."""
        assert SeverityClassifier.classify_z_score(4.0) == SeverityLevel.HIGH
        assert SeverityClassifier.classify_z_score(-4.0) == SeverityLevel.HIGH

    def test_classify_medium_z_score(self):
        """Test classification of medium Z-score (abs >= 2.5)."""
        assert SeverityClassifier.classify_z_score(3.0) == SeverityLevel.MEDIUM
        assert SeverityClassifier.classify_z_score(-3.0) == SeverityLevel.MEDIUM

    def test_classify_low_z_score(self):
        """Test classification of low Z-score (abs >= 1.5)."""
        assert SeverityClassifier.classify_z_score(2.0) == SeverityLevel.LOW
        assert SeverityClassifier.classify_z_score(-2.0) == SeverityLevel.LOW

    def test_classify_info_z_score(self):
        """Test classification of info Z-score (abs < 1.5)."""
        assert SeverityClassifier.classify_z_score(1.0) == SeverityLevel.INFO
        assert SeverityClassifier.classify_z_score(-1.0) == SeverityLevel.INFO
        assert SeverityClassifier.classify_z_score(0.0) == SeverityLevel.INFO


class TestSeverityClassifierPercentageChange:
    """Test classify_percentage_change method."""

    def test_classify_critical_percentage(self):
        """Test classification of critical percentage change."""
        result = SeverityClassifier.classify_percentage_change(60.0)
        assert result == SeverityLevel.CRITICAL
        result = SeverityClassifier.classify_percentage_change(-60.0)
        assert result == SeverityLevel.CRITICAL

    def test_classify_high_percentage(self):
        """Test classification of high percentage change."""
        result = SeverityClassifier.classify_percentage_change(40.0)
        assert result == SeverityLevel.HIGH
        result = SeverityClassifier.classify_percentage_change(-40.0)
        assert result == SeverityLevel.HIGH

    def test_classify_medium_percentage(self):
        """Test classification of medium percentage change."""
        result = SeverityClassifier.classify_percentage_change(20.0)
        assert result == SeverityLevel.MEDIUM
        result = SeverityClassifier.classify_percentage_change(-20.0)
        assert result == SeverityLevel.MEDIUM

    def test_classify_low_percentage(self):
        """Test classification of low percentage change."""
        result = SeverityClassifier.classify_percentage_change(7.0)
        assert result == SeverityLevel.LOW
        result = SeverityClassifier.classify_percentage_change(-7.0)
        assert result == SeverityLevel.LOW

    def test_classify_info_percentage(self):
        """Test classification of info percentage change."""
        result = SeverityClassifier.classify_percentage_change(3.0)
        assert result == SeverityLevel.INFO
        result = SeverityClassifier.classify_percentage_change(-3.0)
        assert result == SeverityLevel.INFO

    def test_classify_custom_thresholds(self):
        """Test classification with custom thresholds."""
        result = SeverityClassifier.classify_percentage_change(
            25.0, critical=100, high=50, medium=25, low=10
        )
        assert result == SeverityLevel.MEDIUM


class TestSeverityClassifierConcentration:
    """Test classify_concentration method."""

    def test_classify_critical_concentration(self):
        """Test classification of critical concentration (>= 80%)."""
        result = SeverityClassifier.classify_concentration(85.0)
        assert result == SeverityLevel.CRITICAL

    def test_classify_high_concentration(self):
        """Test classification of high concentration (>= 60%)."""
        result = SeverityClassifier.classify_concentration(70.0)
        assert result == SeverityLevel.HIGH

    def test_classify_medium_concentration(self):
        """Test classification of medium concentration (>= 40%)."""
        result = SeverityClassifier.classify_concentration(50.0)
        assert result == SeverityLevel.MEDIUM

    def test_classify_low_concentration(self):
        """Test classification of low concentration (>= 20%)."""
        result = SeverityClassifier.classify_concentration(30.0)
        assert result == SeverityLevel.LOW

    def test_classify_info_concentration(self):
        """Test classification of info concentration (< 20%)."""
        result = SeverityClassifier.classify_concentration(10.0)
        assert result == SeverityLevel.INFO


class TestSeverityClassifierColor:
    """Test get_severity_color method."""

    def test_critical_color(self):
        """Test color for CRITICAL severity."""
        color = SeverityClassifier.get_severity_color(SeverityLevel.CRITICAL)
        assert color == "#DC2626"

    def test_high_color(self):
        """Test color for HIGH severity."""
        color = SeverityClassifier.get_severity_color(SeverityLevel.HIGH)
        assert color == "#EA580C"

    def test_medium_color(self):
        """Test color for MEDIUM severity."""
        color = SeverityClassifier.get_severity_color(SeverityLevel.MEDIUM)
        assert color == "#F59E0B"

    def test_low_color(self):
        """Test color for LOW severity."""
        color = SeverityClassifier.get_severity_color(SeverityLevel.LOW)
        assert color == "#10B981"

    def test_info_color(self):
        """Test color for INFO severity."""
        color = SeverityClassifier.get_severity_color(SeverityLevel.INFO)
        assert color == "#6B7280"


class TestSeverityClassifierEmoji:
    """Test get_severity_emoji method."""

    def test_critical_emoji(self):
        """Test emoji for CRITICAL severity."""
        emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.CRITICAL)
        assert emoji == "🔴"

    def test_high_emoji(self):
        """Test emoji for HIGH severity."""
        emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.HIGH)
        assert emoji == "🟠"

    def test_medium_emoji(self):
        """Test emoji for MEDIUM severity."""
        emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.MEDIUM)
        assert emoji == "🟡"

    def test_low_emoji(self):
        """Test emoji for LOW severity."""
        emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.LOW)
        assert emoji == "🟢"

    def test_info_emoji(self):
        """Test emoji for INFO severity."""
        emoji = SeverityClassifier.get_severity_emoji(SeverityLevel.INFO)
        assert emoji == "⚪"


class TestCompareSeverity:
    """Test compare_severity function."""

    def test_compare_critical_vs_high(self):
        """Test comparison of CRITICAL vs HIGH."""
        result = compare_severity(SeverityLevel.CRITICAL, SeverityLevel.HIGH)
        assert result == 1

    def test_compare_low_vs_medium(self):
        """Test comparison of LOW vs MEDIUM."""
        result = compare_severity(SeverityLevel.LOW, SeverityLevel.MEDIUM)
        assert result == -1

    def test_compare_equal_severity(self):
        """Test comparison of equal severities."""
        result = compare_severity(SeverityLevel.HIGH, SeverityLevel.HIGH)
        assert result == 0

    def test_compare_info_vs_critical(self):
        """Test comparison of INFO vs CRITICAL."""
        result = compare_severity(SeverityLevel.INFO, SeverityLevel.CRITICAL)
        assert result == -1


class TestMaxSeverity:
    """Test max_severity function."""

    def test_max_severity_single_value(self):
        """Test max_severity with a single value."""
        result = max_severity(SeverityLevel.HIGH)
        assert result == SeverityLevel.HIGH

    def test_max_severity_multiple_values(self):
        """Test max_severity with multiple values."""
        result = max_severity(
            SeverityLevel.LOW,
            SeverityLevel.CRITICAL,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH
        )
        assert result == SeverityLevel.CRITICAL

    def test_max_severity_all_same(self):
        """Test max_severity when all values are the same."""
        result = max_severity(
            SeverityLevel.MEDIUM,
            SeverityLevel.MEDIUM,
            SeverityLevel.MEDIUM
        )
        assert result == SeverityLevel.MEDIUM

    def test_max_severity_empty(self):
        """Test max_severity with no arguments."""
        result = max_severity()
        assert result == SeverityLevel.INFO

    def test_max_severity_info_only(self):
        """Test max_severity with only INFO levels."""
        result = max_severity(SeverityLevel.INFO, SeverityLevel.INFO)
        assert result == SeverityLevel.INFO
