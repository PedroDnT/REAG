#!/usr/bin/env python
"""Build a searchable, self-contained dashboard from an investigation run.

Findings currently land as one CSV per detector plus a brief per entity. That
answers "what did we find?" but not the question an investigator actually opens
with: *for this fund, what was checked, and what did each check say?*

The dashboard answers that. Every fund in scope gets a row; selecting one shows
every detector with one of three states:

    fired     the detector ran and flagged this fund, with its metric
    clean     the detector ran and did not flag it
    not run   the detector never executed, so it says nothing either way

The third state is the point. A detector that could not run produces no
findings, which in a plain CSV dump is indistinguishable from a detector that
ran and found nothing -- the exact failure mode this toolkit exists to avoid.
The dashboard renders it as absence of information, never as a pass.

Output is a single HTML file with the data inlined: no server, no network, and
it keeps working when the run directory is archived or moved.

    python scripts/build_dashboard.py --run reports/investigation/<run_id>
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.cnpj_utils import normalize_cnpj, normalize_cnpj_series  # noqa: E402

logger = logging.getLogger(__name__)

#: Columns that identify a fund in a findings CSV, in priority order. A file
#: carrying none of these is keyed by something other than a fund (an issuer, a
#: manager) and cannot take part in a per-fund matrix.
FUND_KEY_COLUMNS = ("CNPJ_FUNDO", "fund_cnpj", "CNPJ")

#: findings file -> the SIGNAL_REGISTRY entry that explains it. A file with no
#: entry still appears in the matrix; it just carries no plain-language note.
#: `test_every_mapped_signal_exists` stops this drifting from the registry.
SIGNAL_FOR_FILE = {
    "benford_violations": "benford_violation",
    "circular_flow": "circular_flow",
    "concentration_spikes": "concentration_violation",
    "concentration_violations": "concentration_violation",
    "cost_basis_anomalies": "cost_basis_anomaly",
    "cross_fund_issuer": "cross_fund_issuer",
    "cross_fund_price_divergence": "cross_fund_price_divergence",
    "flow_anomalies": "flow_anomaly",
    "layered_funds": "layered_funds",
    "lifecycle_anomalies": "fund_lifecycle_anomaly",
    "manager_network_anomalies": "manager_network_anomaly",
    "peer_outliers": "peer_outlier",
    "phantom_assets": "phantom_asset_exposure",
    "phantom_assets_by_fund": "phantom_asset_exposure",
    "pl_drops": "pl_drop",
    "quotaholder_anomalies": "quotaholder_anomaly",
    "reconciliation_gaps": "portfolio_reconciliation_gap",
    "runs": "redemption_run",
    "shell_networks": "shell_network",
    "valuation_smoothing": "valuation_smoothing",
    "window_dressing": "window_dressing",
}

#: Metric columns worth quoting, in preference order, when reading a findings
#: CSV directly. Mirrors what the briefs quote.
METRIC_COLUMNS = (
    "Z_SCORE_FLOW", "PL_VAR_PCT", "RUN_LENGTH", "divergence_pct", "PCT_CARTEIRA",
    "top1_pct", "sharpe_zscore", "pl_mad", "pct_change", "per_capita_aum",
    "gain_ratio", "gap_pct", "max_pl", "days_active", "deviation_pct",
    "autocorrelation", "vol_ratio", "stale_days", "DIVERGENCE_SCORE",
    "total_value", "num_funds_holding", "similarity",
)

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

#: Alternate severity columns, in preference order. Detectors do not agree on a
#: single name; without this mapping the matrix grades almost every hit as blank
#: and the page cannot sort by seriousness.
SEVERITY_COLUMNS = ("severity", "overall_fraud_risk", "fraud_risk")

#: Benford on a single CVM month has ~22 observations per fund. The chi-square
#: test inside the analyzer itself treats n < 30 as unreliable; those rows are
#: statistical noise, not leads, and must not fill the matrix.
BENFORD_MIN_SAMPLE = 30


def _trim(value: Any) -> str:
    """Render a metric for a person, not a float dump."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return f"{number:.2f}" if abs(number) >= 1000 else f"{number:.4g}"


def _truthy_mask(series: pd.Series) -> pd.Series:
    """Boolean mask for CSV flags stored as strings (True/False/1/0)."""
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin(("true", "1", "yes", "y", "t"))


def _prepare_findings_frame(key: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are known non-leads before they enter the fund matrix.

    A findings CSV is not always a list of alerts. ``peer_outliers`` writes one
    row per compared fund, including the ones that are *not* outliers;
    ``benford_violations`` scores every fund even when the sample is too small
    for Benford to apply; ``phantom_assets_by_fund`` marks ordinary fund-of-fund
    holdings as phantom. Without these filters a full-universe page reads as
    "everything is suspicious", which trains people to ignore the real leads.
    """
    if frame.empty:
        return frame

    work = frame
    if key == "peer_outliers" and "is_outlier" in work.columns:
        work = work.loc[_truthy_mask(work["is_outlier"])]
    elif key == "benford_violations" and "pl_sample_size" in work.columns:
        samples = pd.to_numeric(work["pl_sample_size"], errors="coerce").fillna(0)
        work = work.loc[samples >= BENFORD_MIN_SAMPLE]
    elif key == "phantom_assets_by_fund" and "asset_type" in work.columns:
        # Cotas de outros fundos are the normal structure of a FIC, not a phantom
        # security. Keep listed-looking codes and manual-review rows only.
        asset_type = work["asset_type"].astype(str).str.upper()
        keep = asset_type.ne("FUND")
        if "status" in work.columns:
            keep = keep | work["status"].astype(str).str.upper().eq("NEEDS_MANUAL_REVIEW")
        work = work.loc[keep]

    return work


def _severity_series(frame: pd.DataFrame, key: str = "") -> pd.Series:
    """Best available severity label per row, uppercased, or empty.

    Some detectors fire on patterns that are common in legitimate Brazilian
    funds (FIC concentration, mild return smoothing). Those still appear as
    signals, but are capped below HIGH so Priority review stays usable.
    """
    severity = pd.Series("", index=frame.index, dtype=str)
    for column in SEVERITY_COLUMNS:
        if column in frame.columns:
            severity = frame[column].astype(str).str.strip().str.upper().replace(
                {"NAN": "", "NONE": "", "UNKNOWN": ""}
            )
            break

    if key == "concentration_violations":
        # High single-name weights are the normal shape of many FICs / feeder
        # funds. Keep the signal visible, but never in the Priority band alone.
        severity = severity.mask(severity.isin(("HIGH", "CRITICAL")), "MEDIUM")
        severity = severity.mask(severity.eq(""), "MEDIUM")
    elif key == "valuation_smoothing":
        # HIGH smoothing alerts are frequent on short windows; keep CRITICAL only
        # in the priority band.
        severity = severity.mask(severity.eq("HIGH"), "MEDIUM")
    elif key == "concentration_spikes":
        severity = severity.mask(severity.isin(("HIGH", "CRITICAL")), "MEDIUM")
        severity = severity.mask(severity.eq(""), "MEDIUM")
    elif key == "phantom_assets_by_fund" and "status" in frame.columns:
        # Registry misses on listed codes are common; only manual-review rows
        # stay urgent.
        manual = frame["status"].astype(str).str.upper().eq("NEEDS_MANUAL_REVIEW")
        severity = severity.mask(
            (~manual) & severity.isin(("HIGH", "CRITICAL")), "MEDIUM"
        )

    return severity


def _names_from_cadastro(summary: dict[str, Any]) -> dict[str, str]:
    """Fund names, read from the registry the run itself used.

    Briefs carry names, but a full-universe run is written with --no-explain,
    so the names have to come from the same registry snapshot the run loaded --
    otherwise search by name works on a scoped run and silently stops working
    on the big one.
    """
    path = (summary.get("args") or {}).get("cadastro")
    if not path or not Path(path).exists():
        return {}
    try:
        from src.processors.data_processor import DataProcessor
        registry = DataProcessor().read_registro_fundo_classe(Path(path))
    except Exception as exc:  # noqa: BLE001 - names are a nicety, never fatal
        logger.warning("Could not read fund names from %s: %s", path, exc)
        return {}
    if registry.empty or "CNPJ_FUNDO" not in registry.columns:
        return {}
    name_col = next((c for c in ("DENOM_SOCIAL", "NM_FUNDO") if c in registry.columns), None)
    if not name_col:
        return {}
    pairs = registry[["CNPJ_FUNDO", name_col]].dropna()
    return {str(c): str(n).strip() for c, n in zip(pairs["CNPJ_FUNDO"], pairs[name_col],
                                                   strict=False)}


def _period(summary: dict[str, Any]) -> dict[str, Any]:
    """The window the findings cover, however the run recorded it."""
    recorded = summary.get("data_period") or {}
    if recorded.get("start"):
        return recorded
    # Older runs predate the field. Derive it from the informe they used rather
    # than showing a report with no period on it.
    path = (summary.get("args") or {}).get("informe")
    if not path or not Path(path).exists():
        return {}
    try:
        dates = pd.read_csv(path, sep=";", encoding="latin1",
                            usecols=lambda c: c.strip().upper().startswith("DT_COMPTC"))
        col = dates.columns[0]
        parsed = pd.to_datetime(dates[col], errors="coerce").dropna()
        if parsed.empty:
            return {}
        return {"start": parsed.min().date().isoformat(),
                "end": parsed.max().date().isoformat(),
                "reporting_days": int(parsed.dt.date.nunique()), "derived": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not derive the data period: %s", exc)
        return {}


def _explanations(tests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Plain-language notes for the detectors on this page.

    Curated already in SIGNAL_REGISTRY -- what the flag means, what would
    explain it innocently, and what to check next. A red flag without its
    caveats invites exactly the over-reading this toolkit warns against.
    """
    from src.explain.signal_registry import SIGNAL_REGISTRY

    out: dict[str, dict[str, Any]] = {}
    for test in tests:
        signal = test.get("signal")
        definition = SIGNAL_REGISTRY.get(signal) if signal else None
        if not definition:
            continue
        out[test["key"]] = {
            "title": definition.title,
            "what": definition.plain_language_explanation,
            "caveats": list(definition.caveats),
            "next_steps": list(definition.next_steps),
        }
    return out


def format_cnpj(digits: str) -> str:
    """Punctuate a 14-digit CNPJ the way Brazilian documents present it."""
    d = str(digits)
    if len(d) != 14:
        return d
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def load_run(run_dir: Path) -> dict[str, Any]:
    """Read a run directory into the shape the page needs.

    Args:
        run_dir: An investigation run directory (contains summary.json)

    Returns:
        Dict with run metadata, the test list, and one record per fund
    """
    summary = json.loads((run_dir / "summary.json").read_text())
    execution = summary.get("execution", {}) or {}
    scope = summary.get("scope", {}) or {}

    # --- which detectors ran, and which are fund-keyed ---------------------
    tests: dict[str, dict[str, Any]] = {}
    fund_hits: dict[str, set[str]] = {}
    csv_detail: dict[str, dict[str, dict[str, Any]]] = {}
    entity_level: list[str] = []

    for csv_path in sorted((run_dir / "findings").glob("*.csv")):
        key = csv_path.stem
        try:
            frame = pd.read_csv(csv_path, dtype=str)
        except pd.errors.EmptyDataError:
            frame = pd.DataFrame()

        column = next((c for c in FUND_KEY_COLUMNS if c in frame.columns), None)
        if column is None and not frame.empty:
            # Has rows but keys on an issuer, manager or asset rather than a
            # fund. Still worth naming, so the reader can see it ran -- just
            # not as a per-fund verdict.
            entity_level.append(key)
            continue

        # Drop known non-leads before counting. The detector still "ran"; the
        # matrix only shows rows that survive as actionable signals.
        frame = _prepare_findings_frame(key, frame)

        # An empty findings file means the detector ran and flagged nobody.
        # That is a clean result for every fund, and must not be filed as
        # "not applicable" -- treating "found nothing" as "said nothing" is the
        # exact conflation this page exists to prevent.
        tests[key] = {"key": key, "rows": int(len(frame)), "signal": SIGNAL_FOR_FILE.get(key)}
        if column is None or frame.empty:
            continue

        metric_col = next((c for c in METRIC_COLUMNS if c in frame.columns), None)
        work = frame.assign(
            _cnpj=normalize_cnpj_series(frame[column]),
            _severity=_severity_series(frame, key),
        ).dropna(subset=["_cnpj"])
        if work.empty:
            continue

        work["_rank"] = work["_severity"].map(SEVERITY_RANK).fillna(0).astype(int)
        # Worst severity and event count per fund in one pass -- a Python
        # groupby loop over 100k+ phantom rows dominated full-universe builds.
        ranked = work.sort_values("_rank", ascending=False)
        first = ranked.groupby("_cnpj", sort=False, as_index=False).first()
        events = work.groupby("_cnpj", sort=False).size()

        for row in first.to_dict("records"):
            cnpj = str(row["_cnpj"])
            fund_hits.setdefault(cnpj, set()).add(key)
            severity = row["_severity"] if row["_severity"] in SEVERITY_RANK else ""
            metric = ""
            if metric_col:
                raw = row.get(metric_col)
                if raw is not None and str(raw) not in ("", "nan", "None"):
                    metric = f"{metric_col}: {_trim(raw)}"
            csv_detail.setdefault(cnpj, {})[key] = {
                "test": key,
                "severity": severity,
                "metric": metric,
                "events": int(events.loc[cnpj]) if cnpj in events.index else 1,
            }

    # --- names, and the metric each brief chose (when briefs were written) ---
    evidence: dict[str, dict[str, dict[str, Any]]] = {}
    names: dict[str, str] = {}
    for path in sorted((run_dir / "entities").glob("*/evidence.json")):
        payload = json.loads(path.read_text())
        entity = payload.get("entity", {}) or {}
        if entity.get("entity_type") != "FUND":
            continue
        cnpj = normalize_cnpj(entity.get("cnpj_digits") or "")
        if not cnpj:
            continue
        if entity.get("name"):
            names[cnpj] = str(entity["name"]).strip()
        for item in payload.get("evidence") or []:
            source = str(item.get("source_ref") or "")
            test = Path(source).stem if source else ""
            if not test:
                continue
            current = evidence.setdefault(cnpj, {}).get(test)
            candidate = {
                "test": test,
                "title": item.get("title") or "",
                "severity": (item.get("severity") or "").upper(),
                "metric": item.get("metric") or "",
            }
            if not current or SEVERITY_RANK.get(candidate["severity"], 0) > SEVERITY_RANK.get(
                current["severity"], 0
            ):
                evidence[cnpj][test] = candidate

    names.update(_names_from_cadastro(summary))

    # --- the fund universe -------------------------------------------------
    in_scope = [normalize_cnpj(c) for c in (scope.get("selected_cnpjs") or [])]
    universe = sorted({c for c in in_scope if c} | set(fund_hits) | set(evidence))

    funds = []
    for cnpj in universe:
        hits = sorted(fund_hits.get(cnpj, set()))
        detail: dict[str, dict[str, Any]] = {}
        for test in hits:
            base = dict(csv_detail.get(cnpj, {}).get(test, {"test": test}))
            # A brief, when one was written, already picked the metric a reader
            # should see and graded it. Prefer that; fall back to the CSV so the
            # page still works for a --no-explain run over the full universe.
            brief = (evidence.get(cnpj) or {}).get(test)
            if brief:
                base["severity"] = brief["severity"] or base.get("severity", "")
                base["metric"] = brief["metric"] or base.get("metric", "")
                base["title"] = brief.get("title", "")
            detail[test] = base
        worst = max((SEVERITY_RANK.get(d.get("severity", ""), 0) for d in detail.values()),
                    default=0)
        funds.append({
            "cnpj": cnpj,
            "display": format_cnpj(cnpj),
            "name": names.get(cnpj, ""),
            "hits": hits,
            "detail": detail,
            "severity": next((s_ for s_, r in SEVERITY_RANK.items() if r == worst), ""),
            "count": len(hits),
        })

    funds.sort(key=lambda f: (-SEVERITY_RANK.get(f["severity"], 0), -f["count"], f["cnpj"]))

    test_list = [tests[k] for k in sorted(tests)]
    return {
        "run_id": summary.get("run_id") or run_dir.name,
        "generated_at": summary.get("generated_at") or "",
        "period": _period(summary),
        "explanations": _explanations(test_list),
        "scope": scope,
        "tests": test_list,
        "entity_level": sorted(entity_level),
        "skipped": sorted(execution.get("skipped_analyzers") or []),
        "failed": sorted(execution.get("failed_analyzers") or []),
        "complete": bool(execution.get("complete", True)),
        "funds": funds,
    }


def _squeeze(text: str) -> str:
    """Strip comments and indentation from generated CSS/JS.

    The stylesheet and script are generated, never hand-edited in the output,
    so shipping their indentation only costs bandwidth. Kept deliberately
    conservative -- comment and leading-whitespace removal only, no renaming or
    semicolon elision, so a broken minifier can never be the reason the page
    fails to load.
    """
    import re
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    text = re.sub(r"^[ \t]+", "", text, flags=re.M)
    return re.sub(r"\n{2,}", "\n", text).strip()


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Re-encode the fund table columnar.

    One object per fund repeats its keys 25,509 times; on a full CVM month that
    is most of the file. Funds become tuples against a shared test index, which
    takes the payload from roughly 20 MB to under 3 MB with no loss.
    """
    keys = [t["key"] for t in data["tests"]]
    index = {k: i for i, k in enumerate(keys)}
    sev = ["", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

    rows = []
    for fund in data["funds"]:
        hits = []
        for test in fund["hits"]:
            d = fund["detail"].get(test, {})
            hits.append([
                index.get(test, -1),
                sev.index(d.get("severity", "")) if d.get("severity", "") in sev else 0,
                d.get("metric", ""),
                d.get("events", 1),
            ])
        rows.append([fund["cnpj"], fund["name"], sev.index(fund["severity"])
                     if fund["severity"] in sev else 0, hits])

    out = {k: v for k, v in data.items() if k != "funds"}
    # selected_cnpjs repeats every CNPJ already carried in `rows` -- on a full
    # month that is 25,509 duplicated identifiers, roughly 350 KB of payload
    # that renders nothing. The counts stay; the list goes.
    out["scope"] = {k: v for k, v in (out.get("scope") or {}).items()
                    if k != "selected_cnpjs"}
    out["severities"] = sev
    out["rows"] = rows
    return out


def render(data: dict[str, Any], *, fragment: bool = False) -> str:
    """Render the dashboard to a single HTML document."""
    payload = json.dumps(_compact(data), ensure_ascii=False, separators=(",", ":"))
    scope = data["scope"]
    where = ""
    if scope.get("fund_mode"):
        where = f"{scope['fund_mode'].replace('_', ' ')} · {scope.get('fund_identifier', '')}"

    body = f"""
<header class="masthead">
  <div class="masthead-id">
    <h1>Fund screening</h1>
    <p class="run">{_period_line(data)}</p>
    <p class="run subtle">run <code>{html.escape(str(data['run_id']))}</code>{
        ' · ' + html.escape(where) if where else ''}{
        ' · analysed ' + html.escape(str(data['generated_at']).replace('T', ' '))
        if data.get('generated_at') else ''}</p>
  </div>
  <dl class="tallies">
    <div><dt>Funds in scope</dt><dd>{len(data['funds'])}</dd></div>
    <div><dt>Detectors run</dt><dd>{len(data['tests'])}</dd></div>
    <div><dt>With any signal</dt><dd>{sum(1 for f in data['funds'] if f['count'])}</dd></div>
    <div><dt>Priority review</dt><dd>{
        sum(1 for f in data['funds'] if SEVERITY_RANK.get(f['severity'], 0) >= 3)
    }</dd></div>
  </dl>
</header>

{_lead_banner()}
{_coverage_banner(data)}

<main class="split">
  <section class="list-pane" aria-label="Funds">
    <div class="searchbar">
      <input id="q" type="search" autocomplete="off" spellcheck="false"
             placeholder="Search by CNPJ or fund name" aria-label="Search funds">
      <label class="only-flagged">
        <input type="checkbox" id="priority" checked>
        Priority only (HIGH / CRITICAL)
      </label>
      <label class="only-flagged">
        <input type="checkbox" id="only"> Any signal
      </label>
    </div>
    <p class="result-count" id="count" role="status"></p>
    <ol class="funds" id="funds"></ol>
  </section>

  <section class="detail-pane" id="detail" aria-live="polite">
    <div class="empty">
      <p>Select a fund to see what each detector reported.</p>
      <p class="empty-note">A signal is a lead to review, not a finding of wrongdoing.</p>
    </div>
  </section>
</main>

<footer>
  <p>Statistical red flags are leads, not proof. Most funds with a signal are
     ultimately fine — concentration, peer deviation, and short-sample quirks are
     common in legitimate portfolios. Corroborate anything you escalate against
     records this toolkit cannot see (subscription ledgers, transfers, custody).</p>
</footer>

<script id="data" type="application/json">{payload}</script>
<script>{_squeeze(_SCRIPT)}</script>
"""

    if fragment:
        return f"<style>{_squeeze(_STYLE)}</style>\n{body}"

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>Fund screening — {html.escape(str(data['run_id']))}</title>\n"
        f"<style>{_squeeze(_STYLE)}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def _period_line(data: dict[str, Any]) -> str:
    """The dates the findings cover. A report without them cannot be rechecked."""
    period = data.get("period") or {}
    if not period.get("start"):
        return '<strong class="no-period">Data period not recorded</strong>'
    start, end = html.escape(period["start"]), html.escape(period["end"])
    days = period.get("reporting_days")
    extra = f' · {days} reporting days' if days else ""
    derived = ' <span class="derived">(derived from the source file)</span>' if period.get(
        "derived") else ""
    return f'<strong>Filings from {start} to {end}</strong>{extra}{derived}'


def _lead_banner() -> str:
    """State the epistemic status of the page before any number is read."""
    return (
        '<p class="coverage lead">'
        "<strong>Leads, not verdicts.</strong> "
        "An outlier or red flag means &ldquo;worth a look,&rdquo; not "
        "&ldquo;this fund is fraudulent.&rdquo; Start with Priority review; "
        "most signals have an innocent explanation."
        "</p>"
    )


def _coverage_banner(data: dict[str, Any]) -> str:
    """Say plainly when part of the battery did not run."""
    missing = data["failed"] + data["skipped"]
    if not missing:
        return (
            '<p class="coverage ok">Every detector ran. '
            'A fund with no signals was checked and came back clean — '
            'that is not the same as proven legitimate, but it is the screen clearing.</p>'
        )
    bits = []
    if data["failed"]:
        bits.append(f"<strong>{len(data['failed'])} failed</strong>: "
                    + ", ".join(f"<code>{html.escape(a)}</code>" for a in data["failed"]))
    if data["skipped"]:
        bits.append(f"{len(data['skipped'])} skipped for missing inputs: "
                    + ", ".join(f"<code>{html.escape(a)}</code>" for a in data["skipped"]))
    return (
        '<p class="coverage warn">Incomplete coverage — ' + "; ".join(bits) +
        ". Those detectors report nothing either way; absence of a signal from them "
        "is not a clean result.</p>"
    )


_STYLE = """
*,*::before,*::after{box-sizing:border-box}

:root{
  --ground:#f7f8fa; --panel:#ffffff; --sunken:#eef0f4;
  --ink:#10141c; --ink-soft:#4a5364; --ink-faint:#78829a;
  --line:#dde1e9; --line-soft:#e6e9f0;
  --accent:#2d4a7c; --accent-soft:#e8edf6;
  --critical:#a8323f; --high:#b8503a; --medium:#9a6b1f; --low:#5b6472;
  --clean:#2f6b4f; --clean-soft:#eaf2ee;
  --unrun:#8b93a5;
  --shadow:0 1px 2px rgba(16,20,28,.06),0 8px 24px -12px rgba(16,20,28,.18);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0e1116; --panel:#161b22; --sunken:#1c222c;
    --ink:#e9edf4; --ink-soft:#a3adbf; --ink-faint:#6f7a8d;
    --line:#262d38; --line-soft:#1f2530;
    --accent:#7ea3d8; --accent-soft:#1a2434;
    --critical:#e8737f; --high:#e08a68; --medium:#d7a94e; --low:#8a94a6;
    --clean:#6dbd94; --clean-soft:#16241d;
    --unrun:#6b7484;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -14px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --ground:#0e1116; --panel:#161b22; --sunken:#1c222c;
  --ink:#e9edf4; --ink-soft:#a3adbf; --ink-faint:#6f7a8d;
  --line:#262d38; --line-soft:#1f2530;
  --accent:#7ea3d8; --accent-soft:#1a2434;
  --critical:#e8737f; --high:#e08a68; --medium:#d7a94e; --low:#8a94a6;
  --clean:#6dbd94; --clean-soft:#16241d;
  --unrun:#6b7484;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -14px rgba(0,0,0,.7);
}

body{
  margin:0; background:var(--ground); color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;
}
code,.mono,.cnpj,.metric{
  font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  font-variant-numeric:tabular-nums;
}

.masthead{
  display:flex; flex-wrap:wrap; gap:24px; align-items:flex-end;
  justify-content:space-between;
  padding:26px clamp(16px,4vw,36px) 20px;
  border-bottom:1px solid var(--line);
}
.masthead h1{
  margin:0; font-size:1.35rem; font-weight:620; letter-spacing:-.01em;
  text-wrap:balance;
}
.run{margin:5px 0 0; color:var(--ink-soft); font-size:.86rem}
.run.subtle{color:var(--ink-faint); font-size:.78rem}
.run strong{font-weight:600; color:var(--ink)}
.no-period{color:var(--medium)}
.derived{color:var(--ink-faint); font-weight:400}
.run code{font-size:.82rem; color:var(--ink-soft)}

.tallies{display:flex; gap:28px; margin:0}
.tallies div{display:flex; flex-direction:column; gap:2px}
.tallies dt{
  font-size:.66rem; letter-spacing:.09em; text-transform:uppercase;
  color:var(--ink-faint);
}
.tallies dd{
  margin:0; font-size:1.5rem; font-weight:600;
  font-variant-numeric:tabular-nums;
}

.coverage{
  margin:0; padding:11px clamp(16px,4vw,36px);
  font-size:.85rem; border-bottom:1px solid var(--line);
}
.coverage.ok{color:var(--clean); background:var(--clean-soft)}
.coverage.warn{color:var(--medium); background:var(--sunken)}
.coverage.lead{color:var(--ink); background:var(--accent-soft)}
.coverage.lead strong{font-weight:650}
.coverage code{font-size:.82em}
.empty-note{margin:8px 0 0; color:var(--ink-faint); font-size:.9rem}

.split{
  display:grid; grid-template-columns:minmax(300px,400px) 1fr;
  align-items:start; min-height:60vh;
}
@media (max-width:860px){ .split{grid-template-columns:1fr} }

.list-pane{border-right:1px solid var(--line); min-width:0}
@media (max-width:860px){ .list-pane{border-right:none; border-bottom:1px solid var(--line)} }

.searchbar{
  display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  padding:16px clamp(14px,3vw,20px) 8px;
}
#q{
  flex:1 1 180px; min-width:0;
  padding:9px 12px; border:1px solid var(--line); border-radius:7px;
  background:var(--panel); color:var(--ink); font:inherit; font-size:.9rem;
}
#q:focus-visible{outline:2px solid var(--accent); outline-offset:1px; border-color:transparent}
.only-flagged{
  display:flex; align-items:center; gap:6px;
  font-size:.79rem; color:var(--ink-soft); white-space:nowrap; cursor:pointer;
}
.result-count{
  margin:0; padding:0 clamp(14px,3vw,20px) 10px;
  font-size:.73rem; letter-spacing:.05em; text-transform:uppercase;
  color:var(--ink-faint);
}

.funds{
  list-style:none; margin:0; padding:0 0 20px;
  max-height:66vh; overflow-y:auto;
}
.funds li{border-top:1px solid var(--line-soft)}
.fund-btn{
  display:grid; grid-template-columns:3px 1fr auto; gap:12px; align-items:center;
  width:100%; padding:10px clamp(14px,3vw,20px);
  background:none; border:0; text-align:left; cursor:pointer;
  color:inherit; font:inherit;
}
.fund-btn:hover{background:var(--sunken)}
.fund-btn:focus-visible{outline:2px solid var(--accent); outline-offset:-2px}
.fund-btn[aria-current="true"]{background:var(--accent-soft)}
.stripe{align-self:stretch; border-radius:2px; background:var(--line)}
.stripe.CRITICAL{background:var(--critical)} .stripe.HIGH{background:var(--high)}
.stripe.MEDIUM{background:var(--medium)}  .stripe.LOW{background:var(--low)}
.fund-id{min-width:0}
.cnpj{font-size:.83rem; display:block}
.fund-name{
  display:block; font-size:.75rem; color:var(--ink-faint);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.hit-count{
  font-size:.74rem; font-variant-numeric:tabular-nums; color:var(--ink-faint);
  white-space:nowrap;
}
.hit-count strong{color:var(--ink); font-weight:600}

.detail-pane{padding:18px clamp(16px,4vw,32px) 40px; min-width:0}
.empty{color:var(--ink-faint); font-size:.9rem; padding-top:28px}

.detail-head h2{margin:0; font-size:1.05rem; font-weight:600}
.detail-head .cnpj{margin-top:3px; color:var(--ink-soft); font-size:.85rem}
.verdict{
  display:inline-block; margin:12px 0 4px; padding:3px 10px; border-radius:999px;
  font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; font-weight:600;
}
.verdict.flagged{background:var(--critical); color:#fff}
.verdict.clear{background:var(--clean-soft); color:var(--clean); border:1px solid currentColor}

.matrix{
  display:grid; gap:8px; margin:16px 0 0; padding:0; list-style:none;
  grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
}
.test{
  border:1px solid var(--line); border-radius:8px; padding:9px 11px;
  background:var(--panel); box-shadow:var(--shadow); min-width:0;
}
.test.is-clean{box-shadow:none; background:transparent}
.test.is-unrun{
  box-shadow:none; background:transparent;
  border-style:dashed; border-color:var(--unrun);
}
.test-name{
  display:flex; align-items:baseline; justify-content:space-between; gap:8px;
  font-size:.82rem; font-weight:550;
}
.test.is-clean .test-name,.test.is-unrun .test-name{font-weight:450; color:var(--ink-soft)}
.chip{
  font-size:.63rem; letter-spacing:.07em; text-transform:uppercase;
  font-weight:700; white-space:nowrap;
}
.chip.CRITICAL{color:var(--critical)} .chip.HIGH{color:var(--high)}
.chip.MEDIUM{color:var(--medium)}   .chip.LOW{color:var(--low)}
.chip.clean{color:var(--clean)}     .chip.unrun{color:var(--unrun)}
.metric{
  margin:5px 0 0; font-size:.76rem; color:var(--ink-soft);
  overflow-wrap:anywhere;
}
.unrun-why{margin:5px 0 0; font-size:.72rem; color:var(--unrun); font-style:italic}

.explain{margin:7px 0 0}
.explain summary{
  cursor:pointer; font-size:.71rem; color:var(--accent);
  letter-spacing:.03em; list-style:none;
}
.explain summary::-webkit-details-marker{display:none}
.explain summary::before{content:"▸ "; font-size:.85em}
.explain[open] summary::before{content:"▾ "}
.explain summary:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:3px}
.explain-body{
  margin-top:7px; padding-left:9px; border-left:2px solid var(--line);
  font-size:.76rem; color:var(--ink-soft);
}
.explain-body p{margin:0 0 6px}
.explain-body .lbl{
  display:block; font-size:.63rem; letter-spacing:.08em; text-transform:uppercase;
  color:var(--ink-faint); margin:8px 0 3px;
}
.explain-body ul{margin:0; padding-left:16px}
.explain-body li{margin:0 0 3px}

.truncation{
  margin:10px clamp(14px,3vw,20px); padding:8px 11px; border-radius:7px;
  background:var(--sunken); color:var(--ink-soft); font-size:.76rem;
}

.section-label{
  margin:26px 0 0; font-size:.68rem; letter-spacing:.09em;
  text-transform:uppercase; color:var(--ink-faint);
}
.entity-note{margin:6px 0 0; font-size:.8rem; color:var(--ink-soft)}

footer{
  padding:20px clamp(16px,4vw,36px) 32px; border-top:1px solid var(--line);
  color:var(--ink-faint); font-size:.79rem; max-width:78ch;
}
footer p{margin:0}

@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

_SCRIPT = r"""
(function(){
  var D = JSON.parse(document.getElementById('data').textContent);
  var testKeys = D.tests.map(function(t){ return t.key; });

  // Rehydrate the columnar payload (see _compact in build_dashboard.py).
  D.funds = D.rows.map(function(r){
    var detail = {}, hits = [];
    r[3].forEach(function(h){
      var key = testKeys[h[0]];
      if (key === undefined) return;
      hits.push(key);
      detail[key] = {severity: D.severities[h[1]] || '', metric: h[2], events: h[3]};
    });
    return {cnpj: r[0], display: fmtCnpj(r[0]), name: r[1],
            severity: D.severities[r[2]] || '', hits: hits, detail: detail,
            count: hits.length};
  });

  function fmtCnpj(d){
    return d.length === 14
      ? d.slice(0,2)+'.'+d.slice(2,5)+'.'+d.slice(5,8)+'/'+d.slice(8,12)+'-'+d.slice(12)
      : d;
  }
  var unrun = D.failed.concat(D.skipped);
  var listEl = document.getElementById('funds');
  var countEl = document.getElementById('count');
  var detailEl = document.getElementById('detail');
  var qEl = document.getElementById('q');
  var onlyEl = document.getElementById('only');
  var priorityEl = document.getElementById('priority');
  var selected = null;
  var SEV_RANK = {LOW:1, MEDIUM:2, HIGH:3, CRITICAL:4};

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function label(key){ return key.replace(/_/g,' '); }

  // What the signal means, what would explain it innocently, what to check next.
  // Collapsed by default: the matrix is for scanning, this is for deciding.
  function explain(key){
    var e = D.explanations[key];
    if (!e) return '';
    var body = '<p>' + esc(e.what) + '</p>';
    if (e.caveats && e.caveats.length){
      body += '<span class="lbl">Could also be</span><ul>' +
        e.caveats.map(function(c){ return '<li>' + esc(c) + '</li>'; }).join('') + '</ul>';
    }
    if (e.next_steps && e.next_steps.length){
      body += '<span class="lbl">What would settle it</span><ul>' +
        e.next_steps.map(function(c){ return '<li>' + esc(c) + '</li>'; }).join('') + '</ul>';
    }
    return '<details class="explain"><summary>What this means</summary>' +
      '<div class="explain-body">' + body + '</div></details>';
  }

  function matches(f, q){
    if (!q) return true;
    return (f.cnpj.indexOf(q) !== -1) ||
           (f.display.toLowerCase().indexOf(q) !== -1) ||
           (f.name && f.name.toLowerCase().indexOf(q) !== -1);
  }

  function passesFilters(f){
    var priorityOnly = priorityEl && priorityEl.checked;
    var anySignal = onlyEl && onlyEl.checked;
    if (priorityOnly) return (SEV_RANK[f.severity] || 0) >= 3;
    if (anySignal) return f.count > 0;
    return true;
  }

  function renderList(){
    var q = qEl.value.trim().toLowerCase().replace(/[.\-\/]/g,'');
    var filtered = priorityEl && priorityEl.checked;
    var anySignal = onlyEl && onlyEl.checked;
    var rows = D.funds.filter(function(f){
      return matches(f, q) && passesFilters(f);
    });

    var total = rows.length;
    // 25k rows would be 25k DOM nodes for a list nobody scrolls to the end of.
    // Cap it and say so; search is the way through, not scrolling.
    var CAP = 250;
    var capped = total > CAP;
    if (capped) rows = rows.slice(0, CAP);

    countEl.textContent = (capped ? 'showing ' + CAP + ' of ' + total : total) +
      (total === 1 ? ' fund' : ' funds') +
      (q || filtered || anySignal ? ' matching' : '');

    if (!total){
      listEl.innerHTML = '<li class="no-hits"><p class="empty" style="padding:14px 20px">' +
        'No fund matches that search.</p></li>';
      return;
    }
    listEl.innerHTML = (capped
      ? '<li><p class="truncation">Showing the ' + CAP + ' most severe of ' + total +
        ' matches. Narrow the search to see the rest.</p></li>'
      : '') + rows.map(function(f){
      return '<li><button class="fund-btn" data-cnpj="' + f.cnpj + '"' +
        (selected === f.cnpj ? ' aria-current="true"' : '') + '>' +
        '<span class="stripe ' + esc(f.severity) + '"></span>' +
        '<span class="fund-id">' +
          '<span class="cnpj">' + esc(f.display) + '</span>' +
          (f.name ? '<span class="fund-name">' + esc(f.name) + '</span>' : '') +
        '</span>' +
        '<span class="hit-count">' + (f.count
            ? '<strong>' + f.count + '</strong>/' + testKeys.length
            : '&mdash;') + '</span>' +
        '</button></li>';
    }).join('');
  }

  function renderDetail(cnpj){
    var f = D.funds.filter(function(x){ return x.cnpj === cnpj; })[0];
    if (!f) return;
    selected = cnpj;

    var cards = testKeys.map(function(key){
      var hit = f.detail[key];
      if (hit){
        var sev = hit.severity || 'flagged';
        return '<li class="test is-fired">' +
          '<div class="test-name"><span>' + esc(hit.title || label(key)) + '</span>' +
          '<span class="chip ' + esc(hit.severity) + '">' + esc(sev) + '</span></div>' +
          (hit.metric ? '<p class="metric">' + esc(hit.metric) + '</p>' : '') +
          (hit.events > 1 ? '<p class="metric">' + hit.events + ' events</p>' : '') +
          explain(key) +
          '</li>';
      }
      if (f.hits.indexOf(key) !== -1){
        // Present in findings but no severity/metric line yet.
        return '<li class="test is-fired"><div class="test-name"><span>' +
          esc(label(key)) + '</span><span class="chip LOW">signal</span></div></li>';
      }
      return '<li class="test is-clean"><div class="test-name"><span>' + esc(label(key)) +
        '</span><span class="chip clean">clean</span></div></li>';
    });

    var unrunCards = unrun.map(function(a){
      return '<li class="test is-unrun"><div class="test-name"><span>' + esc(label(a)) +
        '</span><span class="chip unrun">not run</span></div>' +
        '<p class="unrun-why">No result either way.</p></li>';
    });

    detailEl.innerHTML =
      '<div class="detail-head">' +
        '<h2>' + esc(f.name || 'Fund ' + f.display) + '</h2>' +
        '<p class="cnpj">' + esc(f.display) + '</p>' +
        (f.count
          ? '<span class="verdict flagged">' + f.count + ' of ' + testKeys.length +
            ' detectors raised a signal — review, do not treat as proof</span>'
          : '<span class="verdict clear">No detector raised a signal for this fund</span>') +
      '</div>' +
      '<ul class="matrix">' + cards.join('') + '</ul>' +
      (unrunCards.length
        ? '<p class="section-label">Did not run</p><ul class="matrix">' +
          unrunCards.join('') + '</ul>'
        : '') +
      (D.entity_level.length
        ? '<p class="section-label">Reported at issuer or manager level</p>' +
          '<p class="entity-note">' + D.entity_level.map(label).map(esc).join(', ') +
          ' — these key on a counterparty rather than a fund, so they are not part ' +
          'of this matrix.</p>'
        : '');

    renderList();
  }

  listEl.addEventListener('click', function(e){
    var btn = e.target.closest('.fund-btn');
    if (btn) renderDetail(btn.getAttribute('data-cnpj'));
  });
  qEl.addEventListener('input', renderList);
  if (onlyEl) onlyEl.addEventListener('change', function(){
    if (onlyEl.checked && priorityEl) priorityEl.checked = false;
    renderList();
  });
  if (priorityEl) priorityEl.addEventListener('change', function(){
    if (priorityEl.checked && onlyEl) onlyEl.checked = false;
    renderList();
  });

  renderList();
  if (D.funds.length){
    var first = D.funds.filter(function(f){ return (SEV_RANK[f.severity] || 0) >= 3; })[0]
      || D.funds[0];
    if (first && first.count) renderDetail(first.cnpj);
  }
})();
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, type=Path,
                        help="Investigation run directory (contains summary.json)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Where to write the HTML (default: <run>/dashboard.html)")
    parser.add_argument("--fragment", action="store_true",
                        help="Emit body-only HTML for embedding in a host page")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not (args.run / "summary.json").exists():
        parser.error(f"{args.run} does not look like a run directory (no summary.json)")

    data = load_run(args.run)
    output = args.output or (args.run / "dashboard.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data, fragment=args.fragment), encoding="utf-8")

    flagged = sum(1 for f in data["funds"] if f["count"])
    priority = sum(1 for f in data["funds"] if SEVERITY_RANK.get(f["severity"], 0) >= 3)
    logger.info(
        "%s — %d funds (%d with signals, %d priority), %d detectors, %d not run -> %s",
        data["run_id"], len(data["funds"]), flagged, priority, len(data["tests"]),
        len(data["skipped"]) + len(data["failed"]), output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
