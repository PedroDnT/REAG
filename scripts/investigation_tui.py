#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Imports follow the sys.path insertion above so this stays runnable as a
# standalone script (`python scripts/investigation_tui.py`).
from config.settings import Config  # noqa: E402
from scripts.run_investigation import build_parser, run_investigation, sanitize_run_id  # noqa: E402
from src.processors.data_processor import DataProcessor  # noqa: E402

InputFn = Callable[[str], str]
PrintFn = Callable[[str], None]
MenuOptions = dict[str, tuple[str, object]]

INVESTIGATION_PRESETS: dict[str, tuple[str, list[str]]] = {
    "1": (
        "Flow and liquidity red flags",
        ["flow", "quotaholder", "window_dressing", "valuation_smoothing"],
    ),
    "2": (
        "Portfolio and asset quality",
        ["phantom_assets", "cost_basis", "reconciliation", "cross_fund_issuer"],
    ),
    "3": (
        "Networks and fund relationships",
        ["schemes", "lifecycle", "manager_network"],
    ),
    "4": ("Full investigation", ["all"]),
}

REPORT_FORMATS = {
    "1": ("HTML", "html"),
    "2": ("Markdown", "md"),
    "3": ("HTML and Markdown", "both"),
}

ENRICHMENT_PROVIDERS = {
    "1": ("Exa", "exa"),
    "2": ("Perplexity", "perplexity"),
}

INPUT_MODES = {
    "1": ("Use default data discovery", "quick"),
    "2": ("Choose custom files and folders", "custom"),
}

FUND_SELECTION_MODES = {
    "1": ("Use all listed funds", "all"),
    "2": ("Search and select specific funds", "select"),
}


def _prompt_choice(
    prompt: str,
    options: MenuOptions,
    *,
    default: str,
    input_fn: InputFn,
    print_fn: PrintFn,
) -> str:
    """Prompt for a numbered menu selection and return the selected key."""
    while True:
        print_fn(prompt)
        for key, value in options.items():
            print_fn(f"  {key}. {value[0]}")
        answer = input_fn(f"Select an option [{default}]: ").strip() or default
        if answer in options:
            return answer
        print_fn("Invalid option, please try again.")


def _prompt_text(prompt: str, *, default: str, input_fn: InputFn) -> str:
    answer = input_fn(f"{prompt} [{default}]: ").strip()
    return answer or default


def _prompt_optional_text(prompt: str, *, input_fn: InputFn) -> str | None:
    answer = input_fn(f"{prompt} [optional]: ").strip()
    return answer if answer else None


def _prompt_yes_no(prompt: str, *, default: bool, input_fn: InputFn, print_fn: PrintFn) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        answer = input_fn(f"{prompt} [{default_label}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print_fn("Please answer with 'y' or 'n'.")


def _resolve_cadastro_path(values: dict[str, object], defaults: argparse.Namespace) -> Path | None:
    custom_path = values.get("cadastro")
    if isinstance(custom_path, str) and custom_path:
        return Path(custom_path)

    public_data_dir = values.get("public_data_dir")
    base = Path(public_data_dir) if isinstance(public_data_dir, str) and public_data_dir else Path(defaults.public_data_dir)
    candidates: list[Path] = []
    for pattern in ("cad_fi*.csv",):
        candidates.extend(base.glob(pattern))
        candidates.extend((base / "cadastro").glob(pattern))
        candidates.extend((base / "informe").glob(pattern))
        candidates.extend((base / "cda").glob(pattern))
    return candidates[0] if candidates else None


def _load_fund_catalog(*, cadastro_path: Path | None, print_fn: PrintFn) -> list[tuple[str, str]]:
    if cadastro_path is None or not cadastro_path.exists():
        print_fn("[warning] Cadastro file not found; running with all funds.")
        return []

    df = DataProcessor(Config()).read_cadastro(cadastro_path)
    if df.empty or "CNPJ_FUNDO" not in df.columns:
        print_fn("[warning] Cadastro file has no fund list; running with all funds.")
        return []
    if "DENOM_SOCIAL" not in df.columns:
        df = df.copy()
        df["DENOM_SOCIAL"] = ""

    rows = (
        df[["CNPJ_FUNDO", "DENOM_SOCIAL"]]
        .dropna(subset=["CNPJ_FUNDO"])
        .drop_duplicates(subset=["CNPJ_FUNDO"])
        .sort_values(["DENOM_SOCIAL", "CNPJ_FUNDO"], na_position="last")
    )
    return [
        (str(cnpj), str(name) if name is not None else "")
        for cnpj, name in rows[["CNPJ_FUNDO", "DENOM_SOCIAL"]].itertuples(index=False, name=None)
    ]


def _prompt_fund_selection(
    *,
    catalog: list[tuple[str, str]],
    input_fn: InputFn,
    print_fn: PrintFn,
) -> list[str]:
    if not catalog:
        return []

    selected: set[str] = set()
    print_fn("Fund selection mode enabled.")
    print_fn("Search by fund name or CNPJ. Type 'done' to finish.")
    while True:
        query = input_fn("Search term (name/CNPJ or 'done'): ").strip()
        if query.lower() == "done":
            break

        query_digits = "".join(ch for ch in query if ch.isdigit())
        query_lower = query.lower()
        matches = [
            item
            for item in catalog
            if not query
            or query_lower in item[1].lower()
            or (query_digits and query_digits in item[0])
        ]
        if not matches:
            print_fn("No funds found for this search.")
            continue

        shown = matches[:20]
        for idx, (cnpj, name) in enumerate(shown, start=1):
            label = f"{name} ({cnpj})" if name else cnpj
            print_fn(f"  {idx}. {label}")

        raw_selection = input_fn(
            "Select index(es) separated by comma, Enter to search again, or 'done': "
        ).strip()
        if not raw_selection:
            continue
        if raw_selection.lower() == "done":
            break

        tokens = [token.strip() for token in raw_selection.split(",") if token.strip()]
        invalid = [token for token in tokens if not token.isdigit() or not (1 <= int(token) <= len(shown))]
        if invalid:
            print_fn("Invalid selection; use the listed numeric indexes.")
            continue
        for token in tokens:
            selected.add(shown[int(token) - 1][0])
        print_fn(f"Selected funds: {len(selected)}")

    return sorted(selected)


def build_tui_args(*, input_fn: InputFn = input, print_fn: PrintFn = print) -> argparse.Namespace | None:
    parser = build_parser()
    defaults = parser.parse_args([])

    print_fn("REAG Investigation Assistant")
    print_fn("===========================")

    mode_key = _prompt_choice(
        "How would you like to provide data?",
        INPUT_MODES,
        default="1",
        input_fn=input_fn,
        print_fn=print_fn,
    )
    investigation_key = _prompt_choice(
        "What do you want to investigate?",
        INVESTIGATION_PRESETS,
        default="4",
        input_fn=input_fn,
        print_fn=print_fn,
    )

    raw_run_id = _prompt_text(
        "Run identifier",
        default=datetime.now().strftime("%Y%m%d_%H%M%S"),
        input_fn=input_fn,
    )
    run_id = sanitize_run_id(raw_run_id)
    if run_id != raw_run_id:
        print_fn(
            f"[warning] Run identifier {raw_run_id!r} is invalid; using {run_id!r} instead."
        )
    output_dir = _prompt_optional_text("Output directory", input_fn=input_fn)

    values = vars(defaults).copy()
    values["run_id"] = run_id
    values["output_dir"] = output_dir
    values["analysis"] = INVESTIGATION_PRESETS[investigation_key][1]
    values["explain"] = False
    values["explain_format"] = defaults.explain_format
    values["selected_cnpjs"] = []

    if INPUT_MODES[mode_key][1] == "custom":
        values["public_data_dir"] = _prompt_text(
            "Public/raw data directory",
            default=defaults.public_data_dir,
            input_fn=input_fn,
        )
        values["processed_data_dir"] = _prompt_text(
            "Processed data directory",
            default=defaults.processed_data_dir,
            input_fn=input_fn,
        )
        values["cadastro"] = _prompt_optional_text("Cadastro CSV path", input_fn=input_fn)
        values["informe"] = _prompt_optional_text("Informe CSV or processed file path", input_fn=input_fn)
        values["cda"] = _prompt_optional_text("CDA CSV path", input_fn=input_fn)

    fund_mode = _prompt_choice(
        "How do you want to scope funds?",
        FUND_SELECTION_MODES,
        default="1",
        input_fn=input_fn,
        print_fn=print_fn,
    )
    if FUND_SELECTION_MODES[fund_mode][1] == "select":
        cadastro_path = _resolve_cadastro_path(values, defaults)
        catalog = _load_fund_catalog(cadastro_path=cadastro_path, print_fn=print_fn)
        selected_cnpjs = _prompt_fund_selection(
            catalog=catalog,
            input_fn=input_fn,
            print_fn=print_fn,
        )
        if not selected_cnpjs:
            print_fn("[warning] No funds selected; running with all funds.")
        values["selected_cnpjs"] = selected_cnpjs

    values["enable_enrichment"] = _prompt_yes_no(
        "Enable external context enrichment?",
        default=False,
        input_fn=input_fn,
        print_fn=print_fn,
    )
    if values["enable_enrichment"]:
        provider_key = _prompt_choice(
            "Which enrichment provider do you want to use?",
            ENRICHMENT_PROVIDERS,
            default="1",
            input_fn=input_fn,
            print_fn=print_fn,
        )
        values["enrichment_provider"] = ENRICHMENT_PROVIDERS[provider_key][1]

    values["explain"] = _prompt_yes_no(
        "Generate report after analysis?",
        default=True,
        input_fn=input_fn,
        print_fn=print_fn,
    )
    if values["explain"]:
        report_key = _prompt_choice(
            "Which report format do you want?",
            REPORT_FORMATS,
            default="3",
            input_fn=input_fn,
            print_fn=print_fn,
        )
        values["explain_format"] = REPORT_FORMATS[report_key][1]

    print_fn("")
    print_fn("Planned investigation:")
    print_fn(f"- Focus: {INVESTIGATION_PRESETS[investigation_key][0]}")
    if values["selected_cnpjs"]:
        print_fn(f"- Fund scope: {len(values['selected_cnpjs'])} selected funds")
    else:
        print_fn("- Fund scope: all funds")
    print_fn(f"- Report generation: {'enabled' if values['explain'] else 'disabled'}")
    if values["explain"]:
        format_label = next(
            label for label, value in REPORT_FORMATS.values() if value == values["explain_format"]
        )
        print_fn(f"- Report format: {format_label}")
    print_fn(f"- Run id: {run_id}")
    print_fn(f"- Output directory: {output_dir or f'reports/investigation/{run_id}'}")

    if not _prompt_yes_no(
        "Start the investigation now?",
        default=True,
        input_fn=input_fn,
        print_fn=print_fn,
    ):
        print_fn("Investigation cancelled.")
        return None

    return argparse.Namespace(**values)


def _resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    return Config().REPORTS_DIR / "investigation" / args.run_id


def _print_result_summary(output_dir: Path, *, print_fn: PrintFn) -> None:
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        print_fn(f"Investigation finished. Outputs saved to {output_dir}")
        return

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    counts = payload.get("outputs", {}).get("counts", {})
    report_html = output_dir / "report.html"
    report_md = output_dir / "report.md"
    report_path = report_html if report_html.exists() else (report_md if report_md.exists() else None)

    print_fn("")
    print_fn("Investigation completed.")
    print_fn(f"- Summary: {summary_path}")
    if report_path.exists():
        print_fn(f"- Report: {report_path}")
    if counts:
        print_fn("- Findings generated:")
        for key in sorted(counts):
            print_fn(f"  - {key}: {counts[key]}")


def main(*, input_fn: InputFn = input, print_fn: PrintFn = print) -> int:
    args = build_tui_args(input_fn=input_fn, print_fn=print_fn)
    if args is None:
        return 1

    exit_code = run_investigation(args)
    output_dir = _resolve_output_dir(args)
    _print_result_summary(output_dir, print_fn=print_fn)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
