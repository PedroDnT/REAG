from __future__ import annotations

import hashlib
import html
import json
import numbers
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Iterable

import pandas as pd

from .charts import FundChartOutputs, build_circular_flow_mermaid, render_fund_timeseries_charts, write_mermaid_diagram
from .signal_registry import SIGNAL_REGISTRY, SignalDefinition, validate_registry
from src.utils.validation import normalize_cnpj_digits as _normalize_cnpj_digits


SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _stable_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    cnpj_digits: str | None
    name: str | None
    relationships: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceItem:
    finding_id: str
    title: str
    severity: str
    metric: str
    time_window: str
    counterparties: str
    source_ref: str
    record: dict[str, Any]


class Explainer:
    def __init__(self):
        validate_registry()

    def generate(
        self,
        *,
        results: dict[str, pd.DataFrame],
        output_dir: Path,
        informe_df: pd.DataFrame | None = None,
        cadastro_df: pd.DataFrame | None = None,
        sources: dict[str, str] | None = None,
        contexts_by_entity_id: dict[str, dict[str, Any]] | None = None,
        explain_max_entities: int = 200,
        explain_top_findings: int = 6,
        explain_format: str = "both",
    ) -> pd.DataFrame:
        """
        Create per-entity briefs (md/html), evidence.json, and a global report.html.

        Returns:
            A DataFrame summarizing flagged entities (for top table).
        """
        output_dir = Path(output_dir)
        entities_dir = output_dir / "entities"
        assets_dir = output_dir / "assets"
        entities_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        sources = sources or {}
        contexts_by_entity_id = contexts_by_entity_id or {}

        entity_catalog = self._build_entity_catalog(cadastro_df=cadastro_df)
        entity_evidence = self._collect_evidence(
            results=results,
            sources=sources,
            entity_catalog=entity_catalog,
            informe_df=informe_df,
            assets_dir=assets_dir,
        )

        # Rank entities by overall severity, then by number of evidence items.
        summaries = []
        for entity_id, evidence_items in entity_evidence.items():
            if entity_id not in entity_catalog:
                continue
            overall = self._overall_severity(evidence_items)
            summaries.append(
                {
                    "entity_id": entity_id,
                    "entity_type": entity_catalog[entity_id].entity_type,
                    "cnpj_digits": entity_catalog[entity_id].cnpj_digits,
                    "name": entity_catalog[entity_id].name,
                    "overall_severity": overall,
                    "evidence_count": len(evidence_items),
                }
            )

        summary_df = pd.DataFrame(summaries)
        if not summary_df.empty:
            summary_df = summary_df.sort_values(
                by=["overall_severity", "evidence_count"],
                key=lambda col: col.map(lambda v: SEVERITY_RANK.get(str(v), 0)),
                ascending=False,
            )

        # Limit output volume deterministically.
        if len(summary_df) > explain_max_entities:
            summary_df = summary_df.head(explain_max_entities).copy()

        for row in summary_df.itertuples(index=False):
            entity_id = row.entity_id
            entity = entity_catalog[entity_id]
            evidence_items = entity_evidence.get(entity_id, [])
            evidence_items = self._top_evidence(evidence_items, top_n=explain_top_findings)
            context = contexts_by_entity_id.get(entity_id)
            self._write_entity_outputs(
                entity=entity,
                evidence_items=evidence_items,
                output_dir=entities_dir / entity_id,
                output_root=output_dir,
                charts=self._find_charts_for_entity(assets_dir=assets_dir, entity=entity),
                context=context,
                explain_format=explain_format,
            )

        self._write_global_report(
            output_path=output_dir / "report.html",
            run_id=str(output_dir.name),
            summary_df=summary_df,
        )

        return summary_df

    def _build_entity_catalog(self, *, cadastro_df: pd.DataFrame | None) -> dict[str, Entity]:
        catalog: dict[str, Entity] = {}
        if cadastro_df is None or cadastro_df.empty:
            return catalog

        df = cadastro_df.copy()
        if "CNPJ_FUNDO" not in df.columns:
            return catalog

        name_col = _pick_column(df.columns, ("DENOM_SOCIAL", "DENOM_SOCIAL_FUNDO", "NOME_FUNDO", "NM_FUNDO"))
        admin_col = _pick_column(df.columns, ("CNPJ_ADMIN", "CNPJ_ADMINISTRADOR"))
        gestor_col = _pick_column(df.columns, ("CNPJ_GESTOR", "CNPJ_GESTOR_GESTAO"))

        def present(column: str | None) -> Any:
            """Row value when usable, else None.

            Cadastro columns arrive as nullable dtypes, so a missing value is
            pd.NA -- and `if pd.NA` raises TypeError rather than being falsy.
            Real CVM data has gaps in exactly these columns; synthetic fixtures
            did not, which is why this only surfaced against a live download.
            """
            if not column:
                return None
            value = row_dict.get(column)
            return None if value is None or pd.isna(value) else value

        for row in df.itertuples(index=False):
            row_dict = row._asdict()
            fund_digits = _normalize_cnpj_digits(row_dict.get("CNPJ_FUNDO"))
            if not fund_digits:
                continue
            entity_id = f"FUND_{fund_digits}"
            relationships = []
            if present(admin_col):
                relationships.append(f"Administrator CNPJ: {present(admin_col)}")
            if present(gestor_col):
                relationships.append(f"Manager CNPJ: {present(gestor_col)}")

            name_value = present(name_col)
            catalog[entity_id] = Entity(
                entity_id=entity_id,
                entity_type="FUND",
                cnpj_digits=fund_digits,
                name=str(name_value).strip() if name_value is not None else None,
                relationships=tuple(relationships),
            )

        # Add administrator entities with basic relationships (count of funds).
        if admin_col:
            admin_to_funds = df.groupby(admin_col)["CNPJ_FUNDO"].apply(list).to_dict()
            for admin_raw, funds in admin_to_funds.items():
                admin_digits = _normalize_cnpj_digits(admin_raw)
                if not admin_digits:
                    continue
                entity_id = f"ADMINISTRATOR_{admin_digits}"
                relationships = (f"Funds administered: {len(funds)}",)
                catalog.setdefault(
                    entity_id,
                    Entity(
                        entity_id=entity_id,
                        entity_type="ADMINISTRATOR",
                        cnpj_digits=admin_digits,
                        name=None,
                        relationships=relationships,
                    ),
                )

        if gestor_col:
            gestor_to_funds = df.groupby(gestor_col)["CNPJ_FUNDO"].apply(list).to_dict()
            for gestor_raw, funds in gestor_to_funds.items():
                gestor_digits = _normalize_cnpj_digits(gestor_raw)
                if not gestor_digits:
                    continue
                entity_id = f"MANAGER_{gestor_digits}"
                relationships = (f"Funds managed: {len(funds)}",)
                catalog.setdefault(
                    entity_id,
                    Entity(
                        entity_id=entity_id,
                        entity_type="MANAGER",
                        cnpj_digits=gestor_digits,
                        name=None,
                        relationships=relationships,
                    ),
                )

        return catalog

    def _collect_evidence(
        self,
        *,
        results: dict[str, pd.DataFrame],
        sources: dict[str, str],
        entity_catalog: dict[str, Entity],
        informe_df: pd.DataFrame | None,
        assets_dir: Path,
    ) -> dict[str, list[EvidenceItem]]:
        evidence_by_entity: dict[str, list[EvidenceItem]] = {}

        def add(entity_id: str, item: EvidenceItem) -> None:
            evidence_by_entity.setdefault(entity_id, []).append(item)

        # Flow/report anomalies (fund level)
        for key, finding_id, cnpj_col, date_col, metric_col in (
            ("flow_anomalies", "flow_anomaly", "CNPJ_FUNDO", "DT_COMPTC", "Z_SCORE_FLOW"),
            ("pl_drops", "pl_drop", "CNPJ_FUNDO", "DT_COMPTC", "PL_VAR_PCT"),
            ("runs", "redemption_run", "CNPJ_FUNDO", "DT_COMPTC", "RUN_LENGTH"),
            # Findings that previously reached a CSV but never a brief. A finding
            # the reader never sees is only half-delivered.
            (
                "cross_fund_price_divergence", "cross_fund_price_divergence",
                "CNPJ_FUNDO", "DT_COMPTC", "divergence_pct",
            ),
            ("concentration_spikes", "concentration_violation", "CNPJ_FUNDO", "DT_COMPTC", "PCT_CARTEIRA"),
            ("concentration_violations", "concentration_violation", "CNPJ_FUNDO", None, "top1_pct"),
            ("peer_outliers", "peer_outlier", "CNPJ_FUNDO", None, "sharpe_zscore"),
            ("benford_violations", "benford_violation", "fund_cnpj", None, "pl_mad"),
        ):
            df = results.get(key)
            if df is None or df.empty:
                continue
            definition = SIGNAL_REGISTRY[finding_id]
            source_ref = sources.get(key, "")
            for row in df.to_dict(orient="records"):
                fund_digits = _normalize_cnpj_digits(row.get(cnpj_col))
                if not fund_digits:
                    continue
                entity_id = f"FUND_{fund_digits}"
                entity_catalog.setdefault(
                    entity_id,
                    Entity(entity_id=entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                )

                severity = definition.severity_rule(row)
                metric = _describe_metric(row, metric_col)
                # Some findings are computed over the whole period rather than
                # dated to a day (peer comparison, Benford, concentration), so
                # date_col is None for those and the brief simply omits a window.
                date = row.get(date_col) if date_col else None
                time_window = _format_time_window(date, date)
                add(
                    entity_id,
                    EvidenceItem(
                        finding_id=finding_id,
                        title=definition.title,
                        severity=severity,
                        metric=metric,
                        time_window=time_window,
                        counterparties="",
                        source_ref=source_ref,
                        record=_filter_record(row, definition),
                    ),
                )

        # Divergences
        df = results.get("divergences")
        if df is not None and not df.empty:
            finding_id = "flow_performance_divergence"
            # If registry doesn't have it, treat as flow anomaly explanation.
            definition = SIGNAL_REGISTRY.get("flow_anomaly")
            source_ref = sources.get("divergences", "")
            for row in df.to_dict(orient="records"):
                fund_digits = _normalize_cnpj_digits(row.get("CNPJ_FUNDO"))
                if not fund_digits:
                    continue
                entity_id = f"FUND_{fund_digits}"
                entity_catalog.setdefault(
                    entity_id,
                    Entity(entity_id=entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                )
                metric_val = row.get("DIVERGENCE_SCORE")
                metric = f"DIVERGENCE_SCORE: {metric_val}"
                date = row.get("DT_COMPTC")
                add(
                    entity_id,
                    EvidenceItem(
                        finding_id=finding_id,
                        title="Flow vs performance divergence",
                        severity="MEDIUM",
                        metric=metric,
                        time_window=_format_time_window(date, date),
                        counterparties="",
                        source_ref=source_ref,
                        record=_filter_record(row, definition) if definition else dict(row),
                    ),
                )

        # Fraud schemes: circular flow, layered funds, asset inflation, shell networks
        scheme_map = [
            ("circular_flow", "circular_flow", "admin_cnpj"),
            ("layered_funds", "layered_funds", "admin_cnpj"),
            ("asset_inflation", "asset_inflation", "fund_cnpj"),
            ("shell_networks", "shell_network", "admin_cnpj"),
        ]
        for key, finding_id, primary_col in scheme_map:
            df = results.get(key)
            if df is None or df.empty:
                continue
            definition = SIGNAL_REGISTRY.get(finding_id)
            source_ref = sources.get(key, "")
            for row in df.to_dict(orient="records"):
                # Attach to primary entity.
                primary_digits = _normalize_cnpj_digits(row.get(primary_col))
                if primary_digits:
                    entity_id = _entity_id_for_finding(finding_id=finding_id, primary_col=primary_col, cnpj_digits=primary_digits)
                    entity_catalog.setdefault(
                        entity_id,
                        Entity(
                            entity_id=entity_id,
                            entity_type=entity_id.split("_", 1)[0],
                            cnpj_digits=primary_digits,
                            name=None,
                            relationships=(),
                        ),
                    )
                    severity = definition.severity_rule(row) if definition else "MEDIUM"
                    metric = _metric_for_scheme(finding_id=finding_id, row=row)
                    add(
                        entity_id,
                        EvidenceItem(
                            finding_id=finding_id,
                            title=definition.title if definition else finding_id,
                            severity=severity,
                            metric=metric,
                            time_window="",
                            counterparties=_counterparties_for_scheme(finding_id=finding_id, row=row),
                            source_ref=source_ref,
                            record=_filter_record(row, definition) if definition else dict(row),
                        ),
                    )

                # Attach to involved funds where possible.
                if finding_id == "circular_flow":
                    for fund_col in ("CNPJ_FUNDO", "counterparty_cnpj"):
                        fund_digits = _normalize_cnpj_digits(row.get(fund_col))
                        if not fund_digits:
                            continue
                        fund_entity_id = f"FUND_{fund_digits}"
                        entity_catalog.setdefault(
                            fund_entity_id,
                            Entity(entity_id=fund_entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                        )
                        add(
                            fund_entity_id,
                            EvidenceItem(
                                finding_id=finding_id,
                                title=definition.title if definition else finding_id,
                                severity=definition.severity_rule(row) if definition else "MEDIUM",
                                metric=_metric_for_scheme(finding_id=finding_id, row=row),
                                time_window="",
                                counterparties=_counterparties_for_scheme(finding_id=finding_id, row=row),
                                source_ref=source_ref,
                                record=_filter_record(row, definition) if definition else dict(row),
                            ),
                        )

                if finding_id == "layered_funds":
                    for fund_col in ("holder_fund", "held_fund"):
                        fund_digits = _normalize_cnpj_digits(row.get(fund_col))
                        if not fund_digits:
                            continue
                        fund_entity_id = f"FUND_{fund_digits}"
                        entity_catalog.setdefault(
                            fund_entity_id,
                            Entity(entity_id=fund_entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                        )
                        add(
                            fund_entity_id,
                            EvidenceItem(
                                finding_id=finding_id,
                                title=definition.title if definition else finding_id,
                                severity=definition.severity_rule(row) if definition else "MEDIUM",
                                metric=_metric_for_scheme(finding_id=finding_id, row=row),
                                time_window="",
                                counterparties=_counterparties_for_scheme(finding_id=finding_id, row=row),
                                source_ref=source_ref,
                                record=_filter_record(row, definition) if definition else dict(row),
                            ),
                        )

        # Phantom assets by fund (if present)
        df = results.get("phantom_assets_by_fund")
        if df is not None and not df.empty:
            finding_id = "phantom_asset_exposure"
            definition = SIGNAL_REGISTRY[finding_id]
            source_ref = sources.get("phantom_assets_by_fund", "")
            for row in df.to_dict(orient="records"):
                fund_digits = _normalize_cnpj_digits(row.get("CNPJ_FUNDO"))
                if not fund_digits:
                    continue
                entity_id = f"FUND_{fund_digits}"
                entity_catalog.setdefault(
                    entity_id,
                    Entity(entity_id=entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                )
                metric = f"total_value_fund: {row.get('total_value_fund')}"
                add(
                    entity_id,
                    EvidenceItem(
                        finding_id=finding_id,
                        title=definition.title,
                        severity=definition.severity_rule(row),
                        metric=metric,
                        time_window="",
                        counterparties=str(row.get("asset_code", "")),
                        source_ref=source_ref,
                        record=_filter_record(row, definition),
                    ),
                )

        # --- New analyzers: fund-level signals ---
        # Where an analyzer emits several signal types into one table, list every
        # metric column it can populate. The first one this row filled wins.
        for key, finding_id, cnpj_col, metric_col in (
            ("quotaholder_anomalies", "quotaholder_anomaly", "CNPJ_FUNDO",
             ("pct_change", "per_capita_aum")),
            ("cost_basis_anomalies", "cost_basis_anomaly", "CNPJ_FUNDO", "gain_ratio"),
            ("reconciliation_gaps", "portfolio_reconciliation_gap", "CNPJ_FUNDO", "gap_pct"),
            ("lifecycle_anomalies", "fund_lifecycle_anomaly", "CNPJ_FUNDO",
             ("max_pl", "days_active")),
            ("window_dressing", "window_dressing", "CNPJ_FUNDO", "deviation_pct"),
            ("valuation_smoothing", "valuation_smoothing", "CNPJ_FUNDO",
             ("autocorrelation", "vol_ratio", "stale_days")),
        ):
            df = results.get(key)
            if df is None or df.empty:
                continue
            definition = SIGNAL_REGISTRY.get(finding_id)
            if not definition:
                continue
            source_ref = sources.get(key, "")
            for row in df.to_dict(orient="records"):
                fund_digits = _normalize_cnpj_digits(row.get(cnpj_col))
                if not fund_digits:
                    continue
                entity_id = f"FUND_{fund_digits}"
                entity_catalog.setdefault(
                    entity_id,
                    Entity(entity_id=entity_id, entity_type="FUND", cnpj_digits=fund_digits, name=None, relationships=()),
                )
                severity = definition.severity_rule(row)
                metric = _describe_metric(row, metric_col)
                date = row.get("DT_COMPTC")
                add(
                    entity_id,
                    EvidenceItem(
                        finding_id=finding_id,
                        title=definition.title,
                        severity=severity,
                        metric=metric,
                        time_window=_format_time_window(date, date),
                        counterparties="",
                        source_ref=source_ref,
                        record=_filter_record(row, definition),
                    ),
                )

        # --- New analyzers: manager network signals ---
        df = results.get("manager_network_anomalies")
        if df is not None and not df.empty:
            finding_id = "manager_network_anomaly"
            definition = SIGNAL_REGISTRY.get(finding_id)
            if definition:
                source_ref = sources.get("manager_network_anomalies", "")
                for row in df.to_dict(orient="records"):
                    gestor_digits = _normalize_cnpj_digits(row.get("CNPJ_GESTOR"))
                    if not gestor_digits:
                        continue
                    entity_id = f"MANAGER_{gestor_digits}"
                    entity_catalog.setdefault(
                        entity_id,
                        Entity(entity_id=entity_id, entity_type="MANAGER", cnpj_digits=gestor_digits, name=None, relationships=()),
                    )
                    severity = definition.severity_rule(row)
                    metric = f"num_admins: {row.get('num_admins')}, num_funds: {row.get('num_funds')}"
                    add(
                        entity_id,
                        EvidenceItem(
                            finding_id=finding_id,
                            title=definition.title,
                            severity=severity,
                            metric=metric,
                            time_window="",
                            counterparties="",
                            source_ref=source_ref,
                            record=_filter_record(row, definition),
                        ),
                    )

        # --- New analyzers: cross-fund issuer signals ---
        df = results.get("cross_fund_issuer")
        if df is not None and not df.empty:
            finding_id = "cross_fund_issuer"
            definition = SIGNAL_REGISTRY.get(finding_id)
            if definition:
                source_ref = sources.get("cross_fund_issuer", "")
                for row in df.to_dict(orient="records"):
                    admin_raw = row.get("captive_admin")
                    admin_digits = _normalize_cnpj_digits(admin_raw)
                    if admin_digits:
                        entity_id = f"ADMINISTRATOR_{admin_digits}"
                    else:
                        entity_id = f"ISSUER_{_stable_hash(str(row.get('EMISSOR', '')))}"
                    entity_catalog.setdefault(
                        entity_id,
                        Entity(
                            entity_id=entity_id,
                            entity_type=entity_id.split("_", 1)[0],
                            cnpj_digits=admin_digits,
                            name=None,
                            relationships=(),
                        ),
                    )
                    severity = definition.severity_rule(row)
                    # Only some of this analyzer's signal types have an exposure
                    # to report; a name-similarity cluster's metric is how alike
                    # the two names are.
                    metric = _describe_metric(
                        row, ("total_exposure", "similarity", "num_funds")
                    )
                    add(
                        entity_id,
                        EvidenceItem(
                            finding_id=finding_id,
                            title=definition.title,
                            severity=severity,
                            metric=metric,
                            time_window="",
                            counterparties=str(row.get("EMISSOR", "")),
                            source_ref=source_ref,
                            record=_filter_record(row, definition),
                        ),
                    )

        # Generate charts for fund entities (best-effort) when informe_df is present.
        if informe_df is not None and not informe_df.empty:
            for entity_id, entity in entity_catalog.items():
                if entity.entity_type != "FUND" or not entity.cnpj_digits:
                    continue
                if entity_id not in evidence_by_entity:
                    continue
                prefix = f"{entity_id}"
                render_fund_timeseries_charts(
                    informe_df=informe_df,
                    fund_cnpj=entity.cnpj_digits,
                    output_dir=assets_dir,
                    prefix=prefix,
                )

        # Mermaid diagrams for circular flow findings (deterministic source only).
        df = results.get("circular_flow")
        if df is not None and not df.empty:
            for idx, row in enumerate(df.to_dict(orient="records"), start=1):
                diagram = build_circular_flow_mermaid(row)
                filename = write_mermaid_diagram(
                    mermaid_source=diagram,
                    output_path=assets_dir / f"circular_flow_{idx}.mmd",
                )
                # Attach the mermaid reference to the admin entity if possible.
                admin_digits = _normalize_cnpj_digits(row.get("admin_cnpj"))
                if not admin_digits:
                    continue
                admin_entity_id = f"ADMINISTRATOR_{admin_digits}"
                evidence_by_entity.setdefault(admin_entity_id, []).append(
                    EvidenceItem(
                        finding_id="circular_flow",
                        title="Circularity diagram (Mermaid)",
                        severity="LOW",
                        metric="diagram",
                        time_window="",
                        counterparties="",
                        source_ref=str(Path("assets") / filename),
                        record={"mermaid_file": filename},
                    )
                )

        return evidence_by_entity

    def _overall_severity(self, items: Iterable[EvidenceItem]) -> str:
        best = "LOW"
        for item in items:
            if SEVERITY_RANK.get(item.severity, 0) > SEVERITY_RANK.get(best, 0):
                best = item.severity
        return best

    def _top_evidence(self, items: list[EvidenceItem], top_n: int) -> list[EvidenceItem]:
        items_sorted = sorted(
            items,
            key=lambda it: (
                SEVERITY_RANK.get(it.severity, 0),
                _metric_sort_value(it.metric),
            ),
            reverse=True,
        )
        return items_sorted[:top_n]

    def _find_charts_for_entity(self, *, assets_dir: Path, entity: Entity) -> FundChartOutputs | None:
        if entity.entity_type != "FUND" or not entity.cnpj_digits:
            return None
        prefix = f"FUND_{entity.cnpj_digits}"
        flow = assets_dir / f"{prefix}_flow.png"
        pl = assets_dir / f"{prefix}_pl.png"
        quota = assets_dir / f"{prefix}_quota.png"
        if not any(p.exists() for p in (flow, pl, quota)):
            return None
        return FundChartOutputs(
            flow_png=flow.name if flow.exists() else None,
            pl_png=pl.name if pl.exists() else None,
            quota_png=quota.name if quota.exists() else None,
        )

    def _write_entity_outputs(
        self,
        *,
        entity: Entity,
        evidence_items: list[EvidenceItem],
        output_dir: Path,
        output_root: Path,
        charts: FundChartOutputs | None,
        context: dict[str, Any] | None,
        explain_format: str,
    ) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        evidence_payload = {
            "entity": {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "cnpj_digits": entity.cnpj_digits,
                "name": entity.name,
                "relationships": list(entity.relationships),
            },
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "disclaimer": [
                "Automated red flags are not proof of wrongdoing.",
                "Findings are prioritized leads requiring corroboration.",
            ],
            "evidence": [
                {
                    "finding_id": item.finding_id,
                    "title": item.title,
                    "severity": item.severity,
                    "metric": item.metric,
                    "time_window": item.time_window,
                    "counterparties": item.counterparties,
                    "source_ref": item.source_ref,
                    "record": item.record,
                }
                for item in evidence_items
            ],
            "context": context or None,
        }
        # default=str so pandas Timestamps and NA survive serialization. Real
        # CVM dates parse to Timestamp, which json cannot encode; the synthetic
        # fixtures carried plain strings and so never hit this.
        (output_dir / "evidence.json").write_text(
            json.dumps(evidence_payload, indent=2, default=str), encoding="utf-8"
        )

        markdown = self._render_markdown(entity=entity, evidence_items=evidence_items, context=context)
        html_doc = self._render_html(entity=entity, evidence_items=evidence_items, context=context, charts=charts)

        normalized = explain_format.strip().lower()
        if normalized in {"md", "markdown", "both"}:
            (output_dir / "brief.md").write_text(markdown, encoding="utf-8")
        if normalized in {"html", "both"}:
            (output_dir / "brief.html").write_text(html_doc, encoding="utf-8")

    def _render_markdown(self, *, entity: Entity, evidence_items: list[EvidenceItem], context: dict[str, Any] | None) -> str:
        disclaimer = (
            "Automated red flags are not proof of wrongdoing.\n"
            "Findings are prioritized leads requiring corroboration.\n"
        )
        lines = [f"# Investigation Brief: {entity.entity_id}", "", disclaimer, ""]

        lines.append("## Who is this entity?")
        lines.append(f"- **Type:** {entity.entity_type}")
        if entity.cnpj_digits:
            lines.append(f"- **CNPJ (digits):** {entity.cnpj_digits}")
        if entity.name:
            lines.append(f"- **Name:** {entity.name}")
        if entity.relationships:
            lines.append("- **Known relationships:**")
            for rel in entity.relationships:
                lines.append(f"  - {rel}")
        lines.append("")

        lines.append("## Why it was flagged (plain English)")
        for item in evidence_items:
            lines.append(f"- **{item.title}** ({item.severity}): {item.metric}")
        lines.append("")

        lines.append("## Strongest evidence")
        lines.append("| Signal | Severity | Metric | Time window | Counterparties | Source |")
        lines.append("|---|---:|---|---|---|---|")
        for item in evidence_items:
            lines.append(
                f"| {item.title} | {item.severity} | {item.metric} | {item.time_window} | {item.counterparties} | {item.source_ref} |"
            )
        lines.append("")

        lines.append("## What this could also be (caveats)")
        caveats = self._collect_caveats(evidence_items)
        for cav in caveats:
            lines.append(f"- {cav}")
        lines.append("")

        lines.append("## Recommended next steps")
        steps = self._collect_next_steps(evidence_items)
        lines.append("### Immediate (48h)")
        for step in steps["immediate"]:
            lines.append(f"- {step}")
        lines.append("")
        lines.append("### Short term (2 weeks)")
        for step in steps["short_term"]:
            lines.append(f"- {step}")
        lines.append("")
        lines.append("### Longer term (60 days)")
        for step in steps["long_term"]:
            lines.append(f"- {step}")
        lines.append("")

        lines.append("## Context from public sources")
        if context and context.get("available"):
            lines.append(context.get("overview", "").strip())
            lines.append("")
            citations = context.get("citations", [])
            if citations:
                lines.append("### Citations")
                for c in citations:
                    lines.append(f"- {c.get('title', '')} ({c.get('published_date', '')}): {c.get('url', '')}")
                lines.append("")
            timeline = context.get("timeline", [])
            if timeline:
                lines.append("### Timeline")
                for t in timeline:
                    lines.append(f"- {t.get('date', '')}: {t.get('title', '')}")
                lines.append("")
        else:
            lines.append("Context not collected (API key missing or enrichment disabled).")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _render_html(
        self,
        *,
        entity: Entity,
        evidence_items: list[EvidenceItem],
        context: dict[str, Any] | None,
        charts: FundChartOutputs | None,
    ) -> str:
        def esc(text: Any) -> str:
            return html.escape("" if text is None else str(text))

        evidence_rows = []
        for item in evidence_items:
            evidence_rows.append(
                "<tr>"
                f"<td>{esc(item.title)}</td>"
                f"<td>{esc(item.severity)}</td>"
                f"<td>{esc(item.metric)}</td>"
                f"<td>{esc(item.time_window)}</td>"
                f"<td>{esc(item.counterparties)}</td>"
                f"<td><code>{esc(item.source_ref)}</code></td>"
                "</tr>"
            )
        evidence_table = (
            "<table><thead><tr>"
            "<th>Signal</th><th>Severity</th><th>Metric</th><th>Time window</th><th>Counterparties</th><th>Source</th>"
            "</tr></thead><tbody>"
            + "".join(evidence_rows)
            + "</tbody></table>"
        )

        rels = "".join(f"<li>{esc(r)}</li>" for r in entity.relationships) if entity.relationships else ""
        caveats = "".join(f"<li>{esc(c)}</li>" for c in self._collect_caveats(evidence_items))
        steps = self._collect_next_steps(evidence_items)
        steps_48h = "".join(f"<li>{esc(s)}</li>" for s in steps["immediate"])
        steps_2w = "".join(f"<li>{esc(s)}</li>" for s in steps["short_term"])
        steps_60d = "".join(f"<li>{esc(s)}</li>" for s in steps["long_term"])

        charts_html = ""
        if charts:
            img_tags = []
            for label, filename in (
                ("Net flow", charts.flow_png),
                ("AUM/PL", charts.pl_png),
                ("Quota", charts.quota_png),
            ):
                if filename:
                    # entities/<id>/brief.html -> ../../assets/<file>
                    img_tags.append(
                        f"<div class='chart'><div class='chart-title'>{esc(label)}</div>"
                        f"<img src='../../assets/{esc(filename)}' alt='{esc(label)} chart' /></div>"
                    )
            if img_tags:
                charts_html = "<h2>Visuals</h2><div class='charts'>" + "".join(img_tags) + "</div>"

        context_html = "<h2>Context from public sources</h2>"
        if context and context.get("available"):
            context_html += f"<p>{esc(context.get('overview', ''))}</p>"
            citations = context.get("citations", [])
            if citations:
                context_html += "<h3>Citations</h3><ul>"
                for c in citations:
                    context_html += (
                        "<li>"
                        f"<a href='{esc(c.get('url', ''))}'>{esc(c.get('title', ''))}</a>"
                        f" <span class='muted'>({esc(c.get('published_date', ''))})</span>"
                        "</li>"
                    )
                context_html += "</ul>"
            timeline = context.get("timeline", [])
            if timeline:
                context_html += "<h3>Timeline</h3><ul>"
                for t in timeline:
                    context_html += f"<li><span class='muted'>{esc(t.get('date', ''))}</span> — {esc(t.get('title', ''))}</li>"
                context_html += "</ul>"
        else:
            context_html += "<p class='muted'>Context not collected (API key missing or enrichment disabled).</p>"

        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Investigation Brief: {esc(entity.entity_id)}</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; line-height: 1.5; }}
      .muted {{ color: #666; }}
      .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; background: #f1f5f9; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.5rem; vertical-align: top; text-align: left; }}
      th {{ background: #f8fafc; }}
      code {{ background: #f1f5f9; padding: 0.1rem 0.25rem; border-radius: 6px; }}
      .charts {{ display: grid; grid-template-columns: 1fr; gap: 1rem; }}
      .chart img {{ max-width: 100%; border: 1px solid #e5e7eb; border-radius: 10px; }}
      .chart-title {{ font-weight: 600; margin-bottom: 0.25rem; }}
      .disclaimer {{ border-left: 4px solid #f59e0b; padding-left: 0.75rem; }}
    </style>
  </head>
  <body>
    <h1>Investigation Brief: {esc(entity.entity_id)}</h1>
    <p class="disclaimer">
      Automated red flags are not proof of wrongdoing.<br/>
      Findings are prioritized leads requiring corroboration.
    </p>

    <h2>Who is this entity?</h2>
    <ul>
      <li><strong>Type:</strong> {esc(entity.entity_type)}</li>
      {f"<li><strong>CNPJ (digits):</strong> {esc(entity.cnpj_digits)}</li>" if entity.cnpj_digits else ""}
      {f"<li><strong>Name:</strong> {esc(entity.name)}</li>" if entity.name else ""}
      {f"<li><strong>Known relationships:</strong><ul>{rels}</ul></li>" if rels else ""}
    </ul>

    {charts_html}

    <h2>Why it was flagged (plain English)</h2>
    <ul>
      {''.join(f"<li><strong>{esc(it.title)}</strong> ({esc(it.severity)}): {esc(it.metric)}</li>" for it in evidence_items)}
    </ul>

    <h2>Strongest evidence</h2>
    {evidence_table}

    <h2>What this could also be (caveats)</h2>
    <ul>{caveats}</ul>

    <h2>Recommended next steps</h2>
    <h3>Immediate (48h)</h3>
    <ul>{steps_48h}</ul>
    <h3>Short term (2 weeks)</h3>
    <ul>{steps_2w}</ul>
    <h3>Longer term (60 days)</h3>
    <ul>{steps_60d}</ul>

    {context_html}
  </body>
</html>
"""

    def _collect_caveats(self, evidence_items: list[EvidenceItem]) -> list[str]:
        caveats: list[str] = [
            "Automated red flags are not proof of wrongdoing.",
            "Public datasets may not include investor identity, transaction routing, or full valuation documentation.",
        ]
        seen: set[str] = set(caveats)
        for item in evidence_items:
            definition = SIGNAL_REGISTRY.get(item.finding_id)
            if not definition:
                continue
            for cav in definition.caveats:
                if cav not in seen:
                    caveats.append(cav)
                    seen.add(cav)
        return caveats

    def _collect_next_steps(self, evidence_items: list[EvidenceItem]) -> dict[str, list[str]]:
        immediate: list[str] = []
        short_term: list[str] = []
        long_term: list[str] = []

        def add_unique(target: list[str], value: str) -> None:
            if value not in target:
                target.append(value)

        # Start with generic actions.
        add_unique(immediate, "Confirm the data inputs and rerun the pipeline to ensure reproducibility.")
        add_unique(immediate, "Pull the raw source files for the flagged dates/assets and verify column mappings.")

        for item in evidence_items:
            definition = SIGNAL_REGISTRY.get(item.finding_id)
            if not definition:
                continue
            for step in definition.next_steps:
                # Simple triage split: first 1–2 steps go to immediate, rest short-term.
                add_unique(immediate, step)

        add_unique(short_term, "Perform counterparty-level tracing (bank transfers, distributor orders, investor IDs) for flagged windows.")
        add_unique(short_term, "Validate pricing sources and custody statements for high-impact assets.")

        add_unique(long_term, "Review governance: valuation committees, related-party policies, and audit trails for repeated patterns.")
        add_unique(long_term, "Establish ongoing monitoring with thresholds and alerting tied to these detectors.")

        # Keep them short and 1-page friendly.
        return {
            "immediate": immediate[:6],
            "short_term": short_term[:5],
            "long_term": long_term[:4],
        }

    def _write_global_report(self, *, output_path: Path, run_id: str, summary_df: pd.DataFrame) -> None:
        def esc(value: Any) -> str:
            return html.escape("" if value is None else str(value))

        rows = []
        for row in summary_df.itertuples(index=False):
            entity_id = row.entity_id
            link = f"entities/{esc(entity_id)}/brief.html"
            rows.append(
                "<tr>"
                f"<td><a href='{link}'>{esc(entity_id)}</a></td>"
                f"<td>{esc(row.entity_type)}</td>"
                f"<td>{esc(row.overall_severity)}</td>"
                f"<td>{esc(row.evidence_count)}</td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr>"
            "<th>Entity</th><th>Type</th><th>Severity</th><th>Evidence count</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
        output_path.write_text(
            f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Investigation Report: {esc(run_id)}</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; line-height: 1.5; }}
      .muted {{ color: #666; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.5rem; text-align: left; }}
      th {{ background: #f8fafc; }}
      .disclaimer {{ border-left: 4px solid #f59e0b; padding-left: 0.75rem; }}
    </style>
  </head>
  <body>
    <h1>Investigation Report</h1>
    <p class="muted">Run: {esc(run_id)}</p>
    <p class="disclaimer">
      Automated red flags are not proof of wrongdoing.<br/>
      Findings are prioritized leads requiring corroboration.
    </p>
    <h2>Top flagged entities</h2>
    {table}
  </body>
</html>
""",
            encoding="utf-8",
        )


def _pick_column(columns: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    cols = set(columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def _describe_metric(row: dict[str, Any], candidates: str | tuple[str, ...]) -> str:
    """Name the metric that actually carries a value for this row.

    Several analyzers write more than one signal type into one findings table,
    each with its own metric column and nothing in the others. Naming a fixed
    column therefore labels part of the table with a blank: on a real CVM month
    it produced "autocorrelation: nan" on every low_volatility_ratio finding,
    which tells the reader nothing and reads as a broken detector. Take the
    first candidate this row actually populated instead.
    """
    if isinstance(candidates, str):
        candidates = (candidates,)

    for column in candidates:
        if column not in row:
            continue
        value = row[column]
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass  # Arrays and other non-scalars are values, not blanks.
        return f"{column}: {_format_metric_value(value)}"

    return f"{candidates[0]}: n/a"


def _format_metric_value(value: Any) -> str:
    """Render a metric for a human without dumping full float precision.

    No thousands separators: `_metric_sort_value` splits on commas to read
    multi-part metrics, so a grouped number would sort by its last three
    digits.
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        return str(value)
    if isinstance(value, numbers.Integral):
        return str(int(value))
    number = float(value)
    return f"{number:.2f}" if abs(number) >= 1000 else f"{number:.4g}"


def _filter_record(row: dict[str, Any], definition: SignalDefinition | None) -> dict[str, Any]:
    if not definition or not definition.evidence_fields:
        return dict(row)
    result: dict[str, Any] = {}
    for key in definition.evidence_fields:
        if key in row:
            result[key] = row[key]
    return result


def _format_time_window(start: Any, end: Any) -> str:
    if start is None and end is None:
        return ""
    if start == end:
        return str(start)
    return f"{start} → {end}"


def _metric_sort_value(metric: str) -> float:
    # Extract last number in string, best-effort.
    parts = str(metric).replace(",", " ").split()
    for token in reversed(parts):
        try:
            return abs(float(token))
        except ValueError:
            continue
    return 0.0


def _entity_id_for_finding(*, finding_id: str, primary_col: str, cnpj_digits: str) -> str:
    if primary_col == "admin_cnpj":
        return f"ADMINISTRATOR_{cnpj_digits}"
    if primary_col in {"fund_cnpj", "CNPJ_FUNDO"}:
        return f"FUND_{cnpj_digits}"
    # Fallback by finding type.
    if finding_id in {"shell_network"}:
        return f"ADMINISTRATOR_{cnpj_digits}"
    return f"ENTITY_{cnpj_digits}"


def _metric_for_scheme(*, finding_id: str, row: dict[str, Any]) -> str:
    if finding_id == "circular_flow":
        return f"total_value: {row.get('total_value')}"
    if finding_id == "layered_funds":
        return f"investment_value: {row.get('investment_value')}"
    if finding_id == "asset_inflation":
        return f"illiquid_pct: {row.get('illiquid_pct')}, avg_daily_return: {row.get('avg_daily_return')}"
    if finding_id == "shell_network":
        return f"num_suspicious_issuers: {row.get('num_suspicious_issuers')}"
    return ""


def _counterparties_for_scheme(*, finding_id: str, row: dict[str, Any]) -> str:
    if finding_id == "circular_flow":
        parts = []
        for col in ("CNPJ_FUNDO", "counterparty_cnpj"):
            if row.get(col):
                parts.append(str(row.get(col)))
        return ", ".join(parts)
    if finding_id == "layered_funds":
        parts = []
        for col in ("holder_fund", "held_fund"):
            if row.get(col):
                parts.append(str(row.get(col)))
        return ", ".join(parts)
    return ""

