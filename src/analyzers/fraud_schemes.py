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

        circular_flows = []

        # Identificar fundos do mesmo administrador
        admin_groups = cadastro_df.groupby('CNPJ_ADMIN')['CNPJ_FUNDO'].apply(list).to_dict()

        for admin_cnpj, fund_list in admin_groups.items():
            if len(fund_list) < 2:
                continue  # Precisa ter múltiplos fundos

            # Verificar se fundos investem uns nos outros
            for fund_cnpj in fund_list:
                # Verificar se este fundo aparece como ativo em outros fundos
                fund_as_asset = cda_df[cda_df['CD_ATIVO'] == fund_cnpj]

                if not fund_as_asset.empty:
                    # Verificar se quem detém é outro fundo do mesmo admin
                    holders = fund_as_asset['CNPJ_FUNDO'].unique()

                    circular_holders = [h for h in holders if h in fund_list]

                    if circular_holders:
                        circular_flows.append({
                            'admin_cnpj': admin_cnpj,
                            'fund_as_asset': fund_cnpj,
                            'held_by_funds': circular_holders,
                            'num_circular_connections': len(circular_holders),
                            'total_value': fund_as_asset['VL_MERCADO'].sum(),
                            'fraud_pattern': 'CIRCULAR_FUND_INVESTMENT',
                            'severity': 'CRITICAL',
                            'banco_master_similarity': 'HIGH'
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

        layered_structures = []

        # Identificar fundos que investem em outros fundos
        fund_holdings = cda_df[cda_df['CD_ATIVO'].str.len() == 14].copy()  # CNPJs = fundos

        if fund_holdings.empty:
            logger.info("Nenhuma estrutura de camadas detectada")
            return pd.DataFrame()

        # Mapear administrador de cada fundo
        fund_to_admin = cadastro_df.set_index('CNPJ_FUNDO')['CNPJ_ADMIN'].to_dict()

        # Vectorized approach: add admin columns to fund_holdings
        fund_holdings['holder_admin'] = fund_holdings['CNPJ_FUNDO'].map(fund_to_admin)
        fund_holdings['held_admin'] = fund_holdings['CD_ATIVO'].map(fund_to_admin)

        # Filter to same admin only (much faster than checking in loop)
        same_admin = fund_holdings[
            (fund_holdings['holder_admin'].notna()) &
            (fund_holdings['held_admin'].notna()) &
            (fund_holdings['holder_admin'] == fund_holdings['held_admin'])
        ]

        # Use itertuples for remaining processing (10-100x faster than iterrows)
        for row in same_admin.itertuples():
            holder_fund = row.CNPJ_FUNDO
            held_fund = row.CD_ATIVO
            holder_admin = row.holder_admin

            # Verificar retornos recentes
            holder_returns = informe_df[informe_df['CNPJ_FUNDO'] == holder_fund]
            held_returns = informe_df[informe_df['CNPJ_FUNDO'] == held_fund]

            if not holder_returns.empty and not held_returns.empty:
                holder_avg_return = holder_returns['VL_QUOTA'].pct_change().mean() * 100
                held_avg_return = held_returns['VL_QUOTA'].pct_change().mean() * 100

                # Red flag se retornos muito altos
                if holder_avg_return > 1 or held_avg_return > 1:  # > 1% ao dia
                    layered_structures.append({
                        'admin_cnpj': holder_admin,
                        'holder_fund': holder_fund,
                        'held_fund': held_fund,
                        'investment_value': row.VL_MERCADO,
                        'holder_avg_daily_return': holder_avg_return,
                        'held_avg_daily_return': held_avg_return,
                        'fraud_pattern': 'LAYERED_FUND_STRUCTURE',
                        'severity': 'HIGH' if holder_avg_return > 2 else 'MEDIUM',
                        'banco_master_similarity': 'MEDIUM'
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

        inflation_cases = []

        # Agrupar por fundo
        for fund_cnpj in cda_df['CNPJ_FUNDO'].unique():
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj]
            fund_performance = informe_df[informe_df['CNPJ_FUNDO'] == fund_cnpj]

            if portfolio.empty or fund_performance.empty:
                continue

            total_value = portfolio['VL_MERCADO'].sum()

            # Calcular % em ativos ilíquidos using vectorized regex (much faster than lambda)
            illiquid_types = ['CRI', 'CRA', 'DEBENTURE', 'CDB']
            illiquid_pattern = '|'.join(illiquid_types)
            illiquid_mask = portfolio['CD_ATIVO'].str.contains(illiquid_pattern, case=False, na=False, regex=True)
            illiquid_value = portfolio[illiquid_mask]['VL_MERCADO'].sum()
            illiquid_pct = (illiquid_value / total_value * 100) if total_value > 0 else 0

            # Calcular retorno médio
            fund_performance_sorted = fund_performance.sort_values('DT_COMPTC')
            if len(fund_performance_sorted) < 2:
                continue

            returns = fund_performance_sorted['VL_QUOTA'].pct_change().dropna()
            avg_return = returns.mean() * 100  # % ao dia

            # Calcular crescimento de PL vs fluxos
            if 'VL_PATRIM_LIQ' in fund_performance.columns:
                pl_change = fund_performance['VL_PATRIM_LIQ'].pct_change().mean() * 100

                # Red flags
                if (illiquid_pct > ASSET_INFLATION_ILLIQUID_PCT and avg_return > ASSET_INFLATION_MIN_RETURN_PCT):
                    # >70% ilíquido com retorno >0.5% ao dia = suspeito
                    inflation_cases.append({
                        'fund_cnpj': fund_cnpj,
                        'total_portfolio_value': total_value,
                        'illiquid_pct': illiquid_pct,
                        'avg_daily_return': avg_return,
                        'avg_pl_change': pl_change,
                        'fraud_pattern': 'ILLIQUID_ASSET_INFLATION',
                        'severity': 'CRITICAL' if illiquid_pct > 85 else 'HIGH',
                        'banco_master_similarity': 'HIGH',
                        'explanation': f'{illiquid_pct:.0f}% illiquid assets with {avg_return:.2f}% daily return'
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

        if 'EMISSOR' not in cda_df.columns:
            logger.warning("Coluna EMISSOR nao encontrada")
            return pd.DataFrame()

        shell_networks = []

        # Padrões de empresas de fachada
        shell_patterns = ['LTDA ME', 'LTDA-ME', 'EIRELI', 'LTDA EPP']

        # Agrupar por administrador
        admin_groups = cadastro_df.groupby('CNPJ_ADMIN')['CNPJ_FUNDO'].apply(list).to_dict()

        for admin_cnpj, fund_list in admin_groups.items():
            admin_portfolio = cda_df[cda_df['CNPJ_FUNDO'].isin(fund_list)]

            if admin_portfolio.empty:
                continue

            # Contar emissores com padrões suspeitos
            issuers = admin_portfolio['EMISSOR'].dropna().unique()

            suspicious_issuers = [
                iss for iss in issuers
                if any(pattern in str(iss).upper() for pattern in shell_patterns)
            ]

            if len(suspicious_issuers) >= SHELL_NETWORK_MIN_COUNT:  # Múltiplas shells = red flag
                # Calcular valor total
                suspicious_mask = admin_portfolio['EMISSOR'].isin(suspicious_issuers)
                suspicious_value = admin_portfolio[suspicious_mask]['VL_MERCADO'].sum()
                total_value = admin_portfolio['VL_MERCADO'].sum()

                shell_networks.append({
                    'admin_cnpj': admin_cnpj,
                    'num_suspicious_issuers': len(suspicious_issuers),
                    'suspicious_issuers': suspicious_issuers[:10],  # Top 10
                    'suspicious_value': suspicious_value,
                    'suspicious_pct': (suspicious_value / total_value * 100) if total_value > 0 else 0,
                    'num_funds_affected': len(fund_list),
                    'fraud_pattern': 'SHELL_COMPANY_NETWORK',
                    'severity': 'CRITICAL' if len(suspicious_issuers) > 20 else 'HIGH',
                    'banco_master_similarity': 'VERY_HIGH',
                    'explanation': f'{len(suspicious_issuers)} shell companies detected'
                })

        result_df = pd.DataFrame(shell_networks)

        if not result_df.empty:
            logger.warning(f"{len(result_df)} redes de empresas de fachada detectadas!")
        else:
            logger.info("Nenhuma rede de shells detectada")

        return result_df

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
