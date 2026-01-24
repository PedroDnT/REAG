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


**B. How to Run a Single Test (Patterns)**
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


**8. Quick Start Snippet**
- Activate venv: `source venv/bin/activate`.
- Install: `pip install -r requirements.txt`.
- Lint: `ruff check src tests`.
- Test: `pytest -q`.
- Format: `black src tests`.


If you want me to tailor this to your exact stack, let me know what languages and tools are in scope, and I’ll refine the commands and conventions accordingly.
