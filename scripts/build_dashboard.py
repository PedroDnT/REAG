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

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


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

        # An empty findings file means the detector ran and flagged nobody.
        # That is a clean result for every fund, and must not be filed as
        # "not applicable" -- treating "found nothing" as "said nothing" is the
        # exact conflation this page exists to prevent.
        tests[key] = {"key": key, "rows": int(len(frame))}
        if column is None:
            continue
        cnpjs = normalize_cnpj_series(frame[column]).dropna()
        for cnpj in cnpjs.unique():
            fund_hits.setdefault(str(cnpj), set()).add(key)

    # --- per-fund evidence, for the metric behind each hit -----------------
    evidence: dict[str, list[dict[str, Any]]] = {}
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
            evidence.setdefault(cnpj, []).append({
                "test": Path(source).stem if source else "",
                "title": item.get("title") or "",
                "severity": (item.get("severity") or "").upper(),
                "metric": item.get("metric") or "",
            })

    # --- the fund universe -------------------------------------------------
    in_scope = [normalize_cnpj(c) for c in (scope.get("selected_cnpjs") or [])]
    universe = sorted({c for c in in_scope if c} | set(fund_hits) | set(evidence))

    funds = []
    for cnpj in universe:
        hits = sorted(fund_hits.get(cnpj, set()))
        items = evidence.get(cnpj, [])
        by_test: dict[str, dict[str, Any]] = {}
        for item in items:
            current = by_test.get(item["test"])
            if not current or SEVERITY_RANK.get(item["severity"], 0) > SEVERITY_RANK.get(
                current["severity"], 0
            ):
                by_test[item["test"]] = item
        worst = max(
            (SEVERITY_RANK.get(i["severity"], 0) for i in items), default=0
        )
        funds.append({
            "cnpj": cnpj,
            "display": format_cnpj(cnpj),
            "name": names.get(cnpj, ""),
            "hits": hits,
            "detail": by_test,
            "severity": next((s for s, r in SEVERITY_RANK.items() if r == worst), ""),
            "count": len(hits),
        })

    funds.sort(key=lambda f: (-SEVERITY_RANK.get(f["severity"], 0), -f["count"], f["cnpj"]))

    return {
        "run_id": summary.get("run_id") or run_dir.name,
        "generated_at": summary.get("generated_at") or "",
        "scope": scope,
        "tests": [tests[k] for k in sorted(tests)],
        "entity_level": sorted(entity_level),
        "skipped": sorted(execution.get("skipped_analyzers") or []),
        "failed": sorted(execution.get("failed_analyzers") or []),
        "complete": bool(execution.get("complete", True)),
        "funds": funds,
    }


def render(data: dict[str, Any], *, fragment: bool = False) -> str:
    """Render the dashboard to a single HTML document."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    scope = data["scope"]
    where = ""
    if scope.get("fund_mode"):
        where = f"{scope['fund_mode'].replace('_', ' ')} · {scope.get('fund_identifier', '')}"

    body = f"""
<header class="masthead">
  <div class="masthead-id">
    <h1>Fund screening</h1>
    <p class="run">run <code>{html.escape(str(data['run_id']))}</code>{
        ' · ' + html.escape(where) if where else ''}</p>
  </div>
  <dl class="tallies">
    <div><dt>Funds in scope</dt><dd>{len(data['funds'])}</dd></div>
    <div><dt>Detectors run</dt><dd>{len(data['tests'])}</dd></div>
    <div><dt>Flagged</dt><dd>{sum(1 for f in data['funds'] if f['count'])}</dd></div>
  </dl>
</header>

{_coverage_banner(data)}

<main class="split">
  <section class="list-pane" aria-label="Funds">
    <div class="searchbar">
      <input id="q" type="search" autocomplete="off" spellcheck="false"
             placeholder="Search by CNPJ or fund name" aria-label="Search funds">
      <label class="only-flagged">
        <input type="checkbox" id="only"> Flagged only
      </label>
    </div>
    <p class="result-count" id="count" role="status"></p>
    <ol class="funds" id="funds"></ol>
  </section>

  <section class="detail-pane" id="detail" aria-live="polite">
    <div class="empty">
      <p>Select a fund to see what each detector reported.</p>
    </div>
  </section>
</main>

<footer>
  <p>Statistical red flags are leads, not proof. Every finding needs corroboration
     against records this toolkit cannot see — subscription ledgers, transfers,
     counterparty documentation.</p>
</footer>

<script id="data" type="application/json">{payload}</script>
<script>{_SCRIPT}</script>
"""

    if fragment:
        return f"<style>{_STYLE}</style>\n{body}"

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>Fund screening — {html.escape(str(data['run_id']))}</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def _coverage_banner(data: dict[str, Any]) -> str:
    """Say plainly when part of the battery did not run."""
    missing = data["failed"] + data["skipped"]
    if not missing:
        return (
            '<p class="coverage ok">Every detector ran. '
            'A fund with no flags was checked and came back clean.</p>'
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
        ". Those detectors report nothing either way; absence of a flag from them "
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
.run{margin:4px 0 0; color:var(--ink-faint); font-size:.82rem}
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
.coverage code{font-size:.82em}

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
  var unrun = D.failed.concat(D.skipped);
  var listEl = document.getElementById('funds');
  var countEl = document.getElementById('count');
  var detailEl = document.getElementById('detail');
  var qEl = document.getElementById('q');
  var onlyEl = document.getElementById('only');
  var selected = null;

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function label(key){ return key.replace(/_/g,' '); }

  function matches(f, q){
    if (!q) return true;
    return (f.cnpj.indexOf(q) !== -1) ||
           (f.display.toLowerCase().indexOf(q) !== -1) ||
           (f.name && f.name.toLowerCase().indexOf(q) !== -1);
  }

  function renderList(){
    var q = qEl.value.trim().toLowerCase().replace(/[.\-\/]/g,'');
    var flaggedOnly = onlyEl.checked;
    var rows = D.funds.filter(function(f){
      return matches(f, q) && (!flaggedOnly || f.count > 0);
    });

    countEl.textContent = rows.length + (rows.length === 1 ? ' fund' : ' funds') +
      (q || flaggedOnly ? ' of ' + D.funds.length : '');

    if (!rows.length){
      listEl.innerHTML = '<li class="no-hits"><p class="empty" style="padding:14px 20px">' +
        'No fund matches that search.</p></li>';
      return;
    }
    listEl.innerHTML = rows.map(function(f){
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
        return '<li class="test is-fired">' +
          '<div class="test-name"><span>' + esc(hit.title || label(key)) + '</span>' +
          '<span class="chip ' + esc(hit.severity) + '">' + esc(hit.severity) + '</span></div>' +
          (hit.metric ? '<p class="metric">' + esc(hit.metric) + '</p>' : '') +
          '</li>';
      }
      if (f.hits.indexOf(key) !== -1){
        // Flagged by the CSV but no brief line -- still a hit, shown without a metric.
        return '<li class="test is-fired"><div class="test-name"><span>' +
          esc(label(key)) + '</span><span class="chip LOW">flagged</span></div></li>';
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
            ' detectors flagged this fund</span>'
          : '<span class="verdict clear">No detector flagged this fund</span>') +
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
  onlyEl.addEventListener('change', renderList);

  renderList();
  if (D.funds.length && D.funds[0].count) renderDetail(D.funds[0].cnpj);
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
    logger.info(
        "%s — %d funds (%d flagged), %d detectors, %d not run -> %s",
        data["run_id"], len(data["funds"]), flagged, len(data["tests"]),
        len(data["skipped"]) + len(data["failed"]), output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
