"""Detection-quality regression gate.

Marked `eval` and excluded from the default test run: these measure whether the
detectors detect, not whether the code behaves as written. Run with

    pytest -q -m eval

A failure here means a change altered what the toolkit finds. That is sometimes
correct -- but it should never happen silently, which is the entire point.
"""

import pytest

from evals import fixtures
from evals.run_eval import DETECTORS, load_baseline, run_all

pytestmark = pytest.mark.eval

# Recall may not drop below the baseline at all. False-positive rate is allowed
# a little slack, since it is measured over a finite universe and a single fund
# flipping either way moves it by 1/n_funds.
RECALL_TOLERANCE = 0.0
FP_TOLERANCE = 0.05


@pytest.fixture(scope="module")
def baseline():
    data = load_baseline()
    if not data:
        pytest.skip("no evals/baseline.json; generate with python -m evals.run_eval --write-baseline")
    return data


@pytest.fixture(scope="module")
def results(baseline):
    universe = baseline["universe"]
    return run_all(
        n_funds=universe["n_funds"],
        n_days=universe["n_days"],
        seed=universe["seed"],
    )


def _signals(baseline):
    return sorted(baseline["signals"])


class TestNoRegression:

    def test_every_baseline_signal_is_still_evaluated(self, baseline, results):
        missing = set(baseline["signals"]) - set(results)
        assert not missing, f"signals dropped out of the eval sweep: {missing}"

    @pytest.mark.parametrize("signal", sorted(load_baseline().get("signals", {})))
    def test_recall_has_not_regressed(self, signal, baseline, results):
        expected = baseline["signals"][signal]["recall"]
        actual = results[signal].recall
        assert actual >= expected - RECALL_TOLERANCE, (
            f"{signal} recall fell from {expected:.2f} to {actual:.2f}: "
            f"the detector now misses injected fraud it used to catch"
        )

    @pytest.mark.parametrize("signal", sorted(load_baseline().get("signals", {})))
    def test_false_positive_rate_has_not_regressed(self, signal, baseline, results):
        expected = baseline["signals"][signal]["false_positive_rate"]
        actual = results[signal].false_positive_rate
        assert actual <= expected + FP_TOLERANCE, (
            f"{signal} false-positive rate rose from {expected:.2f} to {actual:.2f} "
            f"on a universe containing no fraud"
        )


class TestAbsoluteFloors:
    """Bounds that hold regardless of what the baseline happens to record."""

    @pytest.mark.parametrize("signal", sorted(DETECTORS))
    def test_detects_the_fraud_it_is_built_for(self, signal, results):
        assert results[signal].recall > 0.0, (
            f"{signal} detected none of the injected anomalies"
        )

    @pytest.mark.parametrize("signal", sorted(DETECTORS))
    def test_does_not_flag_most_of_a_clean_universe(self, signal, results):
        """A detector firing on half of clean data is noise, not a detector."""
        assert results[signal].false_positive_rate < 0.5, (
            f"{signal} flagged {results[signal].false_positive_rate:.0%} of funds "
            f"in a universe with nothing wrong in it"
        )


class TestHarnessIntegrity:
    """The harness itself must be sound, or its numbers mean nothing."""

    def test_every_detector_has_an_injector(self):
        assert set(DETECTORS) == set(fixtures.INJECTORS)

    def test_clean_universe_carries_no_labels(self):
        assert fixtures.make_clean_universe(n_funds=10, n_days=60).labels == set()

    def test_injectors_label_what_they_inject(self):
        clean = fixtures.make_clean_universe(n_funds=20, n_days=90)
        for signal, inject in fixtures.INJECTORS.items():
            injected = inject(clean)
            assert injected.funds_labeled(signal), f"{signal} injected nothing"
            assert clean.labels == set(), "injector mutated the clean universe"

    def test_universe_generation_is_deterministic(self):
        a = fixtures.make_clean_universe(n_funds=10, n_days=60, seed=7)
        b = fixtures.make_clean_universe(n_funds=10, n_days=60, seed=7)
        assert a.informe.equals(b.informe)
        assert a.cda.equals(b.cda)

    def test_different_seeds_give_different_universes(self):
        a = fixtures.make_clean_universe(n_funds=10, n_days=60, seed=1)
        b = fixtures.make_clean_universe(n_funds=10, n_days=60, seed=2)
        assert not a.informe["VL_QUOTA"].equals(b.informe["VL_QUOTA"])

    def test_generated_cnpjs_are_structurally_valid(self):
        from src.utils.cnpj_utils import is_valid_cnpj

        assert all(is_valid_cnpj(fixtures.fund_cnpj(i)) for i in range(100))

    def test_injectors_compose(self):
        """Applying several injectors accumulates labels rather than replacing."""
        universe = fixtures.make_clean_universe(n_funds=20, n_days=120)
        universe = fixtures.inject_pl_drop(universe)
        universe = fixtures.inject_redemption_run(universe)

        assert universe.funds_labeled("pl_drop")
        assert universe.funds_labeled("redemption_run")
