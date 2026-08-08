# funds_fraud_alert

Statistical fraud detection for Brazilian investment funds, built on public CVM
filings.

The toolkit ingests the CVM's open datasets — informe diário (daily NAV, flows,
quotaholder counts), CDA (portfolio composition) and cadastro (fund registry) —
and runs a battery of detectors over them, producing per-fund findings with
plain-language briefs explaining what was flagged and what would corroborate it.

Detection patterns are drawn from documented cases, notably the Banco Master /
REAG scheme: circular fund-to-fund flows, phantom assets, valuation smoothing,
window dressing, and cross-fund issuer concentration.

> **Findings are leads, not proof.** Every detector produces statistical red
> flags that require corroboration against records this toolkit cannot see —
> subscription ledgers, bank transfers, counterparty documentation. Nothing here
> establishes wrongdoing on its own.

## Install

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Requirements are split so you install only what you need:

| File | Contents |
|---|---|
| `requirements.txt` | Core runtime: pandas, numpy, requests, matplotlib, tqdm |
| `requirements-dev.txt` | pytest, hypothesis, ruff, playwright |
| `requirements-optional.txt` | `yfinance`, for the optional market-price validator |
| `requirements-notebooks.txt` | JupyterLab, seaborn, for `notebooks/` |

## Collect data

CVM publishes monthly ZIPs at <https://dados.cvm.gov.br/dados>. `CVMCollector`
downloads and extracts them into `data/raw/`:

```python
from src.collectors.cvm_collector import CVMCollector

CVMCollector().download_period(2024, 1, 2024, 12)
```

CDA is available from January 2023 onward; informe diário from January 2021.

## Run an investigation

```bash
python scripts/run_investigation.py \
    --informe data/raw/inf_diario_fi_202401.csv \
    --cda     data/raw/cda_fi_202401.csv \
    --cadastro data/raw/cad_fi.csv \
    --strict
```

Outputs land in `reports/investigation/<run_id>/`:

- `findings/*.csv` — one file per detector
- `briefs/` — per-entity HTML and Markdown explanations
- `summary.json` — run metadata, finding counts, and which analyzers ran

`--analysis` selects individual detectors; `--help` lists them. There is also a
guided terminal flow at `scripts/investigation_tui.py`.

**Use `--strict` in automation.** It exits non-zero if any analyzer crashed. A
report with no findings because a detector died looks exactly like a clean
result, and `summary.json`'s `execution` block records which analyzers failed or
were skipped for lack of inputs.

## Detectors

| Area | Modules |
|---|---|
| Flow and NAV | `anomaly_detector` (flow z-scores, PL drops, redemption runs, flow/performance divergence) |
| Fraud schemes | `fraud_schemes` (circular flow, layered funds, asset inflation, shell networks) |
| Portfolio | `enhanced_phantom_assets`, `portfolio_reconciliation`, `concentration`, `cost_basis_analyzer` |
| Valuation | `valuation_smoothing`, `window_dressing`, `price_divergence`, `benford_law` |
| Structure | `cross_fund_issuer`, `manager_network`, `fund_lifecycle`, `quotaholder_analyzer`, `peer_comparison` |
| Market data | `market_data` — optional, requires `yfinance` |

### Two ways to detect price manipulation

`price_divergence` works entirely offline: for each asset held by two or more
funds on the same date, it compares each fund's declared unit price
(`VL_MERCADO / QT_POS`) against the cross-fund median. It needs no external API
and covers unlisted credit — CRI, CRA, debêntures, cotas — which is where
mismarking is most likely.

`market_data` compares declared prices against real B3 closes via `yfinance`.
It is optional because yfinance scrapes Yahoo's undocumented endpoints and only
covers listed equities and ETFs. Install `requirements-optional.txt` to enable
it.

## Reports

```bash
python scripts/generate_public_report.py --format html --output reports/public.html
```

Produces an anonymized summary (fund CNPJs replaced with opaque IDs) in
Markdown, HTML or JSON.

## Tests and evals

```bash
pytest -q -m "not eval"   # unit, integration and property tests
pytest -q -m eval         # detection-quality evaluations
ruff check .
```

The eval suite is separate from the tests. It builds synthetic fund universes
with *labeled* injected fraud and measures each detector's precision, recall and
— most importantly — its false-positive rate against a clean universe, checked
against committed baselines in `evals/baseline.json`. A detector that fires on
clean data is worse than one that fires on nothing.

## Layout

```
config/       Settings and detection thresholds
src/
  collectors/ CVM downloads
  processors/ CSV parsing, normalization, flow derivation
  analyzers/  Detectors
  explain/    Findings -> human-readable briefs
  utils/      CNPJ handling, statistics, severity, caching
scripts/      CLI entry points
evals/        Detection-quality harness
notebooks/    Exploratory analysis
docs/         Architecture and guides
```

`src/utils/cnpj_utils.py` is the single source of truth for CNPJ handling. CNPJ
is the join key across every dataset here, so normalization lives in exactly one
place — see the module docstring for the rules.

## License

MIT. See [LICENSE](LICENSE).
