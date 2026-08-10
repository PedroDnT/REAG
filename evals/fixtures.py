"""Synthetic CVM-shaped fund universes with labeled injected fraud.

Every generator is seeded, so a given seed always produces the same universe and
the same labels. That determinism is what lets `evals/baseline.json` be a
meaningful regression gate rather than a flaky one.

The clean universe matters as much as the injected ones. A detector's
false-positive rate against data containing no fraud is the number that decides
whether its output is usable: an analyst who learns to ignore a detector because
it fires constantly gets no value from it firing correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.processors.data_processor import DataProcessor

# Universe defaults, deliberately small enough that the full eval suite runs in
# seconds while still giving each detector enough funds to form a peer group.
DEFAULT_FUNDS = 40
DEFAULT_DAYS = 180
BASE_DATE = "2024-01-01"


@dataclass
class LabeledUniverse:
    """A synthetic universe plus the ground truth of what was injected.

    Attributes:
        informe: Informe diário frame (daily NAV, flows, quotaholders)
        cda: Portfolio composition frame
        cadastro: Fund registry frame
        labels: (CNPJ_FUNDO, signal_id) pairs naming every fund that carries an
            injected anomaly. Fund-level rather than fund-and-date, because
            detectors legitimately differ on which day within an episode they
            flag, and scoring that difference would measure alignment of
            conventions rather than detection.
    """

    informe: pd.DataFrame
    cda: pd.DataFrame
    cadastro: pd.DataFrame
    labels: set[tuple[str, str]] = field(default_factory=set)

    def funds_labeled(self, signal_id: str) -> set[str]:
        """CNPJs carrying an injected anomaly of the given kind."""
        return {cnpj for cnpj, signal in self.labels if signal == signal_id}


def fund_cnpj(index: int) -> str:
    """Deterministic, structurally valid CNPJ for fund *index*."""
    return f"{index + 10000000:08d}{index % 10000:04d}{(index % 89) + 10:02d}"


def make_clean_universe(
    n_funds: int = DEFAULT_FUNDS,
    n_days: int = DEFAULT_DAYS,
    seed: int = 42,
) -> LabeledUniverse:
    """Build a universe with no injected fraud.

    Fund NAVs follow a geometric random walk with per-fund drift and volatility;
    flows are lognormal, so their leading digits approximate Benford naturally.
    Nothing here should trip any detector.

    Args:
        n_funds: Number of funds
        n_days: Number of business days
        seed: RNG seed

    Returns:
        LabeledUniverse with an empty label set
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(BASE_DATE, periods=n_days)

    informe_rows = []
    for i in range(n_funds):
        cnpj = fund_cnpj(i)
        drift = rng.normal(0.0003, 0.0002)
        vol = rng.uniform(0.004, 0.015)

        returns = rng.normal(drift, vol, n_days)
        quota = 1.0 * np.cumprod(1 + returns)

        base_pl = rng.lognormal(17, 1.0)

        # Flows carry a persistent per-fund direction rather than being an
        # unbiased coin flip. Real funds sit in net inflow or net outflow for
        # stretches at a time; modelling flow sign as 50/50 makes long negative
        # streaks a certainty and misrepresents how noisy the run detector is.
        #
        # The drift is applied to the lognormal location parameter rather than
        # added on top, so both series stay lognormal and their leading digits
        # keep following Benford -- otherwise the clean universe would fail the
        # Benford detector by construction.
        # Sized relative to the fund's own net assets: roughly 0.15% a day,
        # which is the order of magnitude ordinary subscription and redemption
        # activity actually runs at. Scaling a lognormal by a constant leaves it
        # lognormal, so Benford conformity survives.
        flow_drift = rng.normal(0, 0.35)
        flow_scale = base_pl * 0.0015
        subscriptions = flow_scale * rng.lognormal(flow_drift, 1.2, n_days)
        redemptions = flow_scale * rng.lognormal(-flow_drift, 1.2, n_days)

        pl = base_pl * quota / quota[0]

        holders = np.maximum(
            10, (rng.lognormal(5, 0.8) + rng.normal(0, 2, n_days)).astype(int)
        )

        for d in range(n_days):
            informe_rows.append({
                "CNPJ_FUNDO": cnpj,
                "DT_COMPTC": dates[d],
                "VL_QUOTA": quota[d],
                "VL_PATRIM_LIQ": pl[d],
                "CAPTC_DIA": subscriptions[d],
                "RESG_DIA": redemptions[d],
                "NR_COTST": holders[d],
            })

    informe = pd.DataFrame(informe_rows)
    informe["FLUXO_LIQ_DIA"] = informe["CAPTC_DIA"] - informe["RESG_DIA"]

    return LabeledUniverse(
        informe=informe,
        cda=_make_clean_cda(n_funds, dates, rng),
        cadastro=_make_cadastro(n_funds),
        labels=set(),
    )


#: Assets carrying their own code, as CVM's coded CDA blocks publish them.
CODED_ASSETS = [f"CRI_{i:03d}" for i in range(12)] + ["PETR4", "VALE3", "ITUB4"]

#: Issuers whose paper reaches the CDA with no asset code at all, as blocks 6
#: and 8 do. Their unit prices legitimately differ between funds: one issuer
#: floats dozens of instruments with different maturities and rates, so two
#: funds holding "paper from bank X" are not holding the same thing.
UNCODED_ISSUERS = [f"BANCO SINTETICO {i}" for i in range(4)]


def _make_clean_cda(n_funds: int, dates: pd.DatetimeIndex, rng) -> pd.DataFrame:
    """Month-end portfolio snapshots where every fund marks assets consistently.

    Built in the raw shape CVM publishes -- ``QT_POS_FINAL``,
    ``VL_MERC_POS_FINAL``, and an asset code that is absent on some rows -- and
    then run through the pipeline's own normalizer. The fixture is therefore
    whatever the processor produces from real-shaped input, rather than a
    hand-written guess at it, and it carries the ``CD_ATIVO_FONTE`` provenance
    the price detector filters on.
    """
    month_ends = sorted({d for d in dates if d.is_month_end} or {dates[-1]})

    rows = []
    for comptc in month_ends:
        # One true price per coded asset per date; funds agree to within a
        # fraction of 1%.
        true_price = {a: rng.uniform(50, 500) for a in CODED_ASSETS}
        for i in range(n_funds):
            cnpj = fund_cnpj(i)

            for asset in rng.choice(CODED_ASSETS, size=5, replace=False):
                price = true_price[asset] * (1 + rng.normal(0, 0.001))
                _append_position(rows, cnpj, comptc, price, rng,
                                 asset=asset, issuer=f"EMISSOR {asset}")

            # Uncoded paper, priced independently per fund. Comparing these
            # across funds is the false positive the provenance filter exists to
            # prevent, so the clean universe has to contain the temptation.
            for issuer in rng.choice(UNCODED_ISSUERS, size=2, replace=False):
                _append_position(rows, cnpj, comptc, rng.uniform(50, 5_000), rng,
                                 asset=None, issuer=issuer)

    return DataProcessor._normalize_cda_positions(pd.DataFrame(rows))


def _append_position(rows, cnpj, comptc, price, rng, *, asset, issuer) -> None:
    quantity = float(rng.integers(1_000, 50_000))
    rows.append({
        "CNPJ_FUNDO": cnpj,
        "CD_ATIVO": asset if asset is not None else pd.NA,
        "DT_COMPTC": comptc,
        "QT_POS_FINAL": quantity,
        "VL_MERC_POS_FINAL": price * quantity,
        "EMISSOR": issuer,
    })


def _make_cadastro(n_funds: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "CNPJ_FUNDO": fund_cnpj(i),
            "CNPJ_ADMIN": f"9999999900{i % 4:02d}1",
            "CNPJ_GESTOR": f"8888888800{i % 3:02d}2",
            "DENOM_SOCIAL": f"FUNDO SINTETICO {i:03d}",
            "ADMIN": f"ADMIN {i % 4}",
            "GESTOR": f"GESTOR {i % 3}",
            "CLASSE": ["Fundo Multimercado", "Fundo de Renda Fixa", "Fundo de Ações"][i % 3],
            "SIT": "EM FUNCIONAMENTO NORMAL",
            "DT_CONST": pd.Timestamp("2020-01-15"),
        }
        for i in range(n_funds)
    ])


# ---------------------------------------------------------------------------
# Injectors
#
# Each mutates a copy of the universe, records which funds it touched, and
# returns the result. They compose: applying several to one universe produces a
# universe carrying several labels.
# ---------------------------------------------------------------------------


def _copy(universe: LabeledUniverse) -> LabeledUniverse:
    return LabeledUniverse(
        informe=universe.informe.copy(),
        cda=universe.cda.copy(),
        cadastro=universe.cadastro.copy(),
        labels=set(universe.labels),
    )


def _target_funds(universe: LabeledUniverse, n: int, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    cnpjs = sorted(universe.informe["CNPJ_FUNDO"].unique())
    return list(rng.choice(cnpjs, size=min(n, len(cnpjs)), replace=False))


def inject_redemption_run(
    universe: LabeledUniverse,
    n_funds: int = 4,
    run_days: int = 12,
    daily_pct_of_assets: float = 2.0,
    seed: int = 1,
) -> LabeledUniverse:
    """Force a sustained stretch of material net redemptions.

    Outflows are sized as a share of the fund's own net assets rather than a
    flat amount, because net assets span orders of magnitude across the
    universe: a flat R$500k is a catastrophe for one fund and a rounding error
    for another.
    """
    out = _copy(universe)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        idx = out.informe.index[mask][60:60 + run_days]
        assets = out.informe.loc[idx, "VL_PATRIM_LIQ"].iloc[0]

        out.informe.loc[idx, "CAPTC_DIA"] = 0.0
        out.informe.loc[idx, "RESG_DIA"] = assets * daily_pct_of_assets / 100
        out.labels.add((cnpj, "redemption_run"))

    out.informe["FLUXO_LIQ_DIA"] = out.informe["CAPTC_DIA"] - out.informe["RESG_DIA"]
    return out


def inject_pl_drop(
    universe: LabeledUniverse, n_funds: int = 4, drop_pct: float = 45.0, seed: int = 2
) -> LabeledUniverse:
    """Collapse net assets in a single day."""
    out = _copy(universe)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        positions = out.informe.index[mask]
        # Everything from the drop day onward stays down; a one-day dip followed
        # by a full recovery is a data error, not a collapse.
        out.informe.loc[positions[90:], "VL_PATRIM_LIQ"] *= (1 - drop_pct / 100)
        out.labels.add((cnpj, "pl_drop"))
    return out


def inject_valuation_smoothing(
    universe: LabeledUniverse, n_funds: int = 4, seed: int = 3
) -> LabeledUniverse:
    """Replace the NAV path with an implausibly smooth one.

    A near-constant daily return produces the serial correlation and suppressed
    volatility that characterize a fund marking its own book.
    """
    out = _copy(universe)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        idx = out.informe.index[mask]
        n = len(idx)
        # 0.04% a day, every day, with negligible noise.
        smooth = np.cumprod(1 + np.full(n, 0.0004) + np.random.default_rng(seed).normal(0, 1e-6, n))
        out.informe.loc[idx, "VL_QUOTA"] = smooth
        out.labels.add((cnpj, "valuation_smoothing"))
    return out


def inject_window_dressing(
    universe: LabeledUniverse, n_funds: int = 4, spike: float = 1.06, seed: int = 4
) -> LabeledUniverse:
    """Spike the NAV on reporting dates and release it immediately after.

    The release matters. Window dressing is a temporary mark applied for a
    reporting date and reversed once it has passed; a spike left in place is a
    permanent level shift, which is a different phenomenon and reads differently
    to a detector comparing month-end returns against the rest of the month.
    """
    out = _copy(universe)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        fund = out.informe.loc[mask].sort_values("DT_COMPTC")

        # Exactly one reporting date per month: the last business day the fund
        # actually reported on. Spiking every day the detector considers "month
        # end" would leave the second such day showing no return at all, since
        # both would be scaled equally -- halving the very signal being planted.
        reporting_dates = fund.groupby(fund["DT_COMPTC"].dt.to_period("M")).tail(1).index

        out.informe.loc[reporting_dates, "VL_QUOTA"] *= spike
        out.labels.add((cnpj, "window_dressing"))
    return out


def inject_price_divergence(
    universe: LabeledUniverse, n_funds: int = 4, markup: float = 1.6, seed: int = 5
) -> LabeledUniverse:
    """Mark one asset well above what every other holder declares."""
    out = _copy(universe)
    # Only a coded instrument can be mismarked detectably: uncoded paper has no
    # cross-fund consensus to diverge from, and the detector drops it. Injecting
    # there would plant a label no correct detector could ever recover.
    codeable = out.cda["CD_ATIVO_FONTE"].isin(
        DataProcessor.INSTRUMENT_LEVEL_ASSET_SOURCES
    )
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = (out.cda["CNPJ_FUNDO"] == cnpj) & codeable
        if not mask.any():
            continue
        # Mismark this fund's largest position.
        target = out.cda.loc[mask, "VL_MERCADO"].idxmax()
        out.cda.loc[target, "VL_MERCADO"] *= markup
        out.cda.loc[target, "VL_MERC_POS_FINAL"] = out.cda.loc[target, "VL_MERCADO"]
        out.labels.add((cnpj, "cross_fund_price_divergence"))
    return out


def inject_benford_violation(
    universe: LabeledUniverse, n_funds: int = 4, seed: int = 6
) -> LabeledUniverse:
    """Replace flows with fabricated-looking values.

    Uniform leading digits are the signature Benford's law is meant to expose:
    a human inventing numbers spreads first digits evenly instead of following
    the logarithmic distribution real financial data obeys.
    """
    out = _copy(universe)
    rng = np.random.default_rng(seed)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        idx = out.informe.index[mask]
        leading = rng.integers(1, 10, len(idx))
        remainder = rng.uniform(0, 1, len(idx))
        out.informe.loc[idx, "CAPTC_DIA"] = (leading + remainder) * 10_000
        out.labels.add((cnpj, "benford_violation"))

    out.informe["FLUXO_LIQ_DIA"] = out.informe["CAPTC_DIA"] - out.informe["RESG_DIA"]
    return out


def inject_quotaholder_exodus(
    universe: LabeledUniverse, n_funds: int = 4, seed: int = 7
) -> LabeledUniverse:
    """Drop the quotaholder count sharply."""
    out = _copy(universe)
    for cnpj in _target_funds(universe, n_funds, seed):
        mask = out.informe["CNPJ_FUNDO"] == cnpj
        idx = out.informe.index[mask]
        out.informe.loc[idx[100:], "NR_COTST"] = (
            out.informe.loc[idx[100:], "NR_COTST"] * 0.2
        ).astype(int)
        out.labels.add((cnpj, "quotaholder_exodus"))
    return out


#: Every injector, keyed by the signal it plants. Used to drive the eval sweep.
INJECTORS = {
    "redemption_run": inject_redemption_run,
    "pl_drop": inject_pl_drop,
    "valuation_smoothing": inject_valuation_smoothing,
    "window_dressing": inject_window_dressing,
    "cross_fund_price_divergence": inject_price_divergence,
    "benford_violation": inject_benford_violation,
    "quotaholder_exodus": inject_quotaholder_exodus,
}
