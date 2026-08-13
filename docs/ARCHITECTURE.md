# REAG Architecture Overview

## Project Purpose

REAG is a Python-based financial fraud detection toolkit for analyzing Brazilian investment fund data from CVM (Comissão de Valores Mobiliários). It implements anomaly detection, Benford's Law analysis, and fraud pattern recognition based on documented Brazilian fund-industry cases.

---

## Directory Structure

```
REAG/
├── config/             # Centralized configuration
│   ├── settings.py     # Config class (URLs, directories, thresholds)
│   └── constants.py    # Domain-specific thresholds and magic numbers
├── src/                # Application source code
│   ├── analyzers/      # Fraud detection engines
│   │   ├── base.py     # BaseAnalyzer abstract class
│   │   ├── anomaly_detector.py
│   │   ├── benford_law.py
│   │   ├── concentration.py
│   │   ├── enhanced_phantom_assets.py
│   │   ├── fraud_schemes.py
│   │   ├── market_data.py
│   │   └── peer_comparison.py
│   ├── collectors/     # Data ingestion from CVM
│   │   └── cvm_collector.py
│   ├── enrichment/     # External context enrichment
│   │   ├── interfaces.py   # Protocol-based abstractions
│   │   ├── exa_provider.py
│   │   └── context_writer.py
│   ├── explain/        # Human-readable output generation
│   │   ├── explainer.py
│   │   ├── signal_registry.py
│   │   └── charts.py
│   ├── processors/     # Data transformation and cleaning
│   │   └── data_processor.py
│   └── utils/          # Cross-cutting utilities
│       ├── caching.py
│       ├── reporting.py
│       └── validation.py
├── scripts/            # CLI entry points
│   ├── run_investigation.py
│   └── generate_public_report.py
├── tests/              # Test suite (pytest)
├── notebooks/          # Jupyter analysis notebooks
├── data/               # Data directory (raw/processed)
├── reports/            # Generated reports
└── docs/               # Documentation
```

---

## Architectural Patterns

### 1. Layered Architecture

The codebase follows a clear layered structure:

| Layer | Package | Responsibility |
|-------|---------|---------------|
| **Collection** | `src/collectors` | Fetches raw data from CVM APIs |
| **Processing** | `src/processors` | Cleans, normalizes, and transforms data |
| **Analysis** | `src/analyzers` | Runs fraud detection algorithms |
| **Enrichment** | `src/enrichment` | Adds external context to findings |
| **Explanation** | `src/explain` | Generates human-readable outputs |
| **Utilities** | `src/utils` | Cross-cutting concerns (caching, validation, reporting) |
| **Configuration** | `config/` | Centralized settings and constants |

### 2. Analyzer Pattern (Strategy)

All analyzers follow a common pattern defined by `BaseAnalyzer`:

- Abstract `analyze()` method returning a `pd.DataFrame`
- Shared `generate_report()`, `validate_dataframe()`, and `log()` utilities
- Each analyzer can operate independently on the same data

### 3. Protocol-Based Abstraction (Enrichment)

The `enrichment` package uses Python's `Protocol` type for provider abstraction:

```python
class ContextProvider(Protocol):
    def search(self, query: str, ...) -> list[SearchResult]: ...
    def fetch(self, urls: list[str]) -> list[dict[str, Any]]: ...
```

This allows swapping enrichment providers (Exa, Perplexity) without changing consumer code.

### 4. Signal Registry (Configuration-Driven)

`signal_registry.py` defines each fraud signal as a `SignalDefinition` dataclass, centralizing:
- Finding metadata (title, explanation)
- Evidence fields and entity types
- Severity calculation rules
- Next steps and caveats

### 5. Centralized Constants

`config/constants.py` centralizes domain-specific thresholds (Z-score limits, HHI thresholds, Ponzi detection parameters). Analyzers import these constants rather than hardcoding values, ensuring consistency across the system.

---

## Best Practices Already in Place

1. **Clear module boundaries**: Each `src/` subpackage has a well-defined `__init__.py` with `__all__` exports
2. **Consistent logging**: All modules use `logging.getLogger(__name__)` for structured logging
3. **Type hints**: Most function signatures include type annotations
4. **Data validation**: `validate_dataframe()` provides column-existence checks before processing
5. **Configuration separation**: `Config` class and `constants.py` separate tunable parameters from logic
6. **Test coverage**: 200 tests covering unit, integration, and feature testing with shared fixtures in `conftest.py`
7. **Protocol-based abstractions**: `ContextProvider` protocol allows provider-agnostic enrichment
8. **Signal Registry pattern**: Declarative signal definitions decouple detection from explanation

---

## Improvement Recommendations

### Short-Term (Low Risk)

1. **Consistent `BaseAnalyzer` adoption**: Ensure all analyzers extend `BaseAnalyzer` for a uniform interface. `AnomalyDetector` now extends it; consider extending it for `BenfordLawAnalyzer`, `ConcentrationAnalyzer`, `PeerComparisonAnalyzer`, and `FraudSchemeDetector` over time.

2. **Constants usage**: Continue replacing any remaining hardcoded thresholds with imports from `config/constants.py` to maintain a single source of truth.

3. **Add `py.typed` marker**: Include a `py.typed` file in `src/` to enable downstream type checking (PEP 561).

### Medium-Term (Moderate Effort)

4. **Pipeline/Orchestrator pattern**: Introduce a pipeline abstraction in `scripts/run_investigation.py` to formalize the data flow (collect → process → analyze → enrich → explain) and make it easier to add or reorder steps.

5. **Dependency injection for Config**: Pass configuration through constructor injection consistently rather than relying on `Config()` defaults. This improves testability and allows per-run configuration.

6. **Result schema standardization**: Define a common result dataclass or TypedDict for analyzer outputs (e.g., `AnalysisResult` with `severity`, `fraud_risk`, `evidence` fields) to make downstream aggregation more robust.

### Long-Term (Scalability)

7. **Async data collection**: For large-scale analyses, the `CVMCollector` could benefit from async HTTP (e.g., `httpx` or `aiohttp`) to parallelize downloads.

8. **Plugin architecture for analyzers**: Use a registry or entry-point mechanism so new analyzers can be added without modifying `__init__.py` or core orchestration code.

9. **Database backend**: Replace CSV-based data storage with a database (e.g., DuckDB for analytical queries or SQLite for portability) to handle growing data volumes.

10. **Containerization**: Add a `Dockerfile` and `docker-compose.yml` for reproducible environments, especially for Jupyter notebooks and data processing pipelines.

---

## Data Flow

```
CVM APIs
  │
  ▼
CVMCollector (collectors/)
  │  Downloads ZIP/CSV files
  ▼
DataProcessor (processors/)
  │  Normalizes columns, types, CNPJs
  ▼
┌─────────────────────────────────────────┐
│          Analyzers (analyzers/)          │
│  AnomalyDetector  │  BenfordLaw         │
│  FraudSchemes     │  Concentration      │
│  PeerComparison   │  PhantomAssets      │
│  MarketData                             │
└─────────────────────────────────────────┘
  │
  ▼
SignalRegistry + Explainer (explain/)
  │  Maps raw findings to human-readable briefs
  ▼
Reports (reports/, HTML/Markdown/JSON)
```

---

## Testing Strategy

- **Unit tests**: Cover individual analyzer methods with synthetic data (`conftest.py` fixtures)
- **Integration tests**: Validate end-to-end workflows (marked with `@pytest.mark.integration`)
- **Configuration**: `pyproject.toml` with `testpaths = ["tests"]` and `pythonpath = ["."]`
- **Markers**: `slow` for performance-sensitive tests, `integration` for network/filesystem tests
- **Run command**: `pytest -q` (or `pytest -v --tb=short` per `addopts`)
