"""Tests for the signal registry module."""

import pytest
from src.explain.signal_registry import (
    validate_registry,
    SIGNAL_REGISTRY,
    SignalDefinition,
)


def test_signal_registry_validates():
    """validate_registry should not raise for the current registry."""
    validate_registry()


def test_registry_has_expected_signals():
    """Registry should contain all expected core finding IDs."""
    expected_ids = {
        "circular_flow",
        "layered_funds",
        "flow_anomaly",
        "pl_drop",
        "redemption_run",
        "shell_network",
        "phantom_asset_exposure",
    }
    assert expected_ids.issubset(SIGNAL_REGISTRY.keys())


def test_each_signal_has_required_fields():
    """Every signal definition should have non-empty key fields."""
    for finding_id, defn in SIGNAL_REGISTRY.items():
        assert isinstance(defn, SignalDefinition), f"{finding_id} is not a SignalDefinition"
        assert defn.title, f"{finding_id} missing title"
        assert defn.plain_language_explanation, f"{finding_id} missing explanation"
        assert defn.primary_entities, f"{finding_id} missing primary_entities"
        assert defn.next_steps, f"{finding_id} missing next_steps"
        assert callable(defn.severity_rule), f"{finding_id} severity_rule not callable"


def test_finding_id_matches_key():
    """Each registry key must match its definition's finding_id."""
    for key, defn in SIGNAL_REGISTRY.items():
        assert key == defn.finding_id, f"Key {key!r} != definition.finding_id {defn.finding_id!r}"


def test_severity_rules_return_valid_values():
    """Each severity_rule should return a valid severity string for empty input."""
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    for finding_id, defn in SIGNAL_REGISTRY.items():
        result = defn.severity_rule({})
        assert result in valid_severities, (
            f"{finding_id} severity_rule returned {result!r} for empty row"
        )
