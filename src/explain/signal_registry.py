from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


Severity = str  # LOW | MEDIUM | HIGH | CRITICAL
Row = Mapping[str, Any]


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _abs_metric(row: Row, column: str) -> float | None:
    value = _to_float(row.get(column))
    return abs(value) if value is not None else None


def _severity_from_named_column(row: Row, column: str = "severity") -> Severity:
    raw = row.get(column)
    if raw is None:
        return "LOW"
    value = str(raw).strip().upper()
    if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return value
    return "LOW"


def _severity_from_thresholds(value: float | None, thresholds: Sequence[tuple[float, Severity]]) -> Severity:
    if value is None:
        return "LOW"
    for minimum, severity in thresholds:
        if value >= minimum:
            return severity
    return "LOW"


def _flow_anomaly_severity(row: Row) -> Severity:
    return _severity_from_thresholds(
        _abs_metric(row, "Z_SCORE_FLOW"),
        thresholds=((5.0, "CRITICAL"), (4.0, "HIGH"), (3.0, "MEDIUM")),
    )


def _pl_drop_severity(row: Row) -> Severity:
    value = _to_float(row.get("PL_VAR_PCT"))
    if value is None:
        return "LOW"
    drop = abs(value) if value < 0 else 0.0
    return _severity_from_thresholds(
        drop,
        thresholds=((40.0, "CRITICAL"), (30.0, "HIGH"), (20.0, "MEDIUM")),
    )


def _run_severity(row: Row) -> Severity:
    value = _to_float(row.get("RUN_LENGTH"))
    return _severity_from_thresholds(
        value,
        thresholds=((20.0, "CRITICAL"), (10.0, "HIGH"), (5.0, "MEDIUM")),
    )


def _shell_network_severity(row: Row) -> Severity:
    count = _to_float(row.get("num_suspicious_issuers"))
    pct = _to_float(row.get("suspicious_pct"))
    # Use whichever is available, biasing toward issuer count.
    if count is not None:
        return _severity_from_thresholds(
            count,
            thresholds=((20.0, "CRITICAL"), (10.0, "HIGH"), (5.0, "MEDIUM")),
        )
    if pct is not None:
        return _severity_from_thresholds(
            pct,
            thresholds=((50.0, "CRITICAL"), (30.0, "HIGH"), (15.0, "MEDIUM")),
        )
    return _severity_from_named_column(row)


def _phantom_asset_severity(row: Row) -> Severity:
    risk = str(row.get("fraud_risk", "")).strip().upper()
    if risk in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        return risk
    return "LOW"


@dataclass(frozen=True)
class SignalDefinition:
    finding_id: str
    title: str
    plain_language_explanation: str
    evidence_fields: tuple[str, ...]
    primary_entities: tuple[str, ...]
    next_steps: tuple[str, ...]
    caveats: tuple[str, ...]
    severity_rule: Callable[[Row], Severity]


SIGNAL_REGISTRY: dict[str, SignalDefinition] = {
    "circular_flow": SignalDefinition(
        finding_id="circular_flow",
        title="Circularity / round-tripping pattern",
        plain_language_explanation=(
            "We detected fund-to-fund links and circular exposures within the same administrator group. "
            "This can be consistent with round-tripping, where money effectively returns to the originating "
            "entity through intermediaries."
        ),
        evidence_fields=(
            "admin_cnpj",
            "fund_as_asset",
            "held_by_funds",
            "num_circular_connections",
            "total_value",
            "severity",
            "banco_master_similarity",
        ),
        primary_entities=("ADMINISTRATOR", "FUND"),
        next_steps=(
            "List the administrator’s funds involved in the loop and request subscription/redemption ledgers for the window.",
            "Trace cash movements around the dates of the circular exposures (bank transfers, distributor orders).",
            "Check related-party links between administrators, issuers, and any involved counterparties.",
        ),
        caveats=(
            "Fund-to-fund holdings can be legitimate in some structures; corroborate with fund documentation and permitted investments.",
            "Public datasets may omit investor identity and transaction routing; internal records are needed to confirm round-tripping.",
        ),
        severity_rule=lambda row: _severity_from_named_column(row),
    ),
    "layered_funds": SignalDefinition(
        finding_id="layered_funds",
        title="Layered funds (fund-of-funds cascade)",
        plain_language_explanation=(
            "We detected funds investing in other funds within the same administrator group, alongside "
            "unusually high recent returns. Layered structures can amplify valuation or reporting problems."
        ),
        evidence_fields=(
            "admin_cnpj",
            "holder_fund",
            "held_fund",
            "investment_value",
            "holder_avg_daily_return",
            "held_avg_daily_return",
            "severity",
        ),
        primary_entities=("ADMINISTRATOR", "FUND"),
        next_steps=(
            "Identify whether inter-fund investments are permitted and disclosed; review prospectuses/regulations.",
            "Check whether returns are consistent with asset mix and whether pricing sources are independent.",
            "Look for rapid growth in AUM/PL with limited external flows (potential valuation inflation).",
        ),
        caveats=(
            "Fund-of-funds structures can be legitimate; focus on unexplained return patterns and related-party exposure.",
        ),
        severity_rule=lambda row: _severity_from_named_column(row),
    ),
    "flow_anomaly": SignalDefinition(
        finding_id="flow_anomaly",
        title="Flow anomaly (z-score outlier)",
        plain_language_explanation=(
            "We detected days where a fund’s net flow was statistically extreme compared to its own history. "
            "This can indicate coordinated subscriptions/redemptions, liquidity stress, or unusual investor behavior."
        ),
        evidence_fields=("CNPJ_FUNDO", "DT_COMPTC", "FLUXO_LIQ_DIA", "Z_SCORE_FLOW"),
        primary_entities=("FUND",),
        next_steps=(
            "Identify the largest subscribers/redeemers for the flagged dates (distributor/investor level).",
            "Confirm whether flows match public disclosures and internal transaction logs (avoid reporting mismatches).",
            "Check if flows coincide with portfolio changes, pricing events, or corporate actions.",
        ),
        caveats=(
            "Large flows can be legitimate (e.g., institutional reallocations); treat as a lead requiring corroboration.",
        ),
        severity_rule=_flow_anomaly_severity,
    ),
    "pl_drop": SignalDefinition(
        finding_id="pl_drop",
        title="Abrupt AUM/PL drop",
        plain_language_explanation=(
            "We detected a sharp drop in a fund’s reported assets under management (AUM/PL) over a short period. "
            "This can indicate a redemption wave, revaluation event, or reporting correction."
        ),
        evidence_fields=("CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ", "PL_VAR_PCT"),
        primary_entities=("FUND",),
        next_steps=(
            "Validate whether the drop is driven by redemptions, valuation changes, or accounting corrections.",
            "Cross-check pricing sources for key holdings during the window.",
            "Review communications to investors and any exceptional events disclosures.",
        ),
        caveats=(
            "PL can change for non-fraud reasons (market moves, large redemptions); confirm with supporting records.",
        ),
        severity_rule=_pl_drop_severity,
    ),
    "redemption_run": SignalDefinition(
        finding_id="redemption_run",
        title="Redemption run (consecutive negative flows)",
        plain_language_explanation=(
            "We detected consecutive days of net negative flows. Sustained runs can signal investor panic, "
            "liquidity mismatch, gating events, or coordinated activity."
        ),
        evidence_fields=("CNPJ_FUNDO", "DT_COMPTC", "FLUXO_LIQ_DIA", "RUN_LENGTH"),
        primary_entities=("FUND",),
        next_steps=(
            "Identify whether the fund used liquidity management tools (gates, side pockets) during the run.",
            "Check if a small number of investors/distributors account for most redemptions.",
            "Compare portfolio liquidity to redemption pressure to assess forced selling risk.",
        ),
        caveats=(
            "Runs can be market-driven; look for clustering across related funds or administrators for stronger signals.",
        ),
        severity_rule=_run_severity,
    ),
    "shell_network": SignalDefinition(
        finding_id="shell_network",
        title="Shell-like issuer network concentration",
        plain_language_explanation=(
            "We detected multiple issuer names with patterns commonly associated with shell or micro-companies. "
            "A dense network of such issuers concentrated under one administrator can be a systemic red flag."
        ),
        evidence_fields=(
            "admin_cnpj",
            "num_suspicious_issuers",
            "suspicious_value",
            "suspicious_pct",
            "num_funds_affected",
            "severity",
        ),
        primary_entities=("ADMINISTRATOR",),
        next_steps=(
            "Collect issuer registries and verify each issuer’s existence, governance, and economic activity.",
            "Map related-party links between issuers, administrators, and any bank/distributor entities.",
            "Review the due diligence process and valuation methodology for private/illiquid instruments.",
        ),
        caveats=(
            "Name-based heuristics can over-flag; confirm with corporate registry and issuance documentation.",
        ),
        severity_rule=_shell_network_severity,
    ),
    "phantom_asset_exposure": SignalDefinition(
        finding_id="phantom_asset_exposure",
        title="Suspicious/phantom asset exposure",
        plain_language_explanation=(
            "We detected assets that appear inconsistent with public registries or have private-asset red flags. "
            "Public assets missing from registries are especially concerning; private assets require manual verification."
        ),
        evidence_fields=("CNPJ_FUNDO", "asset_code", "asset_type", "status", "fraud_risk", "total_value_fund"),
        primary_entities=("FUND",),
        next_steps=(
            "Validate each flagged position with independent documentation (issuance docs, custodian statements).",
            "Confirm pricing sources and whether the asset should be publicly verifiable (stocks/ETFs/BDRs).",
            "Prioritize positions with high value and repeated red flags across multiple funds.",
        ),
        caveats=(
            "Some private assets are not publicly searchable; treat these as ‘needs verification’ rather than definitive fraud.",
        ),
        severity_rule=_phantom_asset_severity,
    ),
    "valuation_smoothing_stub": SignalDefinition(
        finding_id="valuation_smoothing_stub",
        title="Valuation smoothing (placeholder)",
        plain_language_explanation=(
            "This detector is reserved for a next enhancement: identifying return smoothing or stale pricing patterns "
            "that can accompany valuation manipulation in illiquid portfolios."
        ),
        evidence_fields=(),
        primary_entities=("FUND",),
        next_steps=(
            "Implement return autocorrelation and stale-pricing diagnostics once the required time series inputs are confirmed.",
        ),
        caveats=(
            "Not computed in this phase.",
        ),
        severity_rule=lambda row: "LOW",
    ),
    "distributor_concentration_stub": SignalDefinition(
        finding_id="distributor_concentration_stub",
        title="Distributor concentration (placeholder)",
        plain_language_explanation=(
            "This detector is reserved for internal distributor data: identifying flows dominated by a small number "
            "of distributors or investors, which can indicate coordination or concentrated risk."
        ),
        evidence_fields=(),
        primary_entities=("DISTRIBUTOR", "FUND"),
        next_steps=(
            "Implement once distributor order/channel datasets are wired into the pipeline.",
        ),
        caveats=(
            "Not computed in this phase.",
        ),
        severity_rule=lambda row: "LOW",
    ),
}


def validate_registry() -> None:
    """Validate registry is internally consistent (unique IDs, required fields)."""
    seen: set[str] = set()
    for finding_id, definition in SIGNAL_REGISTRY.items():
        if finding_id != definition.finding_id:
            raise ValueError(f"Registry key mismatch for {finding_id}")
        if finding_id in seen:
            raise ValueError(f"Duplicate finding_id: {finding_id}")
        seen.add(finding_id)
        if not definition.title:
            raise ValueError(f"Missing title for {finding_id}")
        if not definition.plain_language_explanation:
            raise ValueError(f"Missing explanation for {finding_id}")
        if not definition.primary_entities:
            raise ValueError(f"Missing primary_entities for {finding_id}")
        if not definition.next_steps:
            raise ValueError(f"Missing next_steps for {finding_id}")

