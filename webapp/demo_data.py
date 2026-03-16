"""
Demo data generator for the REAG investigation webapp.

Produces synthetic Brazilian-style investment fund data that mirrors the
structure of CVM datasets so the existing src/ analyzers work without a live
API connection.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

RNG = np.random.default_rng(42)

# ── Fund universe ────────────────────────────────────────────────────────────

FUND_DEFINITIONS = [
    # (cnpj, name, category, risk_level, is_reag)
    ("12.345.678/0001-90", "Fundo D Mais FIC FIM", "MULTI_MARKET", "CRITICAL", True),
    ("23.456.789/0001-01", "Fundo Bravo FIC FIA", "EQUITY", "HIGH", True),
    ("34.567.890/0001-12", "Fundo Master CRI FIM", "FIXED_INCOME", "CRITICAL", True),
    ("45.678.901/0001-23", "Fundo Nexus Cambial", "FX", "HIGH", True),
    ("56.789.012/0001-34", "Fundo Alpha Multimercado", "MULTI_MARKET", "MEDIUM", True),
    ("67.890.123/0001-45", "Fundo Delta Renda Fixa", "FIXED_INCOME", "LOW", True),
    ("78.901.234/0001-56", "BTG Pactual RF LP FIC", "FIXED_INCOME", "LOW", False),
    ("89.012.345/0001-67", "XP Macro FIC FIM", "MULTI_MARKET", "LOW", False),
    ("90.123.456/0001-78", "Itaú Ações Ibovespa FIC", "EQUITY", "LOW", False),
    ("01.234.567/0001-89", "Safra Cambial FIC", "FX", "LOW", False),
    ("11.222.333/0001-00", "Fundo Omega FIC FIM", "MULTI_MARKET", "HIGH", True),
    ("22.333.444/0001-11", "Fundo Sigma RF FIC", "FIXED_INCOME", "MEDIUM", True),
]

CATEGORY_LABELS = {
    "MULTI_MARKET": "Multimercado",
    "EQUITY": "Renda Variável",
    "FIXED_INCOME": "Renda Fixa",
    "FX": "Cambial",
}

RISK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
RISK_COLOR = {
    "CRITICAL": "#dc3545",
    "HIGH": "#fd7e14",
    "MEDIUM": "#ffc107",
    "LOW": "#28a745",
}


def _date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1) if (start + timedelta(days=i)).weekday() < 5]


def build_informe_diario(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Return a synthetic *informe diário* DataFrame."""
    if start is None:
        start = date(2022, 1, 3)
    if end is None:
        end = date(2024, 12, 31)

    dates = _date_range(start, end)
    rows = []

    for cnpj, name, category, risk, is_reag in FUND_DEFINITIONS:
        base_pl = RNG.uniform(50_000_000, 2_000_000_000)
        trend = RNG.uniform(-0.0002, 0.0003)
        vol = 0.015 if risk in ("CRITICAL", "HIGH") else 0.005
        pl = base_pl

        for dt in dates:
            # Net-worth with drift + noise
            daily_ret = trend + RNG.normal(0, vol)
            if risk == "CRITICAL" and RNG.random() < 0.005:
                daily_ret -= RNG.uniform(0.05, 0.20)  # sudden drop
            pl = max(pl * (1 + daily_ret), 100_000)

            # Flows: suspicious large flows for CRITICAL/HIGH
            if risk == "CRITICAL" and RNG.random() < 0.03:
                flow = RNG.choice([-1, 1]) * RNG.uniform(0.05, 0.25) * pl
            elif risk == "HIGH" and RNG.random() < 0.02:
                flow = RNG.choice([-1, 1]) * RNG.uniform(0.02, 0.10) * pl
            else:
                flow = RNG.normal(0, 0.005) * pl

            quota_value = 1.0 + daily_ret
            rows.append(
                {
                    "DT_COMPTC": dt,
                    "CNPJ_FUNDO": cnpj,
                    "NM_FUNDO": name,
                    "CATEGORIA": category,
                    "RISCO": risk,
                    "IS_REAG": is_reag,
                    "VL_PATRIM_LIQ": round(pl, 2),
                    "FLUXO_LIQ_DIA": round(flow, 2),
                    "VL_QUOTA": round(quota_value, 6),
                    "NR_COTST": int(RNG.uniform(50, 5000)),
                }
            )

    df = pd.DataFrame(rows)
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])
    return df.sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).reset_index(drop=True)


def build_portfolio_holdings() -> pd.DataFrame:
    """Return synthetic portfolio holdings (CDA-style)."""
    asset_types = [
        ("CRI", "CRI Securitizadora Relacionada", "FICTITIOUS"),
        ("CRA", "CRA Agronegócio Relacionado", "FICTITIOUS"),
        ("DEBENTURE", "Debênture Empresa Controlada", "SUSPICIOUS"),
        ("ACAO", "PETR4", "NORMAL"),
        ("ACAO", "VALE3", "NORMAL"),
        ("LFT", "Tesouro Selic 2026", "NORMAL"),
        ("FII", "FII Logística XPLG11", "NORMAL"),
        ("FUNDO", "Fundo Relacionado Layered", "SUSPICIOUS"),
    ]

    rows = []
    for cnpj, name, category, risk, is_reag in FUND_DEFINITIONS:
        pl_sample = RNG.uniform(200_000_000, 1_500_000_000)
        for asset_type, asset_name, asset_status in asset_types:
            weight = RNG.uniform(0.02, 0.25) if risk in ("CRITICAL", "HIGH") else RNG.uniform(0.01, 0.15)
            # CRITICAL / HIGH funds hold more suspicious assets
            if asset_status == "FICTITIOUS" and risk not in ("CRITICAL", "HIGH"):
                weight *= 0.1
            rows.append(
                {
                    "CNPJ_FUNDO": cnpj,
                    "NM_FUNDO": name,
                    "TIPO_ATIVO": asset_type,
                    "NM_ATIVO": asset_name,
                    "STATUS_ATIVO": asset_status,
                    "VL_MERCADO": round(pl_sample * weight, 2),
                    "PCT_PL": round(weight * 100, 2),
                }
            )

    return pd.DataFrame(rows)


def compute_fund_risk_scores(informe_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-fund aggregate risk scores from the informe DataFrame."""
    import sys
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.analyzers.anomaly_detector import AnomalyDetector

    detector = AnomalyDetector()

    records = []
    for (cnpj, nm, cat, risk, is_reag), grp in informe_df.groupby(
        ["CNPJ_FUNDO", "NM_FUNDO", "CATEGORIA", "RISCO", "IS_REAG"]
    ):
        grp = grp.copy()

        # Flow anomalies
        anomalies = detector.detect_flow_anomalies(grp, threshold=2.5, flow_col="FLUXO_LIQ_DIA")
        n_anomalies = len(anomalies)
        max_z = float(anomalies["Z_SCORE_FLOW"].abs().max()) if n_anomalies else 0.0

        # PL drops
        drops = detector.detect_pl_drops(grp, threshold_pct=10.0)
        n_drops = len(drops)
        max_drop = float(drops["PL_VAR_PCT"].min()) if n_drops else 0.0

        # Latest PL
        latest_pl = float(grp.sort_values("DT_COMPTC").iloc[-1]["VL_PATRIM_LIQ"])

        # Composite score (0-100)
        score = min(100, (n_anomalies * 2) + (abs(max_z) * 5) + (n_drops * 3) + abs(max_drop))
        score = round(score, 1)

        records.append(
            {
                "CNPJ_FUNDO": cnpj,
                "NM_FUNDO": nm,
                "CATEGORIA": cat,
                "CATEGORIA_LABEL": CATEGORY_LABELS.get(cat, cat),
                "RISCO": risk,
                "IS_REAG": is_reag,
                "PL_ATUAL": latest_pl,
                "N_ANOMALIAS_FLUXO": n_anomalies,
                "MAX_ZSCORE": round(max_z, 2),
                "N_QUEDAS_PL": n_drops,
                "MAX_QUEDA_PCT": round(max_drop, 2),
                "SCORE_RISCO": score,
            }
        )

    df = pd.DataFrame(records).sort_values("SCORE_RISCO", ascending=False).reset_index(drop=True)
    return df


def compute_benford_data(informe_df: pd.DataFrame) -> pd.DataFrame:
    """Compute Benford's law deviations for every fund."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.analyzers.benford_law import BenfordLawAnalyzer

    analyzer = BenfordLawAnalyzer()

    records = []
    for (cnpj, nm), grp in informe_df.groupby(["CNPJ_FUNDO", "NM_FUNDO"]):
        values = grp["VL_PATRIM_LIQ"].dropna()
        if len(values) < 30:
            continue
        first_digits = analyzer.extract_first_digits(values)
        if len(first_digits) == 0:
            continue
        observed_counts = first_digits.value_counts().reindex(range(1, 10), fill_value=0)
        observed_freq = observed_counts / observed_counts.sum()
        expected_freq = pd.Series(analyzer.BENFORD_EXPECTED)

        mad = float((observed_freq - expected_freq).abs().mean())
        # chi-square
        expected_counts = expected_freq * len(first_digits)
        chi2_stat = float(((observed_counts - expected_counts) ** 2 / expected_counts.replace(0, 1)).sum())

        records.append(
            {
                "CNPJ_FUNDO": cnpj,
                "NM_FUNDO": nm,
                "N_OBSERVACOES": len(first_digits),
                "MAD": round(mad, 4),
                "CHI2": round(chi2_stat, 2),
                "BENFORD_RISK": "HIGH" if mad > 0.015 else ("MEDIUM" if mad > 0.008 else "LOW"),
                "OBSERVED_FREQ": observed_freq.to_dict(),
                "EXPECTED_FREQ": expected_freq.to_dict(),
            }
        )

    return pd.DataFrame(records).sort_values("MAD", ascending=False).reset_index(drop=True)


# ── Convenience loader (cached by caller) ────────────────────────────────────

def load_all() -> dict:
    """Return a dict with all demo datasets ready for the webapp."""
    informe = build_informe_diario()
    holdings = build_portfolio_holdings()
    risk_scores = compute_fund_risk_scores(informe)
    benford = compute_benford_data(informe)
    return {
        "informe": informe,
        "holdings": holdings,
        "risk_scores": risk_scores,
        "benford": benford,
    }
