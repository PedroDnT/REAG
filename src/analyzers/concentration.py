"""
Concentration Analyzer - Analisa concentração de carteiras

Detecta concentração excessiva em poucos ativos, violações regulatórias
e exposição a partes relacionadas.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Set
from pathlib import Path


class ConcentrationAnalyzer:
    """
    Analisa concentração de carteiras de fundos

    Calcula:
    - Índice Herfindahl-Hirschman (HHI)
    - Concentração Top N posições
    - Violações de limites regulatórios
    - Concentração em partes relacionadas
    """

    def __init__(self):
        """Inicializa o analisador de concentração"""
        # Limites regulatórios por categoria (simplificado)
        self.concentration_limits = {
            'FIXED_INCOME': 0.20,  # Max 20% em um emissor
            'MULTI_MARKET': 0.25,  # Max 25% em um emissor
            'EQUITY': 0.30,  # Max 30% em uma posição
            'DEFAULT': 0.25
        }

        self.fund_categories = {}
        self.related_issuers = set()

    def load_fund_categories(self, categories: Dict[str, str]):
        """
        Carrega categorias de fundos

        Args:
            categories: Dict {CNPJ_FUNDO: categoria}
        """
        self.fund_categories = categories
        print(f"✅ {len(self.fund_categories):,} fundos categorizados")

    def set_related_issuers(self, issuers: Set[str]):
        """
        Define lista de emissores relacionados ao administrador

        Args:
            issuers: Set de emissores relacionados
        """
        self.related_issuers = issuers
        print(f"✅ {len(self.related_issuers)} emissores relacionados cadastrados")

    def calculate_herfindahl_index(self, portfolio_df: pd.DataFrame) -> float:
        """
        Calcula índice Herfindahl-Hirschman (HHI)

        HHI = sum(peso_i^2)
        - HHI próximo de 1 = muito concentrado (uma posição domina)
        - HHI próximo de 0 = muito diversificado

        Args:
            portfolio_df: DataFrame com carteira (deve ter coluna VL_MERCADO)

        Returns:
            HHI
        """
        if 'VL_MERCADO' not in portfolio_df.columns:
            return 0.0

        total_value = portfolio_df['VL_MERCADO'].sum()

        if total_value == 0:
            return 0.0

        weights = portfolio_df['VL_MERCADO'] / total_value
        hhi = (weights ** 2).sum()

        return hhi

    def analyze_fund_concentration(self, cda_df: pd.DataFrame,
                                  fund_cnpj: str) -> Dict:
        """
        Analisa concentração de um fundo específico

        Args:
            cda_df: DataFrame do CDA
            fund_cnpj: CNPJ do fundo

        Returns:
            Dict com métricas de concentração
        """
        portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj].copy()

        if portfolio.empty or 'VL_MERCADO' not in portfolio.columns:
            return {}

        total_value = portfolio['VL_MERCADO'].sum()

        if total_value == 0:
            return {}

        # HHI
        hhi = self.calculate_herfindahl_index(portfolio)

        # Top N posições
        portfolio_sorted = portfolio.sort_values('VL_MERCADO', ascending=False)

        top1_value = portfolio_sorted.iloc[0]['VL_MERCADO'] if len(portfolio_sorted) > 0 else 0
        top1_pct = (top1_value / total_value * 100) if total_value > 0 else 0

        top5_value = portfolio_sorted.head(5)['VL_MERCADO'].sum()
        top5_pct = (top5_value / total_value * 100) if total_value > 0 else 0

        top10_value = portfolio_sorted.head(10)['VL_MERCADO'].sum()
        top10_pct = (top10_value / total_value * 100) if total_value > 0 else 0

        # Categoria e limite
        category = self.fund_categories.get(fund_cnpj, 'DEFAULT')
        regulatory_limit = self.concentration_limits.get(category, 0.25)

        # Violações
        violates_limit = top1_pct > (regulatory_limit * 100)

        # Número de posições
        num_positions = len(portfolio)

        return {
            'CNPJ_FUNDO': fund_cnpj,
            'category': category,
            'num_positions': num_positions,
            'total_portfolio_value': total_value,

            # HHI
            'hhi': hhi,

            # Concentração Top N
            'top1_pct': top1_pct,
            'top5_pct': top5_pct,
            'top10_pct': top10_pct,

            # Limites
            'regulatory_limit_pct': regulatory_limit * 100,
            'violates_limit': violates_limit,

            # Maior posição
            'largest_position': portfolio_sorted.iloc[0]['CD_ATIVO'] if len(portfolio_sorted) > 0 else None,
            'largest_position_value': top1_value
        }

    def detect_excessive_concentration(self, cda_df: pd.DataFrame,
                                      target_funds: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Detecta concentração excessiva em fundos

        Args:
            cda_df: DataFrame do CDA
            target_funds: Lista de fundos a analisar (None = todos)

        Returns:
            DataFrame com fundos que violam limites
        """
        print("🔍 Detectando concentração excessiva...")

        if target_funds is None:
            target_funds = cda_df['CNPJ_FUNDO'].unique()

        violations = []

        for fund_cnpj in target_funds:
            metrics = self.analyze_fund_concentration(cda_df, fund_cnpj)

            if not metrics:
                continue

            # Critérios de red flag
            is_violation = (
                metrics['violates_limit'] or  # Violação regulatória
                metrics['hhi'] > 0.25 or  # HHI muito alto
                metrics['top5_pct'] > 75  # Top 5 > 75%
            )

            if is_violation:
                # Determinar severity
                if metrics['top1_pct'] > 50:
                    severity = 'CRITICAL'
                elif metrics['top1_pct'] > 40:
                    severity = 'HIGH'
                else:
                    severity = 'MEDIUM'

                # Determinar fraud flag
                fraud_flags = []
                if metrics['violates_limit']:
                    fraud_flags.append('REGULATORY_VIOLATION')
                if metrics['hhi'] > 0.30:
                    fraud_flags.append('EXTREME_CONCENTRATION')
                if metrics['top5_pct'] > 85:
                    fraud_flags.append('INSUFFICIENT_DIVERSIFICATION')

                metrics['severity'] = severity
                metrics['fraud_flags'] = ', '.join(fraud_flags)
                violations.append(metrics)

        result_df = pd.DataFrame(violations)

        if not result_df.empty:
            result_df = result_df.sort_values('top1_pct', ascending=False)
            print(f"⚠️  {len(result_df)} fundos com concentração excessiva!")
        else:
            print("✅ Nenhuma violação de concentração detectada")

        return result_df

    def detect_related_party_concentration(self, cda_df: pd.DataFrame,
                                          target_funds: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Detecta concentração em partes relacionadas

        Args:
            cda_df: DataFrame do CDA (deve ter coluna EMISSOR ou similar)
            target_funds: Lista de fundos a analisar (None = todos)

        Returns:
            DataFrame com fundos concentrados em partes relacionadas
        """
        print("🔍 Detectando concentração em partes relacionadas...")

        if not self.related_issuers:
            print("⚠️  Nenhum emissor relacionado cadastrado")
            return pd.DataFrame()

        if 'EMISSOR' not in cda_df.columns:
            # Tentar extrair emissor do código do ativo
            print("⚠️  Coluna EMISSOR não encontrada no CDA")
            return pd.DataFrame()

        if target_funds is None:
            target_funds = cda_df['CNPJ_FUNDO'].unique()

        related_concentration = []

        for fund_cnpj in target_funds:
            portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj].copy()

            if portfolio.empty or 'VL_MERCADO' not in portfolio.columns:
                continue

            total_value = portfolio['VL_MERCADO'].sum()

            if total_value == 0:
                continue

            # Identificar ativos de partes relacionadas
            portfolio['is_related'] = portfolio['EMISSOR'].isin(self.related_issuers)
            related_assets = portfolio[portfolio['is_related']]

            if related_assets.empty:
                continue

            # Calcular concentração
            related_value = related_assets['VL_MERCADO'].sum()
            related_pct = (related_value / total_value * 100)

            # Red flag: > 30% em relacionadas
            if related_pct > 30:
                related_concentration.append({
                    'CNPJ_FUNDO': fund_cnpj,
                    'total_portfolio_value': total_value,
                    'related_party_value': related_value,
                    'related_party_pct': related_pct,
                    'num_related_positions': len(related_assets),
                    'related_issuers': related_assets['EMISSOR'].unique().tolist(),
                    'fraud_flag': 'RELATED_PARTY_CONCENTRATION',
                    'severity': 'CRITICAL' if related_pct > 50 else 'HIGH'
                })

        result_df = pd.DataFrame(related_concentration)

        if not result_df.empty:
            result_df = result_df.sort_values('related_party_pct', ascending=False)
            print(f"⚠️  {len(result_df)} fundos com concentração em partes relacionadas!")
        else:
            print("✅ Nenhuma concentração em partes relacionadas detectada")

        return result_df

    def analyze_concentration_evolution(self, cda_df: pd.DataFrame,
                                       fund_cnpj: str) -> pd.DataFrame:
        """
        Analisa evolução da concentração ao longo do tempo

        Args:
            cda_df: DataFrame do CDA com múltiplas datas
            fund_cnpj: CNPJ do fundo

        Returns:
            DataFrame com evolução temporal
        """
        print(f"📊 Analisando evolução de concentração para {fund_cnpj}...")

        if 'DT_COMPTC' not in cda_df.columns:
            print("⚠️  Coluna DT_COMPTC não encontrada")
            return pd.DataFrame()

        portfolio = cda_df[cda_df['CNPJ_FUNDO'] == fund_cnpj].copy()

        if portfolio.empty:
            print("⚠️  Fundo não encontrado")
            return pd.DataFrame()

        # Agrupar por data
        dates = sorted(portfolio['DT_COMPTC'].unique())

        evolution = []

        for date in dates:
            date_portfolio = portfolio[portfolio['DT_COMPTC'] == date]
            metrics = self.analyze_fund_concentration(
                pd.DataFrame(date_portfolio),
                fund_cnpj
            )

            if metrics:
                metrics['date'] = date
                evolution.append(metrics)

        result_df = pd.DataFrame(evolution)

        if not result_df.empty:
            result_df = result_df.sort_values('date')
            print(f"✅ {len(result_df)} snapshots temporais")
        else:
            print("⚠️  Nenhum dado temporal disponível")

        return result_df

    def generate_concentration_report(self, cda_df: pd.DataFrame,
                                     target_funds: Optional[List[str]] = None,
                                     output_path: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
        """
        Gera relatório completo de concentração

        Args:
            cda_df: DataFrame do CDA
            target_funds: Lista de fundos a analisar (None = todos)
            output_path: Diretório para salvar relatórios (opcional)

        Returns:
            Dict com DataFrames de análises
        """
        print("\n" + "="*60)
        print("📊 ANÁLISE DE CONCENTRAÇÃO DE CARTEIRAS")
        print("="*60)

        # Concentração excessiva
        excessive_conc = self.detect_excessive_concentration(cda_df, target_funds)

        # Partes relacionadas
        related_party = self.detect_related_party_concentration(cda_df, target_funds)

        # Salvar relatórios
        if output_path:
            output_path = Path(output_path)
            output_path.mkdir(parents=True, exist_ok=True)

            if not excessive_conc.empty:
                file1 = output_path / 'excessive_concentration.csv'
                excessive_conc.to_csv(file1, index=False)
                print(f"💾 Excessive concentration: {file1}")

            if not related_party.empty:
                file2 = output_path / 'related_party_concentration.csv'
                related_party.to_csv(file2, index=False)
                print(f"💾 Related party concentration: {file2}")

        # Resumo
        print("\n" + "="*60)
        print("📋 RESUMO")
        print("="*60)

        print(f"\n⚠️  Fundos com concentração excessiva: {len(excessive_conc)}")
        print(f"🚨 Fundos com concentração em partes relacionadas: {len(related_party)}")

        if not excessive_conc.empty:
            print("\n🔝 Top 5 por concentração:")
            top5 = excessive_conc.head(5)[['CNPJ_FUNDO', 'top1_pct', 'hhi', 'severity']]
            print(top5.to_string(index=False))

        if not related_party.empty:
            print("\n🔴 Concentração em partes relacionadas:")
            print(related_party[['CNPJ_FUNDO', 'related_party_pct', 'num_related_positions']].to_string(index=False))

        return {
            'excessive_concentration': excessive_conc,
            'related_party_concentration': related_party
        }
