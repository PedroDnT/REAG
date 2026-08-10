"""The eval fixtures must model the schema CVM actually publishes.

Every eval metric is measured against `evals/fixtures.py`, whose frames are
invented rather than downloaded. That is fine right up until a fixture models a
column the source does not publish: the detector reading it scores well in the
eval and cannot run at all on real data. This has already happened once here --
the fixtures carried the manager identifier under a name the legacy `cad_fi.csv`
never had, and the evals gave a clean bill of health to a detector the pipeline
could only ever skip.

So the check runs in both directions:

- Every column a fixture emits must be one the real pipeline can produce, and
  "can produce" is decided by running the actual readers over the real CVM
  headers rather than by a list maintained alongside them.
- Every column a scored detector requires must exist in the fixtures, so a
  detector cannot be silently unscored.

`evals/cvm_headers.json` holds the real headers, so none of this needs network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from evals import fixtures
from src.processors.data_processor import DataProcessor

HEADERS = json.loads((Path("evals") / "cvm_headers.json").read_text())

# Columns the pipeline derives rather than reads, so they appear in no CVM
# header but are legitimately present downstream.
DERIVED_COLUMNS = frozenset({"FLUXO_LIQ_DIA"})


def _write_header_csv(directory: Path, name: str, header: list[str]) -> Path:
    """One CSV carrying a real CVM header and a single blank row.

    Blank values are enough: the assertion is about which columns survive the
    reader, and every date and numeric coercion in the pipeline uses
    ``errors='coerce'``.
    """
    path = directory / name
    path.write_text(
        ";".join(header) + "\n" + ";".join([""] * len(header)) + "\n",
        encoding="latin1",
    )
    return path


@pytest.fixture(scope="module")
def real_informe_columns(tmp_path_factory) -> frozenset[str]:
    directory = tmp_path_factory.mktemp("informe")
    path = _write_header_csv(directory, "inf_diario_fi.csv", HEADERS["inf_diario_fi"])
    return frozenset(DataProcessor().read_informe_diario(path).columns) | DERIVED_COLUMNS


@pytest.fixture(scope="module")
def real_cda_columns(tmp_path_factory) -> frozenset[str]:
    """Union across every block, which is how run_investigation reads the CDA."""
    directory = tmp_path_factory.mktemp("cda")
    processor = DataProcessor()
    columns: set[str] = set()
    for name, header in HEADERS["cda"].items():
        path = _write_header_csv(directory, f"{name}.csv", header)
        columns |= set(processor.read_cda(path).columns)
    return frozenset(columns)


@pytest.fixture(scope="module")
def real_cadastro_columns(tmp_path_factory) -> frozenset[str]:
    directory = tmp_path_factory.mktemp("registro")
    _write_header_csv(directory, "registro_classe.csv", HEADERS["registro_classe"])
    _write_header_csv(directory, "registro_fundo.csv", HEADERS["registro_fundo"])
    return frozenset(DataProcessor().read_registro_fundo_classe(directory).columns)


@pytest.fixture(scope="module")
def universe():
    # Full default length: the injectors plant their anomalies at fixed offsets
    # up to day 100, so a short universe would fail on indexing, not on schema.
    return fixtures.make_clean_universe(n_funds=6, n_days=fixtures.DEFAULT_DAYS, seed=7)


class TestFixturesStayWithinTheRealSchema:
    """A fixture column with no counterpart in real data is a trap."""

    def test_informe_fixture_invents_no_columns(self, universe, real_informe_columns):
        invented = set(universe.informe.columns) - real_informe_columns
        assert not invented, (
            f"informe fixture emits columns CVM does not publish: {sorted(invented)}"
        )

    def test_cda_fixture_invents_no_columns(self, universe, real_cda_columns):
        invented = set(universe.cda.columns) - real_cda_columns
        assert not invented, (
            f"CDA fixture emits columns CVM does not publish: {sorted(invented)}"
        )

    def test_cadastro_fixture_invents_no_columns(self, universe, real_cadastro_columns):
        invented = set(universe.cadastro.columns) - real_cadastro_columns
        assert not invented, (
            f"cadastro fixture emits columns the registry does not publish: "
            f"{sorted(invented)}"
        )

    def test_injectors_invent_no_columns(self, universe, real_informe_columns, real_cda_columns):
        """An injector must plant fraud in the real schema, not extend it."""
        for signal, inject in fixtures.INJECTORS.items():
            injected = inject(universe)
            assert not set(injected.informe.columns) - real_informe_columns, signal
            assert not set(injected.cda.columns) - real_cda_columns, signal


class TestEveryScoredDetectorHasItsInputs:
    """A detector missing an input column scores zero for the wrong reason."""

    #: What each scored detector reads, and from which fixture frame.
    REQUIRED = {
        "redemption_run": ("informe", ["CNPJ_FUNDO", "FLUXO_LIQ_DIA", "VL_PATRIM_LIQ"]),
        "pl_drop": ("informe", ["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"]),
        "valuation_smoothing": ("informe", ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]),
        "window_dressing": ("informe", ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]),
        "quotaholder_exodus": ("informe", ["CNPJ_FUNDO", "DT_COMPTC", "NR_COTST"]),
        "benford_violation": ("informe", ["CNPJ_FUNDO", "CAPTC_DIA"]),
        "cross_fund_price_divergence": (
            "cda",
            ["CNPJ_FUNDO", "CD_ATIVO", "DT_COMPTC", "VL_MERCADO", "QT_POS", "CD_ATIVO_FONTE"],
        ),
    }

    def test_every_detector_in_the_eval_sweep_is_covered_here(self):
        from evals.run_eval import DETECTORS

        assert set(self.REQUIRED) == set(DETECTORS)

    @pytest.mark.parametrize("signal", sorted(REQUIRED))
    def test_required_columns_are_present(self, universe, signal):
        frame_name, required = self.REQUIRED[signal]
        frame = getattr(universe, frame_name)
        missing = [column for column in required if column not in frame.columns]
        assert not missing, f"{signal} reads columns the fixtures do not build: {missing}"


class TestCdaFixtureMatchesRealBlockStructure:
    """The CDA fixture must exercise the same code path production does."""

    def test_asset_identity_provenance_is_populated(self, universe):
        """price_divergence filters on CD_ATIVO_FONTE before comparing prices.

        Without the column the filter is skipped entirely, so the eval would
        score a code path that never runs on real data -- where most positions
        are identified by issuer, not instrument.
        """
        assert "CD_ATIVO_FONTE" in universe.cda.columns
        assert set(universe.cda["CD_ATIVO_FONTE"].unique()) <= (
            DataProcessor.INSTRUMENT_LEVEL_ASSET_SOURCES | {"EMISSOR"}
        )

    def test_issuer_identified_positions_are_present(self, universe):
        """Real CDA blocks 6 and 8 carry no asset code at all."""
        assert (universe.cda["CD_ATIVO_FONTE"] == "EMISSOR").any()

    def test_normalizing_the_fixture_is_a_no_op(self, universe):
        """The fixture already looks like the processor's output."""
        normalized = DataProcessor._normalize_cda_positions(universe.cda)
        pd.testing.assert_frame_equal(normalized, universe.cda)
