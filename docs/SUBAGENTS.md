# Financial Fraud Investigation Subagents

This document defines focused subagents to support financial fraud investigations within REAG. Each subagent is designed to be small, composable, and aligned with existing repo workflows.

## Subagent 1: Data Intake & Validation

**Purpose**: Acquire raw datasets, validate schema, and produce clean, versioned inputs for downstream analysis.

**Responsibilities**
- Collect data from approved sources and store under `data/raw/`.
- Validate schema consistency, required fields, and date ranges.
- Produce cleaned outputs in `data/processed/`.

**Inputs**
- Raw source files (CSV/JSON/Excel) or API extracts.

**Outputs**
- Validated data summary.
- Cleaned datasets in `data/processed/*.csv`.

**Recommended Commands**
- `jupyter lab notebooks/01_data_collection.ipynb`
- `python scripts/generate_public_report.py --format json`

**Success Criteria**
- Schema validation passes.
- Cleaned data is reproducible and tracked.

---

## Subagent 2: Benford & Distribution Checks

**Purpose**: Detect irregular digit distributions and numerical anomalies.

**Responsibilities**
- Run Benford’s Law checks on key numerical fields.
- Flag deviations, summarize by entity and time range.

**Inputs**
- Cleaned datasets from `data/processed/`.

**Outputs**
- Benford deviation report.
- Candidate anomalies for investigation.

**Recommended Commands**
- `jupyter lab notebooks/04_anomaly_detection.ipynb`

**Success Criteria**
- Deviations are documented with thresholds and rationale.

---

## Subagent 3: Flow & Network Analysis

**Purpose**: Identify suspicious movement patterns and abnormal flows.

**Responsibilities**
- Analyze inflow/outflow trends and structural breaks.
- Build network/relationship graphs where applicable.

**Inputs**
- Processed fund flows and entity metadata.

**Outputs**
- Flow anomaly report.
- Entity-to-entity relationship summary.

**Recommended Commands**
- `jupyter lab notebooks/03_flow_analysis.ipynb`

**Success Criteria**
- Abnormal flow clusters are explained and ranked.

---

## Subagent 4: Market Data Enrichment

**Purpose**: Enrich investigations with market, macro, or benchmark context.

**Responsibilities**
- Incorporate market indices, sector benchmarks, or macro indicators.
- Normalize results to improve comparability.

**Inputs**
- Processed datasets and external market data.

**Outputs**
- Enriched datasets.
- Contextual impact summary.

**Recommended Commands**
- `python scripts/generate_public_report.py --format html`

**Success Criteria**
- Enrichment sources are documented and reproducible.

---

## Subagent 5: Entity Risk Profiling

**Purpose**: Aggregate signals into actionable risk scores.

**Responsibilities**
- Combine Benford, flow, and market indicators.
- Generate entity-level risk tiers with rationale.

**Inputs**
- Outputs from Subagents 2–4.

**Outputs**
- Risk score table and rationale notes.
- Ranked investigation queue.

**Success Criteria**
- Clear, auditable scoring logic with traceable inputs.

---

## Subagent 6: Reporting & Evidence Packaging

**Purpose**: Produce reproducible, compliant investigation outputs.

**Responsibilities**
- Assemble the public report and supporting artifacts.
- Ensure citations, assumptions, and methodology are captured.

**Inputs**
- Outputs from all prior subagents.

**Outputs**
- `reports/public_report.[md|html|json]`
- Summary tables and CSV artifacts.

**Recommended Commands**
- `python scripts/generate_public_report.py --format markdown`
- `python scripts/generate_public_report.py --format html`
- `python scripts/generate_public_report.py --format json`

**Success Criteria**
- Reports are reproducible and cite source outputs.

---

## Subagent 7: QA, Audit, & Test Gate

**Purpose**: Validate findings, reproducibility, and quality gates.

**Responsibilities**
- Run targeted tests and checks on changes.
- Verify data lineage and ensure no silent failures.

**Inputs**
- Code and data outputs from other subagents.

**Outputs**
- Test report summary.
- Audit notes for any deviations.

**Recommended Commands**
- `pytest -q`
- `ruff check src tests`
- `mypy src tests`

**Success Criteria**
- Tests and checks pass or deviations are documented.
