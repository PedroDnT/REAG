"""
Phantom Assets Detector - Identifica ativos fictícios

Este módulo detecta ativos que não existem em registros oficiais,
uma das evidências mais diretas de fraude.
"""

import pandas as pd
import requests
from typing import Set, Dict, List, Optional
from pathlib import Path
import json


class PhantomAssetDetector:
    """
    Detecta ativos fictícios em carteiras de fundos

    Verifica se ativos declarados no CDA existem em:
    - B3 (ações, ETFs, BDRs)
    - ANBIMA (títulos públicos e privados)
    - CVM (fundos de investimento)
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Args:
            cache_dir: Diretório para cache de registros oficiais
        """
        self.cache_dir = cache_dir or Path('data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Registros de ativos válidos
        self.valid_stocks: Set[str] = set()
        self.valid_etfs: Set[str] = set()
        self.valid_bdrs: Set[str] = set()
        self.valid_funds: Set[str] = set()

        # Inicializar registros
        self._load_registries()

    def _load_registries(self):
        """Carrega registros de ativos válidos"""
        # Tentar carregar do cache
        cache_file = self.cache_dir / 'asset_registries.json'

        if cache_file.exists():
            print("📂 Carregando registros do cache...")
            with open(cache_file, 'r') as f:
                data = json.load(f)
                self.valid_stocks = set(data.get('stocks', []))
                self.valid_etfs = set(data.get('etfs', []))
                self.valid_bdrs = set(data.get('bdrs', []))
                self.valid_funds = set(data.get('funds', []))
            print(f"✅ Carregados: {len(self.valid_stocks)} ações, "
                  f"{len(self.valid_etfs)} ETFs, {len(self.valid_bdrs)} BDRs")
        else:
            print("⚠️ Cache não encontrado. Use update_registries() para baixar.")

    def update_registries(self):
        """
        Atualiza registros de ativos válidos da B3

        Nota: Esta implementação usa uma lista estática.
        Para produção, integrar com API da B3 ou scraping.
        """
        print("🔄 Atualizando registros de ativos...")

        # Lista de ações mais negociadas (exemplo - em produção, usar API B3)
        common_stocks = {
            'PETR3', 'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'B3SA3', 'BBAS3', 'WEGE3', 'RENT3', 'SUZB3', 'RAIL3',
            'JBSS3', 'MGLU3', 'VIIA3', 'GGBR4', 'USIM5', 'CSNA3',
            'EMBR3', 'TOTS3', 'KLBN11', 'CYRE3', 'RADL3', 'HAPV3',
            'LREN3', 'AZUL4', 'GOAU4', 'ELET3', 'ELET6', 'CMIG4',
            'CSAN3', 'EQTL3', 'ENBR3', 'TAEE11', 'BRFS3', 'BEEF3',
            'MRFG3', 'PCAR3', 'CIEL3', 'COGN3', 'YDUQ3', 'SULA11',
            'NTCO3', 'VBBR3', 'SANB11', 'BPAC11', 'PRIO3', 'UGPA3',
            'CCRO3', 'ECOR3', 'MULT3', 'IRBR3', 'PSSA3', 'CPLE6'
        }

        common_etfs = {
            'BOVA11', 'SMAL11', 'IVVB11', 'PIBB11', 'FIND11',
            'DIVO11', 'ISUS11', 'SPXI11', 'MATB11', 'HASH11'
        }

        common_bdrs = {
            'AAPL34', 'MSFT34', 'GOOGL34', 'AMZO34', 'TSLA34',
            'NVDC34', 'META34', 'NFLX34', 'DISB34', 'COCA34'
        }

        self.valid_stocks = common_stocks
        self.valid_etfs = common_etfs
        self.valid_bdrs = common_bdrs

        # Salvar cache
        cache_file = self.cache_dir / 'asset_registries.json'
        with open(cache_file, 'w') as f:
            json.dump({
                'stocks': list(self.valid_stocks),
                'etfs': list(self.valid_etfs),
                'bdrs': list(self.valid_bdrs),
                'funds': list(self.valid_funds)
            }, f, indent=2)

        print(f"✅ Registros atualizados: {len(self.valid_stocks)} ações")
        print(f"💾 Cache salvo em: {cache_file}")

    def load_funds_from_cadastro(self, cadastro_path: Path):
        """
        Carrega lista de fundos válidos do cadastro CVM

        Args:
            cadastro_path: Caminho para cad_fi.csv
        """
        print(f"📥 Carregando fundos do cadastro...")

        # Only read the required column for better performance
        df = pd.read_csv(cadastro_path, encoding='latin1', sep=';', usecols=['CNPJ_FUNDO'])

        # Extrair CNPJs de fundos ativos
        if 'CNPJ_FUNDO' in df.columns:
            self.valid_funds = set(df['CNPJ_FUNDO'].dropna().astype(str))
            print(f"✅ {len(self.valid_funds):,} fundos carregados")
        else:
            print("⚠️ Coluna CNPJ_FUNDO não encontrada")

    def classify_asset_type(self, asset_code: str) -> str:
        """
        Classifica tipo de ativo pelo código

        Args:
            asset_code: Código do ativo

        Returns:
            Tipo: 'STOCK', 'ETF', 'BDR', 'FUND', 'BOND', 'OTHER'
        """
        asset_code = str(asset_code).strip().upper()

        # ETF: geralmente termina em 11
        if asset_code.endswith('11'):
            return 'ETF'

        # BDR: geralmente termina em 34
        if asset_code.endswith('34'):
            return 'BDR'

        # Ação: termina em 3, 4, 5, 6, etc
        if asset_code and asset_code[-1].isdigit():
            return 'STOCK'

        # CNPJ (fundo): 14 dígitos
        if len(asset_code.replace('.', '').replace('/', '').replace('-', '')) == 14:
            return 'FUND'

        # Debênture/CRI/CRA: geralmente contém código específico
        if any(x in asset_code for x in ['DEB', 'CRI', 'CRA', 'CDB']):
            return 'BOND'

        return 'OTHER'

    def validate_asset(self, asset_code: str, asset_type: str = None) -> Dict:
        """
        Valida se ativo existe em registros oficiais

        Args:
            asset_code: Código do ativo
            asset_type: Tipo do ativo (opcional, será inferido se não fornecido)

        Returns:
            Dict com resultado da validação
        """
        if asset_type is None:
            asset_type = self.classify_asset_type(asset_code)

        asset_code = str(asset_code).strip().upper()

        is_valid = False
        registry = None

        if asset_type == 'STOCK':
            is_valid = asset_code in self.valid_stocks
            registry = 'B3_STOCKS'
        elif asset_type == 'ETF':
            is_valid = asset_code in self.valid_etfs
            registry = 'B3_ETFS'
        elif asset_type == 'BDR':
            is_valid = asset_code in self.valid_bdrs
            registry = 'B3_BDRS'
        elif asset_type == 'FUND':
            is_valid = asset_code in self.valid_funds
            registry = 'CVM_FUNDS'
        elif asset_type == 'BOND':
            # Bonds requerem validação mais complexa
            # Por ora, marcar como "não validável"
            is_valid = None  # Unknown
            registry = 'ANBIMA_BONDS'

        return {
            'asset_code': asset_code,
            'asset_type': asset_type,
            'is_valid': is_valid,
            'registry': registry,
            'status': 'VALID' if is_valid else ('UNKNOWN' if is_valid is None else 'PHANTOM')
        }

    def detect_phantom_assets(self, cda_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta ativos fantasma no CDA

        Args:
            cda_df: DataFrame do CDA com coluna CD_ATIVO

        Returns:
            DataFrame com ativos fantasma e detalhes
        """
        print("🔍 Detectando ativos fantasma...")

        if 'CD_ATIVO' not in cda_df.columns:
            raise ValueError("DataFrame deve conter coluna 'CD_ATIVO'")

        phantom_assets = []

        unique_assets = cda_df['CD_ATIVO'].unique()
        print(f"📊 Analisando {len(unique_assets):,} ativos únicos...")

        # Pre-group by asset code to avoid repeated scans (much faster)
        # Build aggregation dict based on available columns
        agg_dict = {}
        has_vl_mercado = 'VL_MERCADO' in cda_df.columns
        has_cnpj_fundo = 'CNPJ_FUNDO' in cda_df.columns
        has_dt_comptc = 'DT_COMPTC' in cda_df.columns
        
        if has_vl_mercado:
            agg_dict['VL_MERCADO'] = 'sum'
        if has_cnpj_fundo:
            agg_dict['CNPJ_FUNDO'] = 'nunique'
        if has_dt_comptc:
            agg_dict['DT_COMPTC'] = ['min', 'max']
        
        # Only group if we have columns to aggregate
        if agg_dict:
            asset_groups = cda_df.groupby('CD_ATIVO').agg(agg_dict)
        else:
            asset_groups = pd.DataFrame()

        for asset_code in unique_assets:
            validation = self.validate_asset(asset_code)

            if validation['status'] == 'PHANTOM':
                # Use pre-grouped data instead of scanning entire DataFrame
                if not asset_groups.empty and asset_code in asset_groups.index:
                    asset_info = asset_groups.loc[asset_code]
                    total_value = asset_info['VL_MERCADO'] if has_vl_mercado else 0
                    num_funds = asset_info['CNPJ_FUNDO'] if has_cnpj_fundo else 0
                    if has_dt_comptc:
                        first_seen = asset_info[('DT_COMPTC', 'min')]
                        last_seen = asset_info[('DT_COMPTC', 'max')]
                    else:
                        first_seen = None
                        last_seen = None
                else:
                    total_value = 0
                    num_funds = 0
                    first_seen = None
                    last_seen = None

                phantom_assets.append({
                    'asset_code': asset_code,
                    'asset_type': validation['asset_type'],
                    'expected_registry': validation['registry'],
                    'total_value': total_value,
                    'num_funds_holding': num_funds,
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'fraud_severity': 'CRITICAL'
                })

        result_df = pd.DataFrame(phantom_assets)

        if not result_df.empty:
            result_df = result_df.sort_values('total_value', ascending=False)

        print(f"\n⚠️ {len(phantom_assets)} ativos fantasma detectados!")

        return result_df

    def generate_phantom_report(self, cda_df: pd.DataFrame,
                               output_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Gera relatório completo de ativos fantasma

        Args:
            cda_df: DataFrame do CDA
            output_path: Caminho para salvar relatório (opcional)

        Returns:
            DataFrame com relatório
        """
        phantoms = self.detect_phantom_assets(cda_df)

        if output_path and not phantoms.empty:
            phantoms.to_csv(output_path, index=False)
            print(f"💾 Relatório salvo em: {output_path}")

        # Imprimir resumo
        if not phantoms.empty:
            print("\n" + "="*60)
            print("📋 RESUMO DE ATIVOS FANTASMA")
            print("="*60)

            print(f"\n🚨 Total de ativos fantasma: {len(phantoms)}")
            print(f"💰 Valor total: R$ {phantoms['total_value'].sum():,.2f}")
            print(f"🏦 Fundos afetados: {phantoms['num_funds_holding'].sum()}")

            print("\n🔝 Top 5 por valor:")
            top5 = phantoms.head(5)[['asset_code', 'asset_type', 'total_value', 'num_funds_holding']]
            print(top5.to_string(index=False))

            print("\n📊 Por tipo de ativo:")
            by_type = phantoms.groupby('asset_type').agg({
                'asset_code': 'count',
                'total_value': 'sum'
            }).rename(columns={'asset_code': 'count'})
            print(by_type)
        else:
            print("\n✅ Nenhum ativo fantasma detectado!")

        return phantoms
