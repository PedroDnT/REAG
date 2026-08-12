"""The dashboard must distinguish "found nothing" from "said nothing".

A detector that never ran produces no findings, which in a plain CSV dump looks
exactly like a detector that ran and came back clean. The whole point of the
per-fund matrix is that those two are rendered differently, so the tests here
are mostly about that distinction surviving.
"""

import json

import pytest

from scripts.build_dashboard import format_cnpj, load_run, render

FUND_A = "12345678000190"
FUND_B = "11222333000181"


@pytest.fixture
def run_dir(tmp_path):
    """A minimal but structurally faithful investigation run."""
    root = tmp_path / "run"
    (root / "findings").mkdir(parents=True)
    (root / "entities" / f"FUND_{FUND_A}").mkdir(parents=True)

    (root / "summary.json").write_text(json.dumps({
        "run_id": "testrun",
        "scope": {"selected_cnpjs": [FUND_A, FUND_B], "fund_mode": "administrator",
                  "fund_identifier": "ACME"},
        "execution": {"complete": True, "failed_analyzers": [],
                      "skipped_analyzers": ["market_data"]},
    }))

    # Fired on FUND_A only.
    (root / "findings" / "runs.csv").write_text(
        f"CNPJ_FUNDO,RUN_LENGTH\n{FUND_A},7\n")
    # Ran, flagged nobody -- an empty file, not a missing one.
    (root / "findings" / "shell_networks.csv").write_text("")
    # Keyed by issuer, not by fund.
    (root / "findings" / "cross_fund_issuer.csv").write_text(
        "EMISSOR,num_funds\nBANCO X,4\n")

    (root / "entities" / f"FUND_{FUND_A}" / "evidence.json").write_text(json.dumps({
        "entity": {"entity_id": f"FUND_{FUND_A}", "entity_type": "FUND",
                   "cnpj_digits": FUND_A, "name": "ACME FIC FIM"},
        "evidence": [{"finding_id": "redemption_run", "title": "Redemption run",
                      "severity": "HIGH", "metric": "RUN_LENGTH: 7",
                      "source_ref": "findings/runs.csv"}],
    }))
    return root


class TestRanCleanIsNotTheSameAsNeverRan:

    def test_empty_findings_file_still_counts_as_a_detector_that_ran(self, run_dir):
        """The bug this caught on real data: four empty files vanished.

        They were filed as "not applicable" because an empty CSV has no columns
        to key on, so four detectors that ran and cleared every fund silently
        disappeared from the matrix.
        """
        data = load_run(run_dir)
        keys = [t["key"] for t in data["tests"]]
        assert "shell_networks" in keys
        assert "shell_networks" not in data["entity_level"]

    def test_skipped_analyzer_is_reported_separately_from_a_clean_result(self, run_dir):
        data = load_run(run_dir)
        assert data["skipped"] == ["market_data"]
        assert "market_data" not in [t["key"] for t in data["tests"]]

    def test_incomplete_coverage_is_stated_on_the_page(self, run_dir):
        page = render(load_run(run_dir))
        assert "Incomplete coverage" in page
        assert "not a clean result" in page

    def test_full_coverage_says_so(self, run_dir):
        summary = json.loads((run_dir / "summary.json").read_text())
        summary["execution"]["skipped_analyzers"] = []
        (run_dir / "summary.json").write_text(json.dumps(summary))
        page = render(load_run(run_dir))
        assert "Every detector ran" in page
        assert "Incomplete coverage" not in page


class TestFundMatrix:

    def test_a_flagged_fund_carries_its_metric(self, run_dir):
        fund = next(f for f in load_run(run_dir)["funds"] if f["cnpj"] == FUND_A)
        assert fund["hits"] == ["runs"]
        assert fund["severity"] == "HIGH"
        assert fund["detail"]["runs"]["metric"] == "RUN_LENGTH: 7"

    def test_a_fund_in_scope_with_no_findings_still_appears(self, run_dir):
        """Absence from every findings CSV is a result, not a reason to vanish."""
        funds = {f["cnpj"] for f in load_run(run_dir)["funds"]}
        assert FUND_B in funds
        clean = next(f for f in load_run(run_dir)["funds"] if f["cnpj"] == FUND_B)
        assert clean["count"] == 0

    def test_issuer_keyed_findings_are_excluded_from_the_fund_matrix(self, run_dir):
        data = load_run(run_dir)
        assert "cross_fund_issuer" in data["entity_level"]
        assert "cross_fund_issuer" not in [t["key"] for t in data["tests"]]

    def test_funds_are_ordered_worst_first(self, run_dir):
        funds = load_run(run_dir)["funds"]
        assert funds[0]["cnpj"] == FUND_A


class TestOutput:

    def test_page_is_self_contained(self, run_dir):
        page = render(load_run(run_dir))
        assert "<!doctype html>" in page
        # No external fetches: a strict CSP and an archived run must both work.
        for scheme in ("http://", "https://", "//cdn"):
            assert scheme not in page

    def test_fragment_omits_the_document_wrapper(self, run_dir):
        fragment = render(load_run(run_dir), fragment=True)
        assert "<!doctype html>" not in fragment
        assert "<body" not in fragment
        assert "<style>" in fragment

    def test_fund_name_is_searchable_in_the_payload(self, run_dir):
        page = render(load_run(run_dir))
        assert "ACME FIC FIM" in page

    def test_both_themes_define_every_colour_token(self, run_dir):
        """A token defined only under one theme renders unreadable in the other."""
        import re
        page = render(load_run(run_dir))
        style = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        blocks = re.findall(r"(:root[^{]*)\{([^}]*)\}", style)
        light = {m for b in blocks if b[0].strip() == ":root"
                 for m in re.findall(r"(--[\w-]+):", b[1])}
        dark = {m for b in blocks if 'data-theme="dark"' in b[0]
                for m in re.findall(r"(--[\w-]+):", b[1])}
        assert light, "no base :root token block found"
        assert light == dark, f"tokens missing from dark theme: {light ^ dark}"


class TestFormatCnpj:

    def test_punctuates_fourteen_digits(self):
        assert format_cnpj("12345678000190") == "12.345.678/0001-90"

    def test_leaves_anything_else_alone(self):
        assert format_cnpj("123") == "123"


class TestPeriodIsAlwaysStated:
    """A report that does not say what dates it covers cannot be rechecked.

    Recovering the window behind an earlier analysis in this repo meant sweeping
    two years of filings and matching aggregates to the cent, because nobody
    wrote the dates down. The page states them or says plainly that it cannot.
    """

    def test_recorded_period_is_shown(self, run_dir):
        import json as _json
        summary = _json.loads((run_dir / "summary.json").read_text())
        summary["data_period"] = {"start": "2026-06-01", "end": "2026-06-30",
                                  "reporting_days": 21}
        (run_dir / "summary.json").write_text(_json.dumps(summary))
        page = render(load_run(run_dir))
        assert "2026-06-01" in page and "2026-06-30" in page
        assert "21 reporting days" in page

    def test_missing_period_says_so_rather_than_showing_nothing(self, run_dir):
        page = render(load_run(run_dir))
        assert "Data period not recorded" in page

    def test_analysis_timestamp_is_shown_when_recorded(self, run_dir):
        import json as _json
        summary = _json.loads((run_dir / "summary.json").read_text())
        summary["generated_at"] = "2026-08-12T18:30:00"
        (run_dir / "summary.json").write_text(_json.dumps(summary))
        assert "2026-08-12 18:30:00" in render(load_run(run_dir))


class TestRedFlagsAreExplained:

    def test_every_mapped_signal_exists_in_the_registry(self):
        """Stops SIGNAL_FOR_FILE drifting away from the registry it points at."""
        from scripts.build_dashboard import SIGNAL_FOR_FILE
        from src.explain.signal_registry import SIGNAL_REGISTRY

        unknown = {v for v in SIGNAL_FOR_FILE.values() if v not in SIGNAL_REGISTRY}
        assert not unknown, f"mapped to signals the registry does not define: {unknown}"

    def test_a_fired_detector_carries_its_explanation(self, run_dir):
        data = load_run(run_dir)
        assert "runs" in data["explanations"]
        note = data["explanations"]["runs"]
        assert note["what"], "explanation text is empty"
        assert note["caveats"], "a red flag without caveats invites over-reading"

    def test_explanation_reaches_the_page(self, run_dir):
        page = render(load_run(run_dir))
        assert "What this means" in page
        assert "Could also be" in page


class TestMetricsSurviveWithoutBriefs:
    """A full-universe run is written with --no-explain, so there are no briefs."""

    def test_metric_and_severity_come_from_the_csv(self, run_dir, tmp_path):
        import shutil
        stripped = tmp_path / "nobriefs"
        shutil.copytree(run_dir, stripped)
        shutil.rmtree(stripped / "entities")
        (stripped / "entities").mkdir()

        # Give the CSV its own severity column, as the real detectors do.
        (stripped / "findings" / "runs.csv").write_text(
            f"CNPJ_FUNDO,RUN_LENGTH,severity\n{FUND_A},7,HIGH\n")

        fund = next(f for f in load_run(stripped)["funds"] if f["cnpj"] == FUND_A)
        assert fund["severity"] == "HIGH"
        assert fund["detail"]["runs"]["metric"] == "RUN_LENGTH: 7"
