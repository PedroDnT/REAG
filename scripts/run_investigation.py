#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import Config
from src.analyzers.anomaly_detector import AnomalyDetector
from src.analyzers.cost_basis_analyzer import CostBasisAnalyzer
from src.analyzers.cross_fund_issuer import CrossFundIssuerAnalyzer
from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
from src.analyzers.fraud_schemes import FraudSchemeDetector
from src.analyzers.fund_lifecycle import FundLifecycleAnalyzer
from src.analyzers.manager_network import ManagerNetworkAnalyzer
from src.analyzers.portfolio_reconciliation import PortfolioReconciliationAnalyzer
from src.analyzers.quotaholder_analyzer import QuotaholderAnalyzer
from src.analyzers.valuation_smoothing import ValuationSmoothingAnalyzer
from src.analyzers.window_dressing import WindowDressingDetector
from src.enrichment.context_writer import build_context_section
from src.enrichment.exa_provider import ExaProvider
from src.enrichment.interfaces import SearchResult
from src.explain.explainer import Explainer
from src.processors.data_processor import DataProcessor

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def sanitize_run_id(run_id: str) -> str:
    """Return *run_id* if it matches the safe pattern, otherwise a timestamp fallback.

    Rejects absolute paths, path-traversal segments, and any characters that
    could affect file-system placement when used as a directory component.

    Parameters
    ----------
    run_id:
        The candidate run identifier supplied by the user.

    Returns
    -------
    str
        *run_id* unchanged when it matches ``^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$``;
        otherwise a ``%Y%m%d_%H%M%S`` timestamp string.
    """
    if _RUN_ID_RE.match(run_id):
        return run_id
    return datetime.now().strftime("%Y%m%d_%H%M%S")


ANALYSIS_CHOICES = (
    "flow",
    "schemes",
    "phantom_assets",
    "quotaholder",
    "cost_basis",
    "reconciliation",
    "lifecycle",
    "manager_network",
    "window_dressing",
    "valuation_smoothing",
    "cross_fund_issuer",
)


@dataclass(frozen=True)
class LoadedData:
    cadastro: pd.DataFrame | None
    informe: pd.DataFrame | None
    cda: pd.DataFrame | None


def run_investigation(args: argparse.Namespace) -> int:
    config = Config()
    selected_analyses = _selected_analyses(args.analysis)

    run_id = sanitize_run_id(args.run_id) if args.run_id else datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else (config.REPORTS_DIR / "investigation" / run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = DataProcessor(config)
    loaded = _load_data(args=args, config=config, processor=processor)

    results: dict[str, pd.DataFrame] = {}
    sources: dict[str, str] = {}

    findings_dir = output_dir / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)

    # --- Core detectors (public-data based) ---
    if "flow" in selected_analyses and loaded.informe is not None and not loaded.informe.empty:
        informe = loaded.informe.copy()
        informe = processor.calculate_net_flow(informe)

        anomaly_detector = AnomalyDetector(config=config)
        anomaly_report = anomaly_detector.generate_anomaly_report(informe, cda_df=loaded.cda)
        for key, df in anomaly_report.items():
            results[key] = df
            sources[key] = _save_finding(df, findings_dir / f"{key}.csv")

        # Divergences come from the anomaly report as well.
        if "divergences" in results:
            pass

    if (
        "schemes" in selected_analyses
        and loaded.cda is not None
        and not loaded.cda.empty
        and loaded.cadastro is not None
        and not loaded.cadastro.empty
        and loaded.informe is not None
        and not loaded.informe.empty
    ):
        cda = _normalize_cda_columns(loaded.cda)

        scheme_detector = FraudSchemeDetector()
        schemes = scheme_detector.generate_fraud_scheme_report(
            informe_df=loaded.informe,
            cda_df=cda,
            cadastro_df=loaded.cadastro,
            output_path=None,
        )
        # Normalize scheme keys to match explainer expectations.
        scheme_key_map = {
            "circular_flow": "circular_flow",
            "layered_funds": "layered_funds",
            "asset_inflation": "asset_inflation",
            "shell_networks": "shell_networks",
        }
        for raw_key, df in schemes.items():
            key = scheme_key_map.get(raw_key, raw_key)
            results[key] = df
            sources[key] = _save_finding(df, findings_dir / f"{key}.csv")

    if "phantom_assets" in selected_analyses and loaded.cda is not None and not loaded.cda.empty:
        cda = _normalize_cda_columns(loaded.cda)
        phantom = EnhancedPhantomAssetDetector(cache_dir=Path("data/cache"))
        # Best-effort: load valid funds list when cadastro file exists on disk.
        if args.cadastro and Path(args.cadastro).exists():
            try:
                phantom.load_funds_from_cadastro(Path(args.cadastro))
            except Exception:
                pass
        phantom.update_registries()
        phantom_assets = phantom.detect_enhanced_phantom_assets(cda)
        results["phantom_assets"] = phantom_assets
        sources["phantom_assets"] = _save_finding(phantom_assets, findings_dir / "phantom_assets.csv")

        phantom_by_fund = _phantom_assets_by_fund(cda_df=cda, phantom_assets=phantom_assets)
        results["phantom_assets_by_fund"] = phantom_by_fund
        sources["phantom_assets_by_fund"] = _save_finding(phantom_by_fund, findings_dir / "phantom_assets_by_fund.csv")

    # --- New analyzers ---

    # Quotaholder analysis (needs informe with NR_COTST)
    if (
        "quotaholder" in selected_analyses
        and loaded.informe is not None
        and not loaded.informe.empty
        and "NR_COTST" in loaded.informe.columns
    ):
        try:
            quotaholder = QuotaholderAnalyzer(config=config)
            qh_results = quotaholder.analyze(loaded.informe, cadastro_df=loaded.cadastro)
            results["quotaholder_anomalies"] = qh_results
            sources["quotaholder_anomalies"] = _save_finding(qh_results, findings_dir / "quotaholder_anomalies.csv")
        except Exception:
            pass

    # Cost basis analysis (needs cda with VL_CUSTO_POS_FINAL)
    if (
        "cost_basis" in selected_analyses
        and loaded.cda is not None
        and not loaded.cda.empty
        and "VL_CUSTO_POS_FINAL" in loaded.cda.columns
    ):
        try:
            cda = _normalize_cda_columns(loaded.cda)
            cost_basis = CostBasisAnalyzer(config=config)
            cb_results = cost_basis.analyze(cda)
            results["cost_basis_anomalies"] = cb_results
            sources["cost_basis_anomalies"] = _save_finding(cb_results, findings_dir / "cost_basis_anomalies.csv")
        except Exception:
            pass

    # Portfolio reconciliation (needs cda + informe)
    if (
        "reconciliation" in selected_analyses
        and loaded.cda is not None
        and not loaded.cda.empty
        and loaded.informe is not None
        and not loaded.informe.empty
    ):
        try:
            cda = _normalize_cda_columns(loaded.cda)
            recon = PortfolioReconciliationAnalyzer(config=config)
            recon_results = recon.analyze(cda, loaded.informe)
            results["reconciliation_gaps"] = recon_results
            sources["reconciliation_gaps"] = _save_finding(recon_results, findings_dir / "reconciliation_gaps.csv")
        except Exception:
            pass

    # Fund lifecycle analysis (needs cadastro)
    if (
        "lifecycle" in selected_analyses
        and loaded.cadastro is not None
        and not loaded.cadastro.empty
        and "DT_CONST" in loaded.cadastro.columns
    ):
        try:
            lifecycle = FundLifecycleAnalyzer(config=config)
            lc_results = lifecycle.analyze(loaded.cadastro, informe_df=loaded.informe)
            results["lifecycle_anomalies"] = lc_results
            sources["lifecycle_anomalies"] = _save_finding(lc_results, findings_dir / "lifecycle_anomalies.csv")
        except Exception:
            pass

    # Manager network analysis (needs cadastro with CNPJ_GESTOR)
    if (
        "manager_network" in selected_analyses
        and loaded.cadastro is not None
        and not loaded.cadastro.empty
        and "CNPJ_GESTOR" in loaded.cadastro.columns
    ):
        try:
            manager_net = ManagerNetworkAnalyzer(config=config)
            mn_results = manager_net.analyze(
                loaded.cadastro,
                cda_df=_normalize_cda_columns(loaded.cda) if loaded.cda is not None and not loaded.cda.empty else None,
                informe_df=loaded.informe,
            )
            results["manager_network_anomalies"] = mn_results
            sources["manager_network_anomalies"] = _save_finding(mn_results, findings_dir / "manager_network_anomalies.csv")
        except Exception:
            pass

    # Window dressing (needs informe with VL_QUOTA)
    if (
        "window_dressing" in selected_analyses
        and loaded.informe is not None
        and not loaded.informe.empty
        and "VL_QUOTA" in loaded.informe.columns
    ):
        try:
            wd = WindowDressingDetector(config=config)
            wd_results = wd.analyze(loaded.informe)
            results["window_dressing"] = wd_results
            sources["window_dressing"] = _save_finding(wd_results, findings_dir / "window_dressing.csv")
        except Exception:
            pass

    # Valuation smoothing (needs informe with VL_QUOTA)
    if (
        "valuation_smoothing" in selected_analyses
        and loaded.informe is not None
        and not loaded.informe.empty
        and "VL_QUOTA" in loaded.informe.columns
    ):
        try:
            vs = ValuationSmoothingAnalyzer(config=config)
            vs_results = vs.analyze(loaded.informe)
            results["valuation_smoothing"] = vs_results
            sources["valuation_smoothing"] = _save_finding(vs_results, findings_dir / "valuation_smoothing.csv")
        except Exception:
            pass

    # Cross-fund issuer analysis (needs cda + cadastro)
    if (
        "cross_fund_issuer" in selected_analyses
        and loaded.cda is not None
        and not loaded.cda.empty
        and loaded.cadastro is not None
        and not loaded.cadastro.empty
    ):
        try:
            cda = _normalize_cda_columns(loaded.cda)
            cfi = CrossFundIssuerAnalyzer(config=config)
            cfi_results = cfi.analyze(cda, loaded.cadastro)
            results["cross_fund_issuer"] = cfi_results
            sources["cross_fund_issuer"] = _save_finding(cfi_results, findings_dir / "cross_fund_issuer.csv")
        except Exception:
            pass

    _write_run_metadata(
        output_dir=output_dir,
        run_id=run_id,
        args=args,
        results=results,
        sources=sources,
    )

    if not args.explain:
        return 0

    contexts_by_entity_id: dict[str, dict[str, Any]] = {}
    if args.enable_enrichment:
        contexts_by_entity_id = _run_context_enrichment(
            run_id=run_id,
            results=results,
            cadastro_df=loaded.cadastro,
            explain_max_entities=args.explain_max_entities,
            max_results=args.enrichment_max_results,
            since_days=args.enrichment_since_days,
            provider_name=args.enrichment_provider,
        )

    explainer = Explainer()
    explainer.generate(
        results=results,
        output_dir=output_dir,
        informe_df=loaded.informe,
        cadastro_df=loaded.cadastro,
        sources=sources,
        contexts_by_entity_id=contexts_by_entity_id,
        explain_max_entities=args.explain_max_entities,
        explain_top_findings=args.explain_top_findings,
        explain_format=args.explain_format,
    )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a REAG investigation and generate human-readable briefs.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier (defaults to timestamp).")
    parser.add_argument("--output-dir", default=None, help="Output directory (defaults to reports/investigation/<run_id>).")

    parser.add_argument("--public-data-dir", default="data/raw", help="Base directory for public/raw data inputs.")
    parser.add_argument("--processed-data-dir", default="data/processed", help="Base directory for processed data inputs.")

    parser.add_argument("--cadastro", default=None, help="Path to cadastro CSV (cad_fi*.csv).")
    parser.add_argument("--informe", default=None, help="Path to informe CSV or processed file.")
    parser.add_argument("--cda", default=None, help="Path to CDA CSV.")

    parser.add_argument("--explain", action=argparse.BooleanOptionalAction, default=True, help="Generate per-entity briefs.")
    parser.add_argument("--explain-max-entities", type=int, default=200, help="Maximum number of entity briefs.")
    parser.add_argument("--explain-top-findings", type=int, default=6, help="Max evidence rows per brief.")
    parser.add_argument(
        "--explain-format",
        choices=["html", "md", "both"],
        default="both",
        help="Which formats to generate for briefs.",
    )
    parser.add_argument(
        "--analysis",
        nargs="+",
        choices=[*ANALYSIS_CHOICES, "all"],
        default=["all"],
        help="Which investigation modules to run. Defaults to all modules.",
    )

    parser.add_argument("--enable-enrichment", action="store_true", help="Enable external context enrichment (Exa first).")
    parser.add_argument("--enrichment-provider", choices=["exa", "perplexity"], default="exa", help="Enrichment provider.")
    parser.add_argument("--enrichment-since-days", type=int, default=365, help="How far back to search.")
    parser.add_argument("--enrichment-max-results", type=int, default=8, help="Maximum results per query.")

    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _selected_analyses(values: list[str] | None) -> set[str]:
    selected = set(values or ["all"])
    if "all" in selected:
        return set(ANALYSIS_CHOICES)
    return selected


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the investigation pipeline."""
    args = _parse_args(argv)
    return run_investigation(args)


def _load_data(*, args: argparse.Namespace, config: Config, processor: DataProcessor) -> LoadedData:
    cadastro = None
    informe = None
    cda = None

    if args.cadastro:
        cadastro = processor.read_cadastro(Path(args.cadastro))
    else:
        maybe = _find_first(Path(args.public_data_dir), patterns=("cad_fi*.csv",))
        if maybe:
            cadastro = processor.read_cadastro(maybe)

    if args.informe:
        informe = _read_informe_any(Path(args.informe), processor=processor)
    else:
        processed_path = Path(args.processed_data_dir) / "reag_informe_diario_processed.csv"
        if processed_path.exists():
            informe = pd.read_csv(processed_path, sep=";", parse_dates=["DT_COMPTC"])
        else:
            maybe = _find_first(Path(args.public_data_dir), patterns=("inf_diario_fi_*.csv",))
            if maybe:
                informe = processor.read_informe_diario(maybe)

    if args.cda:
        cda = _read_cda_any(Path(args.cda), processor=processor)
    else:
        maybe = _find_first(Path(args.public_data_dir), patterns=("cda_fi_*.csv",))
        if maybe:
            cda = processor.read_cda(maybe)

    return LoadedData(cadastro=cadastro, informe=informe, cda=cda)


def _read_informe_any(path: Path, *, processor: DataProcessor) -> pd.DataFrame:
    if path.is_dir():
        files = sorted(path.glob("inf_diario_fi_*.csv"))
        if not files:
            return pd.DataFrame()
        dfs = [processor.read_informe_diario(p) for p in files[:24]]  # safety cap
        return pd.concat([df for df in dfs if not df.empty], ignore_index=True) if dfs else pd.DataFrame()
    # Heuristic: processed files are saved with ';'
    if path.name.endswith("_processed.csv"):
        return pd.read_csv(path, sep=";", parse_dates=["DT_COMPTC"])
    return processor.read_informe_diario(path)


def _read_cda_any(path: Path, *, processor: DataProcessor) -> pd.DataFrame:
    if path.is_dir():
        files = sorted(path.glob("cda_fi_*.csv"))
        if not files:
            return pd.DataFrame()
        dfs = [processor.read_cda(p) for p in files[:12]]  # safety cap
        return pd.concat([df for df in dfs if not df.empty], ignore_index=True) if dfs else pd.DataFrame()
    return processor.read_cda(path)


def _find_first(base_dir: Path, *, patterns: tuple[str, ...]) -> Path | None:
    if not base_dir.exists():
        return None
    candidates = []
    for pattern in patterns:
        candidates.extend(base_dir.glob(pattern))
        candidates.extend((base_dir / "cadastro").glob(pattern))
        candidates.extend((base_dir / "informe").glob(pattern))
        candidates.extend((base_dir / "cda").glob(pattern))
    return candidates[0] if candidates else None


def _normalize_cda_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "VL_MERCADO" not in df.columns and "VL_MERC_POS_FINAL" in df.columns:
        df["VL_MERCADO"] = df["VL_MERC_POS_FINAL"]
    return df


def _phantom_assets_by_fund(*, cda_df: pd.DataFrame, phantom_assets: pd.DataFrame) -> pd.DataFrame:
    if phantom_assets is None or phantom_assets.empty:
        return pd.DataFrame()
    if cda_df is None or cda_df.empty:
        return pd.DataFrame()
    if "CNPJ_FUNDO" not in cda_df.columns or "CD_ATIVO" not in cda_df.columns:
        return pd.DataFrame()
    flagged_assets = set(phantom_assets["asset_code"].astype(str).tolist())
    df = cda_df[cda_df["CD_ATIVO"].astype(str).isin(flagged_assets)].copy()
    if df.empty:
        return pd.DataFrame()

    # Aggregate per fund & asset.
    value_col = "VL_MERCADO" if "VL_MERCADO" in df.columns else None
    agg: dict[str, Any] = {}
    if value_col:
        agg["total_value_fund"] = (value_col, "sum")
    grouped = df.groupby(["CNPJ_FUNDO", "CD_ATIVO"]).agg(**agg).reset_index()
    grouped = grouped.rename(columns={"CD_ATIVO": "asset_code"})

    # Join risk/status/type from phantom_assets.
    risk_cols = ["asset_code", "asset_type", "status", "fraud_risk", "confidence", "issuer", "red_flags", "reason"]
    meta = phantom_assets[risk_cols].copy()
    return grouped.merge(meta, on="asset_code", how="left")


def _save_finding(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df is None:
        df = pd.DataFrame()
    df.to_csv(path, index=False)
    # Store relative reference for report readability (relative to run root).
    run_root = path.parent.parent
    try:
        return str(path.relative_to(run_root))
    except Exception:
        return str(path)


def _write_run_metadata(
    *,
    output_dir: Path,
    run_id: str,
    args: argparse.Namespace,
    results: dict[str, pd.DataFrame],
    sources: dict[str, str],
) -> None:
    meta = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "args": vars(args),
        "outputs": {
            "sources": sources,
            "counts": {k: int(len(df)) for k, df in results.items()},
        },
        "disclaimer": [
            "Automated red flags are not proof of wrongdoing.",
            "Findings are prioritized leads requiring corroboration.",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _run_context_enrichment(
    *,
    run_id: str,
    results: dict[str, pd.DataFrame],
    cadastro_df: pd.DataFrame | None,
    explain_max_entities: int,
    max_results: int,
    since_days: int,
    provider_name: str,
) -> dict[str, dict[str, Any]]:
    if provider_name != "exa":
        # Perplexity support is planned for a later phase.
        return {}

    provider = ExaProvider.from_env()
    if provider is None:
        return {}

    entities = _collect_flagged_entities(results=results, cadastro_df=cadastro_df)
    entities = entities[:explain_max_entities]

    contexts: dict[str, dict[str, Any]] = {}
    cache_root = Path("data/cache/enrichment") / run_id
    cache_root.mkdir(parents=True, exist_ok=True)

    for entity in entities:
        entity_id = entity["entity_id"]
        queries = _build_queries(entity)
        collected: list[SearchResult] = []
        for q in queries:
            try:
                collected.extend(provider.search(q, max_results=max_results, since_days=since_days))
            except Exception:
                continue

        # Deduplicate by URL deterministically.
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in collected:
            if r.url in seen:
                continue
            seen.add(r.url)
            deduped.append(r)

        raw_path = cache_root / f"{entity_id}.json"
        raw_payload = {
            "entity": entity,
            "queries": queries,
            "results": [r.__dict__ for r in deduped],
        }
        raw_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")

        contexts[entity_id] = build_context_section(deduped)

    return contexts


def _collect_flagged_entities(*, results: dict[str, pd.DataFrame], cadastro_df: pd.DataFrame | None) -> list[dict[str, Any]]:
    def normalize_digits(value: Any) -> str | None:
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return digits if digits else None

    catalog: dict[str, dict[str, Any]] = {}
    fund_name_map = {}
    if cadastro_df is not None and not cadastro_df.empty and "CNPJ_FUNDO" in cadastro_df.columns:
        name_col = None
        for candidate in ("DENOM_SOCIAL", "DENOM_SOCIAL_FUNDO", "NOME_FUNDO", "NM_FUNDO"):
            if candidate in cadastro_df.columns:
                name_col = candidate
                break
        if name_col:
            for row in cadastro_df[["CNPJ_FUNDO", name_col]].dropna().itertuples(index=False):
                fund_name_map[normalize_digits(row[0])] = str(row[1]).strip()

    def add(entity_type: str, cnpj_like: Any, name: str | None = None) -> None:
        digits = normalize_digits(cnpj_like)
        entity_id = f"{entity_type}_{digits}" if digits else f"{entity_type}_{_stable_hash(str(cnpj_like) + (name or ''))}"
        if entity_id in catalog:
            return
        catalog[entity_id] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "cnpj_digits": digits,
            "name": name,
        }

    # Fund-based outputs
    for key in ("flow_anomalies", "pl_drops", "runs", "divergences", "phantom_assets_by_fund"):
        df = results.get(key)
        if df is None or df.empty:
            continue
        if "CNPJ_FUNDO" in df.columns:
            for fund in df["CNPJ_FUNDO"].dropna().astype(str).unique():
                digits = normalize_digits(fund)
                add("FUND", digits, name=fund_name_map.get(digits))

    # Scheme outputs
    df = results.get("circular_flow")
    if df is not None and not df.empty:
        for row in df.to_dict(orient="records"):
            add("ADMINISTRATOR", row.get("admin_cnpj"))
            add("FUND", row.get("fund_as_asset"))
            held_by = row.get("held_by_funds") or []
            if isinstance(held_by, str):
                held_by = [held_by]
            for held in held_by:
                add("FUND", held)

    df = results.get("layered_funds")
    if df is not None and not df.empty:
        for row in df.to_dict(orient="records"):
            add("ADMINISTRATOR", row.get("admin_cnpj"))
            add("FUND", row.get("holder_fund"))
            add("FUND", row.get("held_fund"))

    df = results.get("shell_networks")
    if df is not None and not df.empty:
        for row in df.to_dict(orient="records"):
            add("ADMINISTRATOR", row.get("admin_cnpj"))

    df = results.get("asset_inflation")
    if df is not None and not df.empty:
        for row in df.to_dict(orient="records"):
            add("FUND", row.get("fund_cnpj"))

    # Deterministic ordering: severity not known here, so sort by entity_id.
    return sorted(catalog.values(), key=lambda x: x["entity_id"])


def _build_queries(entity: dict[str, Any]) -> list[str]:
    entity_type = entity.get("entity_type")
    name = entity.get("name") or ""
    cnpj = entity.get("cnpj_digits") or ""
    if entity_type == "BANK":
        return [f"Banco {name} {cnpj} enforcement OR investigation OR CVM OR Banco Central"]
    if entity_type == "DISTRIBUTOR":
        return [f"{name} {cnpj} distribuição fundos CVM"]
    if entity_type == "FUND":
        return [f"{name} {cnpj} CVM fundo investigation OR administrator OR gestor"]
    if entity_type == "ADMINISTRATOR":
        return [f"{name} {cnpj} administradora fundos CVM investigation"]
    return [f"{name} {cnpj} investigation regulatory"]


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    raise SystemExit(main())
