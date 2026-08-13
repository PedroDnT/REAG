"""
Fraud Scheme Detector - Based on Real-World Patterns

Detects specific fraud patterns based on actual cases:
1. Banco Master / REAG (2020-2025): R$ 11.5 billion
2. Bernie Madoff: $65 billion Ponzi
3. Common Brazilian fund fraud patterns

Sources:
- Central Bank investigation of Banco Master
- CVM enforcement actions
- Academic research on investment fraud
"""

import logging

import pandas as pd
from pathlib import Path
from config.constants import (
    ASSET_INFLATION_ILLIQUID_PCT,
    ASSET_INFLATION_MIN_RETURN_PCT,
    SHELL_NETWORK_MIN_COUNT,
)

logger = logging.getLogger(__name__)


class FraudSchemeDetector:
    """
    Detecta esquemas de fraude específicos baseados em padrões conhecidos

    Schemes Implemented:
    1. Circular Flow (Banco Master pattern)
    2. Layered Funds (inflated valuation cascade)
    3. Fictitious Loans
    4. Asset Inflation
    5. Ponzi Structure
    """

    def __init__(self):
        """Inicializa detector de esquemas"""
        self.suspicious_entities = set()
        self.related_entities = {}  # Mapeia entidades a seus relacionados

    def detect_circular_flow(self, informe_df: pd.DataFrame,
                            cda_df: pd.DataFrame,
                            cadastro_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta fluxo circular (padrão Banco Master)

        Pattern:
        1. Empresa recebe "empréstimo" fictício do Banco Master
        2. Empresa investe em fundos REAG (D Mais, Bravo)
        3. Fundos compram ativos de empresas relacionadas
        4. Dinheiro volta ao Banco Master como depósito

        Red Flags:
        - Mesmas entidades aparecem como investidores E emissores
        - Fluxos entre fundos do mesmo administrador
        - Timing suspeito (captação → aplicação → retorno rápido)
        """
        logger.info("Detectando fluxo circular (Banco Master pattern)...")

        # Admins with fewer than two funds cannot form a circular fund-to-fund
        # edge. Build the admin map once; scanning CDA once per fund is O(funds
        # x rows) and stalls a full-universe month for hours.
        admin_fund_counts = cadastro_df.groupby("CNPJ_ADMIN")["CNPJ_FUNDO"].nunique()
        multi_fund_admins = set(admin_fund_counts[admin_fund_counts >= 2].index)
        if not multi_fund_admins:
            logger.info("Nenhum fluxo circular detectado")
            return pd.DataFrame()

        fund_to_admin = (
            cadastro_df.loc[
                cadastro_df["CNPJ_ADMIN"].isin(multi_fund_admins),
                ["CNPJ_FUNDO", "CNPJ_ADMIN"],
            ]
            .drop_duplicates("CNPJ_FUNDO")
            .set_index("CNPJ_FUNDO")["CNPJ_ADMIN"]
        )
        fund_cnpjs = set(fund_to_admin.index)

        holdings = cda_df.loc[cda_df["CD_ATIVO"].isin(fund_cnpjs), [
            "CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO",
        ]].copy()
        if holdings.empty:
            logger.info("Nenhum fluxo circular detectado")
            return pd.DataFrame()

        holdings["holder_admin"] = holdings["CNPJ_FUNDO"].map(fund_to_admin)
        holdings["asset_admin"] = holdings["CD_ATIVO"].map(fund_to_admin)
        circular = holdings[
            holdings["holder_admin"].notna()
            & holdings["asset_admin"].notna()
            & (holdings["holder_admin"] == holdings["asset_admin"])
            & (holdings["CNPJ_FUNDO"] != holdings["CD_ATIVO"])
        ]
        if circular.empty:
            logger.info("Nenhum fluxo circular detectado")
            return pd.DataFrame()

        # total_value matches the pre-vectorized detector: sum over every holder
        # of the asset, not only same-admin circular edges.
        total_by_asset = holdings.groupby("CD_ATIVO")["VL_MERCADO"].sum()

        circular_flows = []
        for (admin_cnpj, fund_cnpj), group in circular.groupby(
            ["asset_admin", "CD_ATIVO"], sort=False
        ):
            holders = group["CNPJ_FUNDO"].unique().tolist()
            circular_flows.append({
                "admin_cnpj": admin_cnpj,
                "fund_as_asset": fund_cnpj,
                "held_by_funds": holders,
                "num_circular_connections": len(holders),
                "total_value": float(total_by_asset.get(fund_cnpj, 0.0)),
                "fraud_pattern": "CIRCULAR_FUND_INVESTMENT",
                "severity": "CRITICAL",
                "banco_master_similarity": "HIGH",
            })

        result_df = pd.DataFrame(circular_flows)

        if not result_df.empty:
            logger.warning(f"{len(result_df)} casos de fluxo circular detectados!")
        else:
            logger.info("Nenhum fluxo circular detectado")

        return result_df

    def detect_layered_funds(self, cda_df: pd.DataFrame,
                            informe_df: pd.DataFrame,
                            cadastro_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta "fundos em camadas" (Banco Master pattern)

        Pattern:
        1. Fundo A investe em ativos ilíquidos
        2. Ativos são marcados com valorização contábil artificial
        3. Fundo B é criado e investe no Fundo A (já inflado)
        4. Fundo C investe no Fundo B
        5. Cada camada amplifica a fraude

        Red Flags:
        - Fundos que investem em outros fundos do mesmo administrador
        - Retornos muito altos em curto período
        - Fundos recentes com performance "milagrosa"
        """
        logger.info("Detectando fundos em camadas...")

        # Identificar fundos que investem em outros fundos
        fund_holdings = cda_df[cda_df["CD_ATIVO"].str.len() == 14].copy()  # CNPJs = fundos

        if fund_holdings.empty:
            logger.info("Nenhuma estrutura de camadas detectada")
            return pd.DataFrame()

        fund_to_admin = cadastro_df.set_index("CNPJ_FUNDO")["CNPJ_ADMIN"].to_dict()
        fund_holdings["holder_admin"] = fund_holdings["CNPJ_FUNDO"].map(fund_to_admin)
        fund_holdings["held_admin"] = fund_holdings["CD_ATIVO"].map(fund_to_admin)

        same_admin = fund_holdings[
            fund_holdings["holder_admin"].notna()
            & fund_holdings["held_admin"].notna()
            & (fund_holdings["holder_admin"] == fund_holdings["held_admin"])
        ]
        if same_admin.empty:
            logger.info("Nenhuma estrutura de camadas detectada")
            return pd.DataFrame()

        # Precompute mean daily returns once. Looking up informe per edge was
        # O(edges x informe rows) and dominates a full-universe run.
        avg_daily_return = self._mean_daily_quota_return_by_fund(informe_df)
        if avg_daily_return.empty:
            logger.info("Nenhuma estrutura de camadas detectada")
            return pd.DataFrame()

        same_admin = same_admin.copy()
        same_admin["holder_avg_daily_return"] = same_admin["CNPJ_FUNDO"].map(avg_daily_return)
        same_admin["held_avg_daily_return"] = same_admin["CD_ATIVO"].map(avg_daily_return)
        flagged = same_admin[
            same_admin["holder_avg_daily_return"].notna()
            & same_admin["held_avg_daily_return"].notna()
            & (
                (same_admin["holder_avg_daily_return"] > 1)
                | (same_admin["held_avg_daily_return"] > 1)
            )
        ]

        layered_structures = []
        for row in flagged.itertuples():
            layered_structures.append({
                "admin_cnpj": row.holder_admin,
                "holder_fund": row.CNPJ_FUNDO,
                "held_fund": row.CD_ATIVO,
                "investment_value": row.VL_MERCADO,
                "holder_avg_daily_return": row.holder_avg_daily_return,
                "held_avg_daily_return": row.held_avg_daily_return,
                "fraud_pattern": "LAYERED_FUND_STRUCTURE",
                "severity": "HIGH" if row.holder_avg_daily_return > 2 else "MEDIUM",
                "banco_master_similarity": "MEDIUM",
            })

        result_df = pd.DataFrame(layered_structures)

        if not result_df.empty:
            logger.warning(f"{len(result_df)} estruturas em camadas detectadas!")
        else:
            logger.info("Nenhuma estrutura em camadas detectada")

        return result_df

    def detect_asset_inflation(self, cda_df: pd.DataFrame,
                              informe_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta inflação artificial de ativos (Banco Master pattern)

        Pattern:
        1. Ativos ilíquidos são marcados a valor de mercado "interno"
        2. Valorização contábil sem negociação real
        3. Patrimônio líquido cresce artificialmente
        4. Performance "milagrosa" sem justificativa

        Red Flags:
        - Alta concentração em ativos ilíquidos (CRI, CRA, debêntures privadas)
        - Performance muito acima do mercado
        - Crescimento de PL incompatível com fluxos
        """
        logger.info("Detectando inflacao de ativos...")

        # The legacy detector only emitted findings when PL was available to
        # compute avg_pl_change; keep that gate so an informe without the
        # column cannot suddenly start flagging inflation cases.
        if (
            cda_df.empty
            or informe_df.empty
            or "VL_PATRIM_LIQ" not in informe_df.columns
        ):
            logger.info("Nenhuma inflacao de ativos detectada")
            return pd.DataFrame()

        portfolio = cda_df[["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO"]].copy()
        portfolio["VL_MERCADO"] = pd.to_numeric(portfolio["VL_MERCADO"], errors="coerce").fillna(0.0)
        illiquid_pattern = "CRI|CRA|DEBENTURE|CDB"
        portfolio["is_illiquid"] = portfolio["CD_ATIVO"].astype(str).str.contains(
            illiquid_pattern, case=False, na=False, regex=True
        )
        portfolio["illiquid_value"] = portfolio["VL_MERCADO"].where(portfolio["is_illiquid"], 0.0)

        by_fund = portfolio.groupby("CNPJ_FUNDO", sort=False).agg(
            total_portfolio_value=("VL_MERCADO", "sum"),
            illiquid_value=("illiquid_value", "sum"),
        )
        by_fund = by_fund[by_fund["total_portfolio_value"] > 0]
        if by_fund.empty:
            logger.info("Nenhuma inflacao de ativos detectada")
            return pd.DataFrame()

        by_fund["illiquid_pct"] = (
            by_fund["illiquid_value"] / by_fund["total_portfolio_value"] * 100.0
        )

        avg_return = self._mean_daily_quota_return_by_fund(informe_df)
        avg_pl_change = self._mean_daily_pl_change_by_fund(informe_df)
        by_fund = by_fund.join(avg_return.rename("avg_daily_return"), how="inner")
        by_fund = by_fund.join(avg_pl_change.rename("avg_pl_change"), how="left")

        flagged = by_fund[
            (by_fund["illiquid_pct"] > ASSET_INFLATION_ILLIQUID_PCT)
            & (by_fund["avg_daily_return"] > ASSET_INFLATION_MIN_RETURN_PCT)
        ]
        if flagged.empty:
            logger.info("Nenhuma inflacao de ativos detectada")
            return pd.DataFrame()

        inflation_cases = []
        for fund_cnpj, row in flagged.iterrows():
            inflation_cases.append({
                "fund_cnpj": fund_cnpj,
                "total_portfolio_value": row["total_portfolio_value"],
                "illiquid_pct": row["illiquid_pct"],
                "avg_daily_return": row["avg_daily_return"],
                "avg_pl_change": row["avg_pl_change"],
                "fraud_pattern": "ILLIQUID_ASSET_INFLATION",
                "severity": "CRITICAL" if row["illiquid_pct"] > 85 else "HIGH",
                "banco_master_similarity": "HIGH",
                "explanation": (
                    f"{row['illiquid_pct']:.0f}% illiquid assets with "
                    f"{row['avg_daily_return']:.2f}% daily return"
                ),
            })

        result_df = pd.DataFrame(inflation_cases)

        if not result_df.empty:
            logger.warning(f"{len(result_df)} casos de inflacao de ativos detectados!")
        else:
            logger.info("Nenhuma inflacao de ativos detectada")

        return result_df

    def detect_shell_company_network(self, cda_df: pd.DataFrame,
                                     cadastro_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta rede de empresas de fachada (Banco Master pattern)

        Pattern (Banco Master):
        - 36 empresas participaram do esquema
        - Maioria eram pequenas empresas/shells
        - Recebiam "empréstimos" fictícios
        - Investiam nos fundos REAG

        Red Flags:
        - Múltiplos emissores pequenos/desconhecidos
        - Mesmo padrão de naming (LTDA ME, EIRELI)
        - Concentração de emissores em fundos do mesmo administrador
        """
        logger.info("Detectando redes de empresas de fachada...")

        if "EMISSOR" not in cda_df.columns:
            logger.warning("Coluna EMISSOR nao encontrada")
            return pd.DataFrame()

        shell_patterns = ["LTDA ME", "LTDA-ME", "EIRELI", "LTDA EPP"]
        shell_regex = "|".join(shell_patterns)

        fund_to_admin = (
            cadastro_df[["CNPJ_FUNDO", "CNPJ_ADMIN"]]
            .dropna()
            .drop_duplicates("CNPJ_FUNDO")
            .set_index("CNPJ_FUNDO")["CNPJ_ADMIN"]
        )
        admin_fund_counts = cadastro_df.groupby("CNPJ_ADMIN")["CNPJ_FUNDO"].nunique()

        portfolio = cda_df[["CNPJ_FUNDO", "EMISSOR", "VL_MERCADO"]].copy()
        portfolio["CNPJ_ADMIN"] = portfolio["CNPJ_FUNDO"].map(fund_to_admin)
        portfolio = portfolio.dropna(subset=["CNPJ_ADMIN"])
        if portfolio.empty:
            logger.info("Nenhuma rede de shells detectada")
            return pd.DataFrame()

        portfolio["EMISSOR"] = portfolio["EMISSOR"].astype(str)
        portfolio["is_shell"] = portfolio["EMISSOR"].str.upper().str.contains(
            shell_regex, na=False, regex=True
        )

        shell_networks = []
        for admin_cnpj, admin_portfolio in portfolio.groupby("CNPJ_ADMIN", sort=False):
            suspicious_issuers = (
                admin_portfolio.loc[admin_portfolio["is_shell"], "EMISSOR"]
                .drop_duplicates()
                .tolist()
            )
            if len(suspicious_issuers) < SHELL_NETWORK_MIN_COUNT:
                continue

            suspicious_value = admin_portfolio.loc[
                admin_portfolio["is_shell"], "VL_MERCADO"
            ].sum()
            total_value = admin_portfolio["VL_MERCADO"].sum()
            shell_networks.append({
                "admin_cnpj": admin_cnpj,
                "num_suspicious_issuers": len(suspicious_issuers),
                "suspicious_issuers": suspicious_issuers[:10],
                "suspicious_value": suspicious_value,
                "suspicious_pct": (suspicious_value / total_value * 100) if total_value > 0 else 0,
                "num_funds_affected": int(admin_fund_counts.get(admin_cnpj, 0)),
                "fraud_pattern": "SHELL_COMPANY_NETWORK",
                "severity": "CRITICAL" if len(suspicious_issuers) > 20 else "HIGH",
                "banco_master_similarity": "VERY_HIGH",
                "explanation": f"{len(suspicious_issuers)} shell companies detected",
            })

        result_df = pd.DataFrame(shell_networks)

        if not result_df.empty:
            logger.warning(f"{len(result_df)} redes de empresas de fachada detectadas!")
        else:
            logger.info("Nenhuma rede de shells detectada")

        return result_df

    @staticmethod
    def _mean_daily_quota_return_by_fund(informe_df: pd.DataFrame) -> pd.Series:
        """Mean daily VL_QUOTA percent change per fund, as percent points."""
        if informe_df.empty or "VL_QUOTA" not in informe_df.columns:
            return pd.Series(dtype=float)

        work = informe_df[["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]].copy()
        work["DT_COMPTC"] = pd.to_datetime(work["DT_COMPTC"], errors="coerce")
        work["VL_QUOTA"] = pd.to_numeric(work["VL_QUOTA"], errors="coerce")
        work = work.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
        work = work.sort_values(["CNPJ_FUNDO", "DT_COMPTC"])
        work["daily_return"] = work.groupby("CNPJ_FUNDO", sort=False)["VL_QUOTA"].pct_change()
        return work.groupby("CNPJ_FUNDO", sort=False)["daily_return"].mean() * 100.0

    @staticmethod
    def _mean_daily_pl_change_by_fund(informe_df: pd.DataFrame) -> pd.Series:
        """Mean daily VL_PATRIM_LIQ percent change per fund, as percent points."""
        if informe_df.empty or "VL_PATRIM_LIQ" not in informe_df.columns:
            return pd.Series(dtype=float)

        work = informe_df[["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"]].copy()
        work["DT_COMPTC"] = pd.to_datetime(work["DT_COMPTC"], errors="coerce")
        work["VL_PATRIM_LIQ"] = pd.to_numeric(work["VL_PATRIM_LIQ"], errors="coerce")
        work = work.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_PATRIM_LIQ"])
        work = work.sort_values(["CNPJ_FUNDO", "DT_COMPTC"])
        work["pl_change"] = work.groupby("CNPJ_FUNDO", sort=False)["VL_PATRIM_LIQ"].pct_change()
        return work.groupby("CNPJ_FUNDO", sort=False)["pl_change"].mean() * 100.0

    def generate_fraud_scheme_report(self, informe_df: pd.DataFrame,
                                     cda_df: pd.DataFrame,
                                     cadastro_df: pd.DataFrame,
                                     output_path: Path | None = None) -> dict[str, pd.DataFrame]:
        """
        Gera relatório completo de esquemas de fraude

        Detecta os 4 principais padrões do caso Banco Master:
        1. Fluxo circular
        2. Fundos em camadas
        3. Inflação de ativos
        4. Rede de shells
        """
        logger.info("=" * 70)
        logger.info("DETECCAO DE ESQUEMAS DE FRAUDE - PADRAO BANCO MASTER")
        logger.info("=" * 70)

        # Executar todas as análises
        circular = self.detect_circular_flow(informe_df, cda_df, cadastro_df)
        layered = self.detect_layered_funds(cda_df, informe_df, cadastro_df)
        inflation = self.detect_asset_inflation(cda_df, informe_df)
        shells = self.detect_shell_company_network(cda_df, cadastro_df)

        # Salvar relatórios
        if output_path:
            output_path = Path(output_path)
            output_path.mkdir(parents=True, exist_ok=True)

            if not circular.empty:
                circular.to_csv(output_path / 'circular_flow.csv', index=False)
                logger.info(f"Circular flow saved: {output_path / 'circular_flow.csv'}")

            if not layered.empty:
                layered.to_csv(output_path / 'layered_funds.csv', index=False)
                logger.info(f"Layered funds saved: {output_path / 'layered_funds.csv'}")

            if not inflation.empty:
                inflation.to_csv(output_path / 'asset_inflation.csv', index=False)
                logger.info(f"Asset inflation saved: {output_path / 'asset_inflation.csv'}")

            if not shells.empty:
                shells.to_csv(output_path / 'shell_networks.csv', index=False)
                logger.info(f"Shell networks saved: {output_path / 'shell_networks.csv'}")

        # Resumo
        logger.info("=" * 70)
        logger.info("RESUMO DE ESQUEMAS DETECTADOS")
        logger.info("=" * 70)

        logger.info(f"1. Fluxo Circular:          {len(circular)} casos")
        logger.info(f"2. Fundos em Camadas:        {len(layered)} casos")
        logger.info(f"3. Inflacao de Ativos:       {len(inflation)} casos")
        logger.info(f"4. Redes de Shells:          {len(shells)} casos")

        total_schemes = len(circular) + len(layered) + len(inflation) + len(shells)
        logger.warning(f"TOTAL DE ESQUEMAS:        {total_schemes}")

        if total_schemes > 0:
            logger.warning("PADRAO BANCO MASTER DETECTADO!")
            logger.warning("    Multiplos esquemas indicam fraude sistemica.")
            logger.warning("    Recomenda-se investigacao imediata.")
        else:
            logger.info("Nenhum esquema de fraude obvio detectado")

        return {
            'circular_flow': circular,
            'layered_funds': layered,
            'asset_inflation': inflation,
            'shell_networks': shells
        }
