"""Score each detector against labeled synthetic fraud.

Two numbers per detector matter, and they are not equally important:

- **Recall** — of the funds carrying an injected anomaly, how many were flagged.
- **False-positive rate on the clean universe** — of the funds carrying nothing,
  how many were flagged anyway. This is the one that decides whether a detector
  is usable in practice. A detector that fires on clean data trains its reader
  to ignore it, at which point its correct findings stop mattering too.

Run directly for a report:

    python -m evals.run_eval
    python -m evals.run_eval --write-baseline
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from config.settings import Config
from evals import fixtures
from src.analyzers.anomaly_detector import AnomalyDetector
from src.analyzers.benford_law import BenfordLawAnalyzer
from src.analyzers.price_divergence import CrossFundPriceDivergenceAnalyzer
from src.analyzers.quotaholder_analyzer import QuotaholderAnalyzer
from src.analyzers.valuation_smoothing import ValuationSmoothingAnalyzer
from src.analyzers.window_dressing import WindowDressingDetector

logger = logging.getLogger(__name__)

BASELINE_PATH = Path(__file__).parent / "baseline.json"


@dataclass
class SignalMetrics:
    """Detection quality for one signal."""

    signal: str
    injected_funds: int
    detected_funds: int
    true_positives: int
    false_negatives: int
    clean_universe_flags: int
    clean_universe_funds: int

    @property
    def recall(self) -> float:
        if not self.injected_funds:
            return 0.0
        return self.true_positives / self.injected_funds

    @property
    def false_positive_rate(self) -> float:
        """Share of unlabeled funds flagged in a universe with no fraud."""
        if not self.clean_universe_funds:
            return 0.0
        return self.clean_universe_flags / self.clean_universe_funds

    def to_dict(self) -> dict:
        data = asdict(self)
        data["recall"] = round(self.recall, 4)
        data["false_positive_rate"] = round(self.false_positive_rate, 4)
        return data


# ---------------------------------------------------------------------------
# Detector adapters
#
# Each takes a universe and returns the set of CNPJs it flagged, normalizing
# away the differing output shapes of the analyzers.
# ---------------------------------------------------------------------------


def _flagged(df: pd.DataFrame | None, column: str = "CNPJ_FUNDO") -> set[str]:
    if df is None or df.empty or column not in df.columns:
        return set()
    return set(df[column].dropna().astype(str))


def detect_redemption_run(universe) -> set[str]:
    return _flagged(AnomalyDetector(config=Config()).detect_runs(universe.informe))


def detect_pl_drop(universe) -> set[str]:
    return _flagged(AnomalyDetector(config=Config()).detect_pl_drops(universe.informe))


def detect_valuation_smoothing(universe) -> set[str]:
    return _flagged(ValuationSmoothingAnalyzer(config=Config()).analyze(universe.informe))


def detect_window_dressing(universe) -> set[str]:
    return _flagged(WindowDressingDetector(config=Config()).analyze(universe.informe))


def detect_price_divergence(universe) -> set[str]:
    return _flagged(CrossFundPriceDivergenceAnalyzer(config=Config()).analyze(universe.cda))


def detect_quotaholder_exodus(universe) -> set[str]:
    return _flagged(QuotaholderAnalyzer(config=Config()).analyze(universe.informe))


def detect_benford_violation(universe) -> set[str]:
    """Flag funds whose subscription flows fail the Benford chi-square test."""
    analyzer = BenfordLawAnalyzer()
    flagged = set()
    for cnpj, group in universe.informe.groupby("CNPJ_FUNDO"):
        result = analyzer.analyze_series(group["CAPTC_DIA"], series_name=str(cnpj))
        if result.get("is_significant"):
            flagged.add(str(cnpj))
    return flagged


DETECTORS = {
    "redemption_run": detect_redemption_run,
    "pl_drop": detect_pl_drop,
    "valuation_smoothing": detect_valuation_smoothing,
    "window_dressing": detect_window_dressing,
    "cross_fund_price_divergence": detect_price_divergence,
    "benford_violation": detect_benford_violation,
    "quotaholder_exodus": detect_quotaholder_exodus,
}


def evaluate_signal(signal: str, n_funds: int, n_days: int, seed: int) -> SignalMetrics:
    """Score one detector against its injector, and against clean data.

    Args:
        signal: Key present in both fixtures.INJECTORS and DETECTORS
        n_funds: Universe size
        n_days: Universe length in business days
        seed: RNG seed, fixed so results are reproducible

    Returns:
        SignalMetrics for this signal
    """
    detect = DETECTORS[signal]
    inject = fixtures.INJECTORS[signal]

    clean = fixtures.make_clean_universe(n_funds=n_funds, n_days=n_days, seed=seed)
    clean_flags = detect(clean)

    injected = inject(clean)
    labeled = injected.funds_labeled(signal)
    detected = detect(injected)

    return SignalMetrics(
        signal=signal,
        injected_funds=len(labeled),
        detected_funds=len(detected),
        true_positives=len(detected & labeled),
        false_negatives=len(labeled - detected),
        clean_universe_flags=len(clean_flags),
        clean_universe_funds=clean.informe["CNPJ_FUNDO"].nunique(),
    )


def run_all(
    n_funds: int = fixtures.DEFAULT_FUNDS,
    n_days: int = fixtures.DEFAULT_DAYS,
    seed: int = 42,
) -> dict[str, SignalMetrics]:
    """Evaluate every signal that has both an injector and a detector."""
    return {
        signal: evaluate_signal(signal, n_funds, n_days, seed)
        for signal in sorted(DETECTORS)
    }


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text())


def write_baseline(results: dict[str, SignalMetrics], *, n_funds: int, n_days: int, seed: int) -> None:
    """Persist current metrics as the regression floor."""
    payload = {
        "universe": {"n_funds": n_funds, "n_days": n_days, "seed": seed},
        "signals": {signal: metrics.to_dict() for signal, metrics in results.items()},
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def format_report(results: dict[str, SignalMetrics]) -> str:
    lines = [
        f"{'signal':<30} {'recall':>8} {'TP':>4} {'FN':>4} {'clean FP rate':>14}",
        "-" * 64,
    ]
    for signal, m in results.items():
        lines.append(
            f"{signal:<30} {m.recall:>8.2f} {m.true_positives:>4} "
            f"{m.false_negatives:>4} {m.false_positive_rate:>14.2f}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funds", type=int, default=fixtures.DEFAULT_FUNDS)
    parser.add_argument("--days", type=int, default=fixtures.DEFAULT_DAYS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Overwrite evals/baseline.json with the current metrics.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    results = run_all(n_funds=args.funds, n_days=args.days, seed=args.seed)
    print(format_report(results))

    if args.write_baseline:
        write_baseline(results, n_funds=args.funds, n_days=args.days, seed=args.seed)
        print(f"\nBaseline written to {BASELINE_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
