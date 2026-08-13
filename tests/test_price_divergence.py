"""Tests for the offline cross-fund price divergence analyzer."""

import numpy as np
import pandas as pd
import pytest

from src.analyzers.price_divergence import (
    DIVERGENCE_ROBUST_Z,
    MIN_FUNDS_FOR_CONSENSUS,
    CrossFundPriceDivergenceAnalyzer,
)


def make_cda(prices_by_fund, asset="CRI_ABC_2024", comptc="2024-01-31", quantity=1000.0):
    """Build a CDA frame where each fund declares a given unit price for one asset."""
    return pd.DataFrame([
        {
            "CNPJ_FUNDO": fund,
            "CD_ATIVO": asset,
            "DT_COMPTC": pd.Timestamp(comptc),
            "QT_POS": quantity,
            "VL_MERCADO": price * quantity,
        }
        for fund, price in prices_by_fund.items()
    ])


@pytest.fixture
def analyzer():
    return CrossFundPriceDivergenceAnalyzer()


class TestDetection:

    def test_flags_the_fund_marking_above_its_peers(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 101.0, "F3": 99.0, "F4": 100.5, "F5": 140.0})

        result = analyzer.analyze(cda)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["CNPJ_FUNDO"] == "F5"
        assert row["direction"] == "OVERVALUATION"
        assert row["declared_unit_price"] == pytest.approx(140.0)
        assert row["consensus_unit_price"] == pytest.approx(100.5)
        assert row["divergence_pct"] == pytest.approx(39.3, abs=0.1)
        assert row["peer_fund_count"] == 5

    def test_flags_the_fund_marking_below_its_peers(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 101.0, "F3": 99.0, "F4": 100.5, "F5": 60.0})

        result = analyzer.analyze(cda)

        assert len(result) == 1
        assert result.iloc[0]["CNPJ_FUNDO"] == "F5"
        assert result.iloc[0]["direction"] == "UNDERVALUATION"
        assert result.iloc[0]["divergence_pct"] < 0

    def test_agreeing_funds_produce_nothing(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 101.0, "F3": 99.0, "F4": 100.5, "F5": 100.2})
        assert analyzer.analyze(cda).empty

    def test_identical_prices_produce_nothing(self, analyzer):
        """MAD is zero here; the fallback must not flag everyone."""
        cda = make_cda({f"F{i}": 100.0 for i in range(6)})
        assert analyzer.analyze(cda).empty

    def test_single_outlier_against_identical_peers_is_flagged(self, analyzer):
        """MAD zero, one dissenter: the percentage test still applies."""
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 100.0, "F5": 150.0})

        result = analyzer.analyze(cda)

        assert len(result) == 1
        assert result.iloc[0]["CNPJ_FUNDO"] == "F5"

    def test_median_consensus_resists_a_single_extreme_mark(self, analyzer):
        """One grossly mismarked fund must not drag the reference toward itself."""
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 100.0, "F5": 10_000.0})

        result = analyzer.analyze(cda)

        assert result.iloc[0]["consensus_unit_price"] == pytest.approx(100.0)
        assert result.iloc[0]["CNPJ_FUNDO"] == "F5"

    def test_wide_but_uniform_spread_is_not_flagged(self, analyzer):
        """When every fund disagrees by a lot, no single fund is the outlier."""
        cda = make_cda({"F1": 50.0, "F2": 75.0, "F3": 100.0, "F4": 125.0, "F5": 150.0})
        assert analyzer.analyze(cda).empty


class TestConsensusRequirements:

    @pytest.mark.parametrize("n_funds", [1, 2])
    def test_too_few_funds_yields_no_consensus(self, analyzer, n_funds):
        prices = {"F1": 100.0, "F2": 500.0}
        cda = make_cda(dict(list(prices.items())[:n_funds]))
        assert analyzer.analyze(cda).empty

    def test_minimum_is_three_funds(self, analyzer):
        assert MIN_FUNDS_FOR_CONSENSUS == 3
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 200.0})
        assert not analyzer.analyze(cda).empty

    def test_funds_are_compared_only_within_the_same_asset_and_date(self, analyzer):
        """A price gap across different assets or dates is not a divergence."""
        frames = [
            make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0}, asset="AAAA1"),
            make_cda({"F4": 900.0, "F5": 900.0, "F6": 900.0}, asset="BBBB2"),
            make_cda({"F7": 5.0, "F8": 5.0, "F9": 5.0}, comptc="2024-02-29"),
        ]
        assert analyzer.analyze(pd.concat(frames, ignore_index=True)).empty

    def test_multiple_positions_in_one_fund_count_once(self, analyzer):
        """Tranches sharing an asset code must not give one fund several votes."""
        cda = pd.concat([
            make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0}),
            make_cda({"F1": 101.0}),   # same fund, second position
            make_cda({"F1": 99.0}),    # same fund, third position
        ], ignore_index=True)

        result = analyzer.analyze(cda)

        assert result.empty  # F1's median is 100.0, matching its peers


class TestUnusableRows:

    def test_zero_quantity_rows_are_dropped(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 150.0})
        cda.loc[cda["CNPJ_FUNDO"] == "F4", "QT_POS"] = 0.0

        # F4 is dropped, leaving three agreeing funds.
        assert analyzer.analyze(cda).empty

    def test_zero_market_value_is_dropped_not_treated_as_a_zero_price(self, analyzer):
        """A zero mark would otherwise register as a 100% divergence."""
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 100.0})
        cda.loc[cda["CNPJ_FUNDO"] == "F4", "VL_MERCADO"] = 0.0

        assert analyzer.analyze(cda).empty

    def test_non_numeric_values_are_dropped(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0})
        cda["QT_POS"] = cda["QT_POS"].astype(object)
        cda.loc[0, "QT_POS"] = "not a number"

        assert analyzer.analyze(cda).empty

    def test_all_rows_unusable_returns_empty(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0})
        cda["QT_POS"] = 0.0

        assert analyzer.analyze(cda).empty

    def test_missing_required_column_raises(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0}).drop(columns=["QT_POS"])

        with pytest.raises(ValueError, match="QT_POS"):
            analyzer.analyze(cda)


class TestSeverity:

    @pytest.mark.parametrize("divergence,expected", [
        (15.0, "LOW"),
        (25.0, "MEDIUM"),
        (35.0, "HIGH"),
        (75.0, "CRITICAL"),
        (-75.0, "CRITICAL"),
    ])
    def test_grades_by_distance_from_consensus(self, analyzer, divergence, expected):
        assert analyzer._severity(divergence) == expected

    def test_severity_appears_in_output(self, analyzer):
        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 100.0, "F5": 300.0})
        assert analyzer.analyze(cda).iloc[0]["severity"] == "CRITICAL"


class TestOutputContract:

    def test_findings_are_sorted_by_absolute_divergence(self, analyzer):
        frames = [
            make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 130.0}, asset="AAAA1"),
            make_cda({"G1": 100.0, "G2": 100.0, "G3": 100.0, "G4": 400.0}, asset="BBBB2"),
        ]
        result = analyzer.analyze(pd.concat(frames, ignore_index=True))

        assert len(result) == 2
        assert result.iloc[0]["divergence_pct"] > result.iloc[1]["divergence_pct"]

    def test_output_columns_match_the_signal_registry(self, analyzer):
        from src.explain.signal_registry import SIGNAL_REGISTRY

        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 200.0})
        result = analyzer.analyze(cda)

        definition = SIGNAL_REGISTRY["cross_fund_price_divergence"]
        missing = set(definition.evidence_fields) - set(result.columns)
        assert not missing, f"registry references columns the analyzer never emits: {missing}"

    def test_registry_severity_rule_reads_the_emitted_severity(self, analyzer):
        from src.explain.signal_registry import SIGNAL_REGISTRY

        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 300.0})
        row = analyzer.analyze(cda).iloc[0].to_dict()

        rule = SIGNAL_REGISTRY["cross_fund_price_divergence"].severity_rule
        assert rule(row) == "CRITICAL"

    def test_no_network_access_is_required(self, analyzer, monkeypatch):
        """The whole point of this analyzer: it works entirely offline."""
        import requests

        def explode(*args, **kwargs):
            raise AssertionError("analyzer must not make network calls")

        monkeypatch.setattr(requests.Session, "request", explode)

        cda = make_cda({"F1": 100.0, "F2": 100.0, "F3": 100.0, "F4": 200.0})
        assert len(analyzer.analyze(cda)) == 1


class TestScale:

    def test_handles_a_realistic_universe(self, analyzer):
        """200 funds x 50 assets, with 10 planted mismarks."""
        rng = np.random.default_rng(42)
        rows = []
        for asset_idx in range(50):
            asset = f"CRI_{asset_idx:03d}"
            true_price = float(rng.uniform(50, 500))
            for fund_idx in range(200):
                # Peers agree to within a fraction of a percent.
                price = true_price * (1 + rng.normal(0, 0.001))
                rows.append({
                    "CNPJ_FUNDO": f"FUND{fund_idx:05d}",
                    "CD_ATIVO": asset,
                    "DT_COMPTC": pd.Timestamp("2024-01-31"),
                    "QT_POS": 1000.0,
                    "VL_MERCADO": price * 1000.0,
                })

        # Plant 10 mismarks at +60%.
        cda = pd.DataFrame(rows)
        planted = cda.sample(n=10, random_state=1).index
        cda.loc[planted, "VL_MERCADO"] *= 1.6

        result = analyzer.analyze(cda)

        assert len(result) == 10
        assert set(result["direction"]) == {"OVERVALUATION"}


class TestConsensusPrefilterScales:
    """Groups too small for a consensus are dropped before the Python loop.

    Without the prefilter the loop ran a nested pandas groupby on every
    asset-date pair just to find fewer than three holders. Most assets are held
    by one or two funds, so on a real CVM month that was 144,847 groups where
    only a few thousand could produce anything, and a full run never finished.
    The filter must not change a single result.
    """

    def _analyzer(self):
        from config.settings import Config
        return CrossFundPriceDivergenceAnalyzer(config=Config())

    def _cda(self, rows):
        return pd.DataFrame(rows)

    def test_holder_count_is_evaluated_per_date_not_per_asset(self):
        """The subtle case the prefilter must get right.

        One asset can clear the threshold on one date and miss it on another.
        Counting holders per asset instead of per asset-date would either drop a
        comparable date or readmit an incomparable one.
        """
        rows = []
        # 2024-01-01: three funds hold it, one of them mismarked -> comparable.
        for cnpj, price in (("111", 100.0), ("222", 100.0), ("333", 500.0)):
            rows.append({"CNPJ_FUNDO": cnpj, "CD_ATIVO": "CRI_1",
                         "DT_COMPTC": pd.Timestamp("2024-01-01"),
                         "QT_POS": 10.0, "VL_MERCADO": price * 10,
                         "CD_ATIVO_FONTE": "CD_ATIVO"})
        # 2024-02-01: only two funds -> no consensus, must yield nothing.
        for cnpj, price in (("111", 100.0), ("222", 900.0)):
            rows.append({"CNPJ_FUNDO": cnpj, "CD_ATIVO": "CRI_1",
                         "DT_COMPTC": pd.Timestamp("2024-02-01"),
                         "QT_POS": 10.0, "VL_MERCADO": price * 10,
                         "CD_ATIVO_FONTE": "CD_ATIVO"})

        result = self._analyzer().analyze(self._cda(rows))
        assert not result.empty, "the three-holder date should still be compared"
        dates = set(result["DT_COMPTC"])
        assert dates == {pd.Timestamp("2024-01-01")}, (
            "only the date with enough holders may produce findings"
        )

    def test_a_universe_with_no_shared_assets_returns_empty(self):
        rows = [{"CNPJ_FUNDO": str(i), "CD_ATIVO": f"UNIQUE_{i}",
                 "DT_COMPTC": pd.Timestamp("2024-01-01"), "QT_POS": 10.0,
                 "VL_MERCADO": 1000.0, "CD_ATIVO_FONTE": "CD_ATIVO"}
                for i in range(50)]
        result = self._analyzer().analyze(self._cda(rows))
        assert result.empty
