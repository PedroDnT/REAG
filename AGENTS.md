**AGENTS Guidelines for REAG**

This document provides concrete, repeatable guidance for automated agents operating within this repository. It covers build, lint, test workflows, code styling expectations, and any policy rules (Cursor, Copilot) that may affect edits. Maintainers may extend this file as the project evolves. When in doubt, prefer minimal, surgical changes aligned with existing conventions.


**1. Scope & Audience**
- Applies to all agent‑level edits in this repository.
- Primary emphasis is Python-based code (per root `requirements.txt`, `tests/`, and `src/`). Where other stacks exist, follow their dedicated tooling and add guidance here.
- Section cross‑references to Cursor rules (`.cursor/rules/`, `.cursorrules`) and Copilot guidance (`.github/copilot-instructions.md`) if present.


**2. Build / Lint / Test Workflow**
- Always prefer deterministic, local reproductions using the project’s tooling before changes enter CI.
- When possible, run a focused test to verify a targeted change, then broaden to full test suite if time allows.

**3. Python Environment**
- Use the repository’s virtual environment when available.
- Activate: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` on Windows.
- Install dependencies: `pip install -r requirements.txt` (and `requirements-dev.txt` if present).
- Ensure the Python version matches the project’s CI (e.g., `pyproject.toml` or CI config may specify a minimum Python).


**A. Commands: Build / Lint / Tests**
- General
  - Build (if project has build steps): run the project’s build script or a representative checker. If no build step is defined, this can be a no‑op.
  - Lint: use the project’s standard linter. If not specified, adopt `ruff` as a fast, cross‑stack linter.
  - Type check: use `mypy` when typing is used; otherwise skip.
  - Tests: `pytest -q` by default; report a concise summary on success/failure.

- Python tests (pytest)
  - Run all tests: `pytest -q` or `pytest` (respect CI verbosity).
  - Run a single test by file: `pytest tests/path/to/file_test.py`.
  - Run a single test by function: `pytest tests/path/to/file_test.py::test_function`.
  - Run tests with a keyword filter: `pytest -k "pattern"`.
  - Run with verbose output for a failing test: `pytest -q -k <name> -vv`.
  - Run a subset via marker: `pytest -m <tag>` (e.g., `-m unit`).
  - Coverage (optional): `pytest --maxfail=1 --disable-warnings -q --cov=src`.

- Type checking (mypy)
  - Run: `mypy src tests`.
  - If strict mode is enabled in your config, ensure type coverage is meaningful and incremental.

- Formatting / imports (Prettier/Black/Isort assumptions)
  - If Black is configured: `black src tests`.
  - If isort is configured: `isort -rc src tests` or rely on `ruff check --fix` for automated reformatting.
  - If a pre-commit hook exists, rely on it to enforce formatting prior to commit.

- Node/JS or other stacks
  - If a `package.json` exists, include:
    - Install: `npm ci` or `pnpm install`.
    - Lint: `npm run lint`.
    - Test: `npm test` or `npm test -- -t "Name"` for single test.
- CI considerations
  - CI environments should mirror local commands where possible.
  - Prefer `CI=true` to simulate CI conditions locally when needed.

**B. Project Workflows & Commands**
- Data collection and analysis (Jupyter)
  - Collect CVM data: `jupyter lab notebooks/01_data_collection.ipynb`
  - Identify REAG funds: `jupyter lab notebooks/02_identify_reag_funds.ipynb`
  - Flow analysis: `jupyter lab notebooks/03_flow_analysis.ipynb`
  - Anomaly detection: `jupyter lab notebooks/04_anomaly_detection.ipynb`
- Public report generation (scripted)
  - Markdown report: `python scripts/generate_public_report.py --format markdown`
  - HTML report: `python scripts/generate_public_report.py --format html`
  - JSON report: `python scripts/generate_public_report.py --format json`
  - Custom output path: `python scripts/generate_public_report.py --format html --output meu_relatorio.html`
- Data outputs (expected artifacts)
  - Processed data: `data/processed/*.csv`
  - Anomaly reports: `reports/*.csv`
  - Aggregated public report: `reports/public_report.[md|html|json]`


**C. How to Run a Single Test (Patterns)**
- Python/pytest: `pytest tests/module.py::TestClass::test_method` or `pytest tests/module.py::test_function`.
- If you use `-k` for keyword, ensure pattern uniquely identifies the test to avoid flakiness.
- Use markers to isolate test families (e.g., `-m unit`, `-m slow`).


**2. Code Style Guidelines**
- Language focus: Python (but apply general software carpentry patterns to other languages when present).

- General philosophy
  - Write readable, maintainable code first; performance if obvious later.
  - Favor small, well-named functions; limit cognitive load per function.
  - Minimize side effects and hidden state; prefer explicit inputs/outputs.

- Imports
  - Grouping: standard library, third‑party, local modules; separate groups with a blank line.
  - Avoid wildcard imports; prefer explicit names.
  - Resolve path aliases consistently; ensure IDE/linters hyper‑resolve imports.

- Formatting
  - Follow the repo’s formatter config (likely Black with a configured line length, and Prettier/Pre-commit for JS if present).
  - 2‑space indentation for Python; ensure consistent newline at end of file.
  - No trailing whitespace; avoid long lines; wrap thoughtfully.

- Typing & types
  - Use type hints for public APIs; prefer `Protocol` or `TypedDict` for structural constraints.
  - From __future__ import annotations can help with forward references.
  - Avoid `Any` where possible; use precise types or `Unknown` with runtime guards.

- Naming conventions
  - Functions and variables: snake_case; classes: PascalCase; constants: UPPER_SNAKE_CASE.
  - Descriptive names; avoid over-abbreviating. Async functions may end with `Async` suffix if not obvious from usage.

- Error handling
  - Do not swallow errors; raise with context or propagate to caller.
  - Define project‑level error hierarchy: `AppError`, `ValidationError`, `ServiceError`, etc.
  - Use `try/except` blocks around I/O or external calls; log and re‑raise with additional metadata.
  - Avoid catching broad exceptions; catch specific error classes first.

- Logging
  - Use `logging` module; configure a module‑level logger: `LOGGER = logging.getLogger(__name__)`.
  - Do not print directly for user‑facing errors; rely on structured logs.

- Testing practice
  - Tests should be deterministic, isolated, and fast.
  - Use fixtures to reduce duplication; avoid brittle tests tied to implementation details.
  - Name tests clearly; reflect behavior and edge cases. Include docstrings in tests when non-obvious.

- Documentation
  - Public APIs should be documented with docstrings; follow project style (Google/NumPy/Sphinx as per convention).
  - Update README or API docs when public behavior changes.

- Security & validation
  - Validate inputs at boundaries; sanitize and escape outputs for UI or logs.
  - Be mindful of secrets exposure in logs; never log sensitive values.

- Performance considerations
  - Avoid heavy work in module import paths; prefer lazy initialization when appropriate.
  - Look for obvious N+1 patterns or synchronous I/O on hot paths and propose refactors.

- Accessibility & UX (UI codebases)
  - Ensure semantic HTML and accessibility attributes when UI exists; keep focus order intuitive.

- Versioning & compatibility
  - Document breaking changes; bump version numbers appropriately; update changelog.


**3. Cursor Rules (Cursor) and Copilot Rules**
- Cursor rules: If `.cursor/rules/` or `.cursorrules` exist, apply them strictly. Edits should respect linting and constraints there.
- Copilot rules: If `.github/copilot-instructions.md` exists, follow its guidance. Do not bypass repo conventions for speed.


**4. Existing AGENTS.md (Migration)**
- If an AGENTS.md exists elsewhere, merge improvements rather than duplicating.
- Keep a single source of truth; reconcile conflicting guidelines.


**5. Quality Gates & Validation**
- Local checks before commit: `lint && typecheck` when applicable.
- Run a single, targeted test first; expand to full suite if needed.
- Ensure tests pass on CI with the same commands used locally.
- Formatting and linting should pass before code is merged.


**6. Maintenance & Evolution**
- Revisit guidelines after major tooling upgrades or rebuilds.
- Keep this doc lightweight but precise; include examples where helpful.
- Schedule periodic reviews or PR-driven updates to the doc.


**7. Update & Versioning**
- Include a short rationale for changes when you modify this file.
- Capture the PR/commit that introduced guideline changes for traceability.

**Rationale Log**
- 2025-02-14: Added repo-specific workflows and report commands to streamline consistent execution paths.


**8. Quick Start Snippet**
- Activate venv: `source venv/bin/activate`.
- Install: `pip install -r requirements.txt`.
- Lint: `ruff check src tests`.
- Test: `pytest -q`.
- Format: `black src tests`.


If you want me to tailor this to your exact stack, let me know what languages and tools are in scope, and I’ll refine the commands and conventions accordingly.


## Cursor Cloud specific instructions

Environment: Python-only toolkit. The system interpreter is Python 3.12 (matches CI),
but it is externally-managed (PEP 668), so dependencies live in a virtualenv at
`/workspace/venv` created by the startup update script. There is no server, database,
or Node build — everything runs locally against CSV/JSON/HTML files.

- Activate the environment with `source venv/bin/activate`, or call tools directly
  (`venv/bin/pytest`, `venv/bin/ruff`, `venv/bin/python`). The update script keeps
  `requirements.txt` + `requirements-dev.txt` installed in this venv.
- Lint/test commands are the ones in CI (`.github/workflows/ci.yml`) and the Quick
  Start above: `ruff check .`, `pytest -q -m "not eval"`, `pytest -q -m eval`. The
  full test + eval suites are self-contained (synthetic fixtures/mocks) and need no
  network or external services.
- Gotcha: the entry-point scripts `scripts/run_investigation.py` and
  `scripts/generate_public_report.py` do `from config...`/`from src...` but do NOT add
  the repo root to `sys.path`. Run them from `/workspace` with `PYTHONPATH=.`
  (e.g. `PYTHONPATH=. venv/bin/python scripts/run_investigation.py ...`) or `pytest`
  handles this automatically via `pythonpath = ["."]` in `pyproject.toml`.
  (`scripts/build_dashboard.py` inserts its own path and does not need this.)
- Running an investigation needs CVM-shaped CSV inputs in `data/raw/` (gitignored).
  Real data comes from `CVMCollector` (network to `https://dados.cvm.gov.br`); for a
  deterministic offline run, the repo's own `evals/fixtures.py` generates labeled
  synthetic universes. Typical flow: `run_investigation.py` -> then
  `build_dashboard.py --run reports/investigation/<run_id>` for a self-contained HTML
  dashboard.
- `data/raw/*`, `data/processed/*`, `reports/*` and `venv/` are gitignored; generated
  run outputs and demo data are never committed. `public/index.html` IS tracked — do
  not overwrite it when building demo dashboards (write to another path).
- Optional integrations degrade gracefully when absent: the `market_data` analyzer is
  skipped without `yfinance` (`requirements-optional.txt`), and context enrichment is
  skipped without `EXA_API_KEY`. Neither is required for tests, evals, or a normal run.
