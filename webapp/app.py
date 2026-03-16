"""
REAG Investigation Web App
==========================
Interactive Streamlit application for exploring investment-fund investigation
findings and identifying other funds worth investigating.

Run with:
    streamlit run webapp/app.py
"""

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Allow imports from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from webapp.demo_data import (
    CATEGORY_LABELS,
    RISK_COLOR,
    load_all,
)

# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="REAG – Investigação de Fundos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal custom CSS ────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }
    .risk-badge-CRITICAL { color: #dc3545; font-weight: 700; }
    .risk-badge-HIGH     { color: #fd7e14; font-weight: 700; }
    .risk-badge-MEDIUM   { color: #ffc107; font-weight: 700; }
    .risk-badge-LOW      { color: #28a745; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Data loading (cached) ─────────────────────────────────────────────────────

@st.cache_data(show_spinner="Carregando dados de investigação…")
def get_data() -> dict:
    return load_all()


DATA = get_data()
INFORME: pd.DataFrame = DATA["informe"]
HOLDINGS: pd.DataFrame = DATA["holdings"]
RISK_SCORES: pd.DataFrame = DATA["risk_scores"]
BENFORD: pd.DataFrame = DATA["benford"]

FUND_NAMES = dict(zip(RISK_SCORES["CNPJ_FUNDO"], RISK_SCORES["NM_FUNDO"]))


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🇧🇷 REAG Investigation")
    st.caption("Análise forense de fundos de investimento")
    st.divider()

    PAGE = st.radio(
        "Navegação",
        options=[
            "📊 Dashboard",
            "🏦 Explorar Fundos",
            "📈 Anomalias de Fluxo",
            "🔢 Lei de Benford",
            "🕵️ Padrões de Fraude",
            "📋 Comparação com Peers",
        ],
    )

    st.divider()
    st.caption(
        "Dados: CVM Dados Abertos (simulado)  \n"
        "Período: Jan 2022 – Dez 2024"
    )
    st.caption("⚠️ App demonstrativo com dados sintéticos")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.title("📊 Dashboard de Investigação – REAG / Banco Master")
    st.markdown(
        """
        Esta ferramenta apresenta achados da investigação sobre fundos administrados pela **REAG**,
        gestora ligada ao **Banco Master**, com fraude estimada em **R$ 11,5 bilhões** (2020–2025).
        Use o menu lateral para explorar cada dimensão da análise.
        """
    )

    # ── KPI row ──────────────────────────────────────────────────────────────
    reag_funds = RISK_SCORES[RISK_SCORES["IS_REAG"]]
    critical = reag_funds[reag_funds["RISCO"] == "CRITICAL"]
    high = reag_funds[reag_funds["RISCO"] == "HIGH"]
    total_pl = reag_funds["PL_ATUAL"].sum()
    total_anomalies = reag_funds["N_ANOMALIAS_FLUXO"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Fundos REAG analisados", len(reag_funds))
    c2.metric("🔴 Risco CRÍTICO", len(critical))
    c3.metric("🟠 Risco ALTO", len(high))
    c4.metric("Anomalias de fluxo", int(total_anomalies))
    c5.metric("PL total exposto", f"R$ {total_pl/1e9:.1f} bi")

    st.divider()

    # ── Risk score bubble chart ───────────────────────────────────────────────
    st.subheader("Mapa de Risco dos Fundos")
    fig_bubble = px.scatter(
        RISK_SCORES,
        x="N_ANOMALIAS_FLUXO",
        y="SCORE_RISCO",
        size="PL_ATUAL",
        color="RISCO",
        color_discrete_map=RISK_COLOR,
        hover_name="NM_FUNDO",
        hover_data={"CNPJ_FUNDO": True, "MAX_ZSCORE": True, "N_QUEDAS_PL": True},
        symbol="IS_REAG",
        symbol_map={True: "circle", False: "diamond"},
        labels={
            "N_ANOMALIAS_FLUXO": "Nº de Anomalias de Fluxo",
            "SCORE_RISCO": "Score de Risco (0-100)",
            "PL_ATUAL": "PL Atual (R$)",
            "RISCO": "Nível de Risco",
            "IS_REAG": "Fundo REAG",
        },
        title="Score de Risco × Anomalias  (tamanho = PL atual; ● REAG  ◆ peer)",
    )
    fig_bubble.update_layout(height=480)
    st.plotly_chart(fig_bubble, use_container_width=True)

    # ── Risk distribution + Category breakdown ────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Distribuição de Risco")
        risk_counts = RISK_SCORES.groupby(["RISCO", "IS_REAG"]).size().reset_index(name="count")
        risk_counts["Grupo"] = risk_counts["IS_REAG"].map({True: "REAG", False: "Peer"})
        fig_bar = px.bar(
            risk_counts,
            x="RISCO",
            y="count",
            color="Grupo",
            barmode="group",
            color_discrete_map={"REAG": "#e63946", "Peer": "#457b9d"},
            category_orders={"RISCO": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
            labels={"count": "Nº de fundos", "RISCO": "Nível de risco"},
        )
        fig_bar.update_layout(height=320, showlegend=True)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.subheader("PL por Categoria (fundos REAG)")
        cat_pl = (
            reag_funds.groupby("CATEGORIA_LABEL")["PL_ATUAL"].sum().reset_index()
        )
        fig_pie = px.pie(
            cat_pl,
            names="CATEGORIA_LABEL",
            values="PL_ATUAL",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_layout(height=320)
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Key findings ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🚨 Principais Achados da Investigação")
    findings = [
        ("🔴", "Fluxo Circular", "Transferências entre entidades relacionadas (padrão Banco Master)"),
        ("🔴", "Ativos Fantasma", "CRIs/CRAs declarados sem lastro verificável em B3/ANBIMA"),
        ("🟠", "Benford Desviante", "Distribuição de algarismos incompatível com dados naturais"),
        ("🟠", "Concentração Excessiva", "Fundos com >40% em um único emissor relacionado"),
        ("🟡", "Quedas Bruscas de PL", "Resgates maciços não justificados por mercado"),
        ("🟡", "Layering de Fundos", "Cascata de fundos para obstruir rastreamento"),
    ]
    cols = st.columns(3)
    for i, (icon, title, desc) in enumerate(findings):
        with cols[i % 3]:
            st.info(f"**{icon} {title}**  \n{desc}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Fund Explorer
# ═══════════════════════════════════════════════════════════════════════════════

def page_fund_explorer():
    st.title("🏦 Explorador de Fundos")
    st.markdown("Filtre, ordene e investigue fundos individualmente.")

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1:
        risk_filter = st.multiselect(
            "Nível de risco",
            options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            default=["CRITICAL", "HIGH"],
        )
    with f2:
        cat_filter = st.multiselect(
            "Categoria",
            options=list(CATEGORY_LABELS.values()),
            default=list(CATEGORY_LABELS.values()),
        )
    with f3:
        reag_only = st.checkbox("Somente fundos REAG", value=False)

    df = RISK_SCORES.copy()
    if risk_filter:
        df = df[df["RISCO"].isin(risk_filter)]
    if cat_filter:
        df = df[df["CATEGORIA_LABEL"].isin(cat_filter)]
    if reag_only:
        df = df[df["IS_REAG"]]

    # ── Sortable table ────────────────────────────────────────────────────────
    display_cols = ["NM_FUNDO", "CATEGORIA_LABEL", "RISCO", "IS_REAG",
                    "PL_ATUAL", "SCORE_RISCO", "N_ANOMALIAS_FLUXO", "N_QUEDAS_PL", "MAX_ZSCORE"]
    display_df = df[display_cols].rename(
        columns={
            "NM_FUNDO": "Fundo",
            "CATEGORIA_LABEL": "Categoria",
            "RISCO": "Risco",
            "IS_REAG": "REAG?",
            "PL_ATUAL": "PL Atual (R$)",
            "SCORE_RISCO": "Score",
            "N_ANOMALIAS_FLUXO": "Anomalias",
            "N_QUEDAS_PL": "Quedas PL",
            "MAX_ZSCORE": "Max Z-Score",
        }
    ).sort_values("Score", ascending=False)

    display_df["PL Atual (R$)"] = display_df["PL Atual (R$)"].apply(
        lambda x: f"R$ {x/1e6:.1f}M"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score de Risco", min_value=0, max_value=100, format="%d"
            ),
            "Risco": st.column_config.TextColumn("Risco"),
        },
    )
    st.caption(f"{len(display_df)} fundos exibidos.")

    # ── Fund detail ───────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Detalhes do Fundo")
    fund_options = df["NM_FUNDO"].tolist()
    if not fund_options:
        st.warning("Nenhum fundo corresponde aos filtros aplicados.")
        return

    selected_name = st.selectbox("Selecione um fundo para análise detalhada", fund_options)
    selected = df[df["NM_FUNDO"] == selected_name].iloc[0]
    cnpj = selected["CNPJ_FUNDO"]

    # Metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("CNPJ", cnpj)
    mc2.metric(
        "Risco",
        selected["RISCO"],
        delta="REAG" if selected["IS_REAG"] else "Peer",
        delta_color="inverse" if selected["IS_REAG"] else "normal",
    )
    mc3.metric("Score de Risco", f"{selected['SCORE_RISCO']:.0f}/100")
    mc4.metric("PL Atual", f"R$ {selected['PL_ATUAL']/1e6:.1f}M")

    # PL evolution chart
    fund_data = INFORME[INFORME["CNPJ_FUNDO"] == cnpj].sort_values("DT_COMPTC")

    fig_pl = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("Patrimônio Líquido (R$)", "Fluxo Líquido Diário (R$)"),
        row_heights=[0.6, 0.4],
    )
    fig_pl.add_trace(
        go.Scatter(
            x=fund_data["DT_COMPTC"],
            y=fund_data["VL_PATRIM_LIQ"],
            mode="lines",
            name="PL",
            line=dict(color="#4da6ff"),
        ),
        row=1, col=1,
    )
    colors_flow = ["#dc3545" if v < 0 else "#28a745" for v in fund_data["FLUXO_LIQ_DIA"]]
    fig_pl.add_trace(
        go.Bar(
            x=fund_data["DT_COMPTC"],
            y=fund_data["FLUXO_LIQ_DIA"],
            name="Fluxo",
            marker_color=colors_flow,
        ),
        row=2, col=1,
    )
    fig_pl.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig_pl, use_container_width=True)

    # Holdings
    st.subheader("Carteira (Holdings)")
    fund_holdings = HOLDINGS[HOLDINGS["CNPJ_FUNDO"] == cnpj].sort_values("PCT_PL", ascending=False)
    if not fund_holdings.empty:
        fig_holdings = px.treemap(
            fund_holdings,
            path=["TIPO_ATIVO", "NM_ATIVO"],
            values="VL_MERCADO",
            color="STATUS_ATIVO",
            color_discrete_map={
                "FICTITIOUS": "#dc3545",
                "SUSPICIOUS": "#fd7e14",
                "NORMAL": "#28a745",
            },
            title="Composição da Carteira (tamanho = valor de mercado)",
        )
        fig_holdings.update_layout(height=380)
        st.plotly_chart(fig_holdings, use_container_width=True)

        st.dataframe(
            fund_holdings[["TIPO_ATIVO", "NM_ATIVO", "STATUS_ATIVO", "VL_MERCADO", "PCT_PL"]].rename(
                columns={
                    "TIPO_ATIVO": "Tipo",
                    "NM_ATIVO": "Ativo",
                    "STATUS_ATIVO": "Status",
                    "VL_MERCADO": "Valor (R$)",
                    "PCT_PL": "% PL",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Anomaly Detection
# ═══════════════════════════════════════════════════════════════════════════════

def page_anomaly_detection():
    st.title("📈 Detecção de Anomalias de Fluxo")
    st.markdown(
        "Identifica fluxos financeiros com **Z-score** acima do limiar configurado, "
        "indicando movimentações atípicas que podem sinalizar fraude."
    )

    threshold = st.slider("Limiar de Z-score", 1.5, 5.0, 2.5, 0.1)

    # Re-run anomaly detection with chosen threshold
    from src.analyzers.anomaly_detector import AnomalyDetector

    detector = AnomalyDetector()
    anomalies_all = detector.detect_flow_anomalies(INFORME, threshold=threshold)

    if anomalies_all.empty:
        st.info("Nenhuma anomalia encontrada com este limiar.")
        return

    st.metric("Total de anomalias detectadas", len(anomalies_all))

    # Fund selector
    fund_options = ["Todos os fundos REAG"] + RISK_SCORES[RISK_SCORES["IS_REAG"]]["NM_FUNDO"].tolist()
    selected_fund_name = st.selectbox("Fundo", fund_options)

    if selected_fund_name == "Todos os fundos REAG":
        reag_cnpjs = RISK_SCORES[RISK_SCORES["IS_REAG"]]["CNPJ_FUNDO"].tolist()
        fund_anomalies = anomalies_all[anomalies_all["CNPJ_FUNDO"].isin(reag_cnpjs)]
    else:
        cnpj = RISK_SCORES[RISK_SCORES["NM_FUNDO"] == selected_fund_name]["CNPJ_FUNDO"].iloc[0]
        fund_anomalies = anomalies_all[anomalies_all["CNPJ_FUNDO"] == cnpj]

    # Timeline
    fig_timeline = px.scatter(
        fund_anomalies,
        x="DT_COMPTC",
        y="Z_SCORE_FLOW",
        color="NM_FUNDO" if selected_fund_name == "Todos os fundos REAG" else None,
        size=fund_anomalies["FLUXO_LIQ_DIA"].abs(),
        hover_data=["NM_FUNDO", "FLUXO_LIQ_DIA", "VL_PATRIM_LIQ"],
        title=f"Anomalias de Fluxo (Z-score > ±{threshold})",
        labels={"DT_COMPTC": "Data", "Z_SCORE_FLOW": "Z-score"},
    )
    fig_timeline.add_hline(y=threshold, line_dash="dash", line_color="red", annotation_text=f"+{threshold}σ")
    fig_timeline.add_hline(y=-threshold, line_dash="dash", line_color="red", annotation_text=f"−{threshold}σ")
    fig_timeline.update_layout(height=430)
    st.plotly_chart(fig_timeline, use_container_width=True)

    # Z-score histogram
    fig_hist = px.histogram(
        fund_anomalies,
        x="Z_SCORE_FLOW",
        nbins=40,
        color_discrete_sequence=["#e63946"],
        title="Histograma dos Z-scores das anomalias",
        labels={"Z_SCORE_FLOW": "Z-score"},
    )
    fig_hist.update_layout(height=300)
    st.plotly_chart(fig_hist, use_container_width=True)

    # Top anomalies table
    st.subheader("Top 20 anomalias")
    top = fund_anomalies.nlargest(20, "Z_SCORE_FLOW", keep="all").sort_values(
        "Z_SCORE_FLOW", key=abs, ascending=False
    )
    st.dataframe(
        top[["DT_COMPTC", "NM_FUNDO", "FLUXO_LIQ_DIA", "Z_SCORE_FLOW", "VL_PATRIM_LIQ"]].rename(
            columns={
                "DT_COMPTC": "Data",
                "NM_FUNDO": "Fundo",
                "FLUXO_LIQ_DIA": "Fluxo (R$)",
                "Z_SCORE_FLOW": "Z-score",
                "VL_PATRIM_LIQ": "PL (R$)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Benford's Law
# ═══════════════════════════════════════════════════════════════════════════════

def page_benford():
    st.title("🔢 Análise pela Lei de Benford")
    st.markdown(
        "Em conjuntos de dados financeiros naturais, o **primeiro algarismo** segue uma distribuição "
        "logarítmica (Lei de Benford). Desvios significativos sugerem possível **manipulação de dados**."
    )

    # Overview MAD bar chart
    benford_merged = BENFORD.merge(
        RISK_SCORES[["CNPJ_FUNDO", "IS_REAG", "RISCO"]], on="CNPJ_FUNDO", how="left"
    )

    fig_mad = px.bar(
        benford_merged.sort_values("MAD", ascending=False),
        x="NM_FUNDO",
        y="MAD",
        color="BENFORD_RISK",
        color_discrete_map={"HIGH": "#dc3545", "MEDIUM": "#ffc107", "LOW": "#28a745"},
        title="Desvio Médio Absoluto (MAD) da Lei de Benford por fundo",
        labels={"MAD": "MAD", "NM_FUNDO": "Fundo"},
        text_auto=".4f",
    )
    fig_mad.add_hline(y=0.015, line_dash="dash", line_color="#dc3545", annotation_text="Limiar ALTO")
    fig_mad.add_hline(y=0.008, line_dash="dash", line_color="#ffc107", annotation_text="Limiar MÉDIO")
    fig_mad.update_layout(height=400, xaxis_tickangle=-35)
    st.plotly_chart(fig_mad, use_container_width=True)

    # Fund deep-dive
    st.divider()
    st.subheader("Análise individual")
    fund_opts = BENFORD["NM_FUNDO"].tolist()
    selected_fund = st.selectbox("Selecione um fundo", fund_opts)

    row = BENFORD[BENFORD["NM_FUNDO"] == selected_fund].iloc[0]
    obs = row["OBSERVED_FREQ"]
    exp = row["EXPECTED_FREQ"]

    digits = list(range(1, 10))
    obs_vals = [obs.get(d, 0) for d in digits]
    exp_vals = [exp.get(d, 0) for d in digits]

    fig_benford = go.Figure()
    fig_benford.add_trace(
        go.Bar(
            x=[str(d) for d in digits],
            y=exp_vals,
            name="Esperado (Benford)",
            marker_color="#457b9d",
            opacity=0.7,
        )
    )
    fig_benford.add_trace(
        go.Bar(
            x=[str(d) for d in digits],
            y=obs_vals,
            name="Observado",
            marker_color="#e63946",
            opacity=0.85,
        )
    )
    fig_benford.update_layout(
        barmode="group",
        title=f"Distribuição do 1º Algarismo – {selected_fund}",
        xaxis_title="Primeiro algarismo",
        yaxis_title="Frequência relativa",
        height=380,
    )
    st.plotly_chart(fig_benford, use_container_width=True)

    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("Observações", int(row["N_OBSERVACOES"]))
    bc2.metric("MAD", f"{row['MAD']:.4f}")
    bc3.metric("Chi² stat", f"{row['CHI2']:.2f}")

    risk_level = row["BENFORD_RISK"]
    risk_msg = {
        "HIGH": "🔴 **Risco ALTO** – desvio significativo sugere possível manipulação.",
        "MEDIUM": "🟡 **Risco MÉDIO** – desvio moderado, investigação recomendada.",
        "LOW": "🟢 **Risco BAIXO** – distribuição compatível com dados naturais.",
    }
    st.info(risk_msg.get(risk_level, ""))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Fraud Patterns
# ═══════════════════════════════════════════════════════════════════════════════

def page_fraud_patterns():
    st.title("🕵️ Padrões de Fraude Detectados")
    st.markdown(
        "Padrões baseados em casos reais: **Banco Master / REAG (R$ 11,5 bi)**, "
        "Bernie Madoff e outros esquemas documentados pela CVM."
    )

    patterns = {
        "Fluxo Circular": {
            "desc": "Dinheiro circula entre entidades relacionadas sem criar valor real.",
            "formula": "Fundo → Empresa Controlada → Banco Master → Fundo",
            "icon": "🔄",
            "funds": ["Fundo D Mais FIC FIM", "Fundo Bravo FIC FIA", "Fundo Master CRI FIM"],
            "severity": "CRITICAL",
        },
        "Ativos Fantasma": {
            "desc": "CRIs/CRAs declarados na carteira sem registro verificável em B3/ANBIMA.",
            "formula": "VL_MERCADO declarado ≠ valor de mercado real",
            "icon": "👻",
            "funds": ["Fundo D Mais FIC FIM", "Fundo Master CRI FIM"],
            "severity": "CRITICAL",
        },
        "Layering de Fundos": {
            "desc": "Cascata de fundos para dificultar rastreamento de origem dos recursos.",
            "formula": "Fundo A → Fundo B → Fundo C → Ativo Ilíquido",
            "icon": "🪆",
            "funds": ["Fundo Bravo FIC FIA", "Fundo Omega FIC FIM"],
            "severity": "HIGH",
        },
        "Inflação de Ativos": {
            "desc": "Ativos precificados acima do valor de mercado para inflar PL.",
            "formula": "Preço declarado >> preço de mercado (diferença > 20%)",
            "icon": "📈",
            "funds": ["Fundo Nexus Cambial", "Fundo Alpha Multimercado"],
            "severity": "HIGH",
        },
        "Concentração Excessiva": {
            "desc": "Mais de 40% do PL em ativo de um único emissor relacionado.",
            "formula": "HHI > 0.18 (limite regulatório CVM 555)",
            "icon": "⚡",
            "funds": ["Fundo Master CRI FIM", "Fundo D Mais FIC FIM"],
            "severity": "HIGH",
        },
        "Resgates em Sequência": {
            "desc": "5+ dias consecutivos de resgates líquidos (sinal de desconfiança).",
            "formula": "FLUXO_LIQ_DIA < 0 por ≥ 5 dias seguidos",
            "icon": "🏃",
            "funds": ["Fundo Sigma RF FIC", "Fundo Alpha Multimercado"],
            "severity": "MEDIUM",
        },
    }

    for pattern_name, info in patterns.items():
        severity_color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(info["severity"], "⚪")
        with st.expander(f"{info['icon']} {pattern_name}  {severity_color} {info['severity']}"):
            st.markdown(f"**Descrição:** {info['desc']}")
            st.code(info["formula"], language=None)
            st.markdown("**Fundos afetados:**")
            for fn in info["funds"]:
                st.markdown(f"  - {fn}")

    st.divider()
    st.subheader("Resumo de Exposição por Padrão")

    pattern_data = []
    for name, info in patterns.items():
        pattern_data.append(
            {
                "Padrão": f"{info['icon']} {name}",
                "Severidade": info["severity"],
                "Fundos Afetados": len(info["funds"]),
            }
        )
    pdf = pd.DataFrame(pattern_data)

    fig_patterns = px.bar(
        pdf,
        x="Padrão",
        y="Fundos Afetados",
        color="Severidade",
        color_discrete_map={"CRITICAL": "#dc3545", "HIGH": "#fd7e14", "MEDIUM": "#ffc107"},
        title="Número de fundos afetados por padrão de fraude",
        text="Fundos Afetados",
    )
    fig_patterns.update_layout(height=360, xaxis_tickangle=-20)
    st.plotly_chart(fig_patterns, use_container_width=True)

    # Holdings suspect assets heatmap
    st.divider()
    st.subheader("Ativos Suspeitos / Fantasma por Fundo")
    susp = HOLDINGS[HOLDINGS["STATUS_ATIVO"].isin(["FICTITIOUS", "SUSPICIOUS"])].copy()
    if not susp.empty:
        fig_heat = px.bar(
            susp.groupby(["NM_FUNDO", "STATUS_ATIVO"])["PCT_PL"].sum().reset_index(),
            x="NM_FUNDO",
            y="PCT_PL",
            color="STATUS_ATIVO",
            barmode="stack",
            color_discrete_map={"FICTITIOUS": "#dc3545", "SUSPICIOUS": "#fd7e14"},
            labels={"PCT_PL": "% do PL", "NM_FUNDO": "Fundo", "STATUS_ATIVO": "Status do ativo"},
            title="Peso de ativos suspeitos/fictícios no PL (empilhado)",
        )
        fig_heat.update_layout(height=380, xaxis_tickangle=-35)
        st.plotly_chart(fig_heat, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: Peer Comparison
# ═══════════════════════════════════════════════════════════════════════════════

def page_peer_comparison():
    st.title("📋 Comparação com Peers")
    st.markdown(
        "Compara indicadores dos fundos REAG com fundos similares do mercado para identificar "
        "desvios que podem indicar manipulação de resultados."
    )

    # Merge scores with category labels
    df = RISK_SCORES.copy()
    df["Grupo"] = df["IS_REAG"].map({True: "REAG", False: "Peer de Mercado"})

    # Box plots side by side
    metrics = {
        "SCORE_RISCO": "Score de Risco (0-100)",
        "N_ANOMALIAS_FLUXO": "Nº Anomalias de Fluxo",
        "MAX_ZSCORE": "Máximo Z-score",
        "N_QUEDAS_PL": "Nº Quedas de PL",
    }

    metric_choice = st.selectbox("Métrica para comparação", list(metrics.keys()), format_func=lambda k: metrics[k])

    fig_box = px.box(
        df,
        x="CATEGORIA_LABEL",
        y=metric_choice,
        color="Grupo",
        color_discrete_map={"REAG": "#e63946", "Peer de Mercado": "#457b9d"},
        points="all",
        hover_name="NM_FUNDO",
        title=f"{metrics[metric_choice]} – REAG vs. Peers por categoria",
        labels={"CATEGORIA_LABEL": "Categoria"},
    )
    fig_box.update_layout(height=430)
    st.plotly_chart(fig_box, use_container_width=True)

    # Radar chart for top suspect fund
    st.divider()
    st.subheader("Radar de Indicadores – Fundo vs. Mediana de Peers")

    reag_funds = df[df["IS_REAG"]]["NM_FUNDO"].tolist()
    selected = st.selectbox("Fundo REAG", reag_funds)
    fund_row = df[df["NM_FUNDO"] == selected].iloc[0]
    cat = fund_row["CATEGORIA"]
    peers = df[(~df["IS_REAG"]) & (df["CATEGORIA"] == cat)]

    radar_metrics = ["SCORE_RISCO", "N_ANOMALIAS_FLUXO", "MAX_ZSCORE", "N_QUEDAS_PL"]
    radar_labels = ["Score Risco", "Anomalias Fluxo", "Máx Z-score", "Quedas PL"]

    def normalize(series, val):
        mx = max(series.max(), val, 1)
        return val / mx

    fund_vals = [normalize(df[m], fund_row[m]) for m in radar_metrics]
    peer_vals = [normalize(df[m], peers[m].median()) for m in radar_metrics]

    fig_radar = go.Figure()
    fig_radar.add_trace(
        go.Scatterpolar(
            r=fund_vals + [fund_vals[0]],
            theta=radar_labels + [radar_labels[0]],
            fill="toself",
            name=selected,
            line_color="#e63946",
        )
    )
    fig_radar.add_trace(
        go.Scatterpolar(
            r=peer_vals + [peer_vals[0]],
            theta=radar_labels + [radar_labels[0]],
            fill="toself",
            name="Mediana Peers",
            line_color="#457b9d",
        )
    )
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        height=420,
        title=f"Perfil de risco: {selected} vs. peers ({CATEGORY_LABELS.get(cat, cat)})",
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Statistical summary table
    st.divider()
    st.subheader("Estatísticas Descritivas por Grupo")
    stat_cols = ["SCORE_RISCO", "N_ANOMALIAS_FLUXO", "MAX_ZSCORE", "N_QUEDAS_PL"]
    summary = (
        df.groupby("Grupo")[stat_cols]
        .agg(["mean", "median", "max"])
        .round(2)
    )
    summary.columns = [" ".join(c) for c in summary.columns]
    st.dataframe(summary, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════════════

if PAGE == "📊 Dashboard":
    page_dashboard()
elif PAGE == "🏦 Explorar Fundos":
    page_fund_explorer()
elif PAGE == "📈 Anomalias de Fluxo":
    page_anomaly_detection()
elif PAGE == "🔢 Lei de Benford":
    page_benford()
elif PAGE == "🕵️ Padrões de Fraude":
    page_fraud_patterns()
elif PAGE == "📋 Comparação com Peers":
    page_peer_comparison()
