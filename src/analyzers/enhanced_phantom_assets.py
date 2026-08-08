"""
Enhanced Phantom Assets Detector with Private Asset Handling

This module distinguishes between:
1. Public assets (stocks, ETFs) - SHOULD be in registries
2. Private assets (debentures, CRI, CRA) - May not be in public registries
3. Truly fictitious assets - Don't exist anywhere

Based on research of Banco Master/REAG fraud scheme.
"""

import logging

import pandas as pd
from typing import Any
from pathlib import Path
import json
import re

logger = logging.getLogger(__name__)


class EnhancedPhantomAssetDetector:
    """
    Enhanced detector that handles private/illiquid assets properly

    Key Distinctions:
    - PUBLIC assets (stocks, ETFs, BDRs): MUST exist in B3
    - PRIVATE assets (debêntures, CRI, CRA, CDB): May be legitimate even if not in public registries
    - FICTITIOUS assets: Claims about assets that cannot be verified anywhere
    """

    def __init__(self, cache_dir: Path | None = None):
        """
        Args:
            cache_dir: Diretório para cache de registros oficiais
        """
        self.cache_dir = cache_dir or Path('data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Registros de ativos públicos válidos
        self.valid_stocks: set[str] = set()
        self.valid_etfs: set[str] = set()
        self.valid_bdrs: set[str] = set()
        self.valid_funds: set[str] = set()

        # Registros de emissores conhecidos (para validação de privados)
        self.known_issuers: set[str] = set()

        # Patterns suspeitos (baseado em fraudes reais)
        self.suspicious_patterns = self._load_fraud_patterns()

        # Inicializar registros
        self._load_registries()

    def _load_fraud_patterns(self) -> dict[str, list[str]]:
        """
        Carrega padrões de fraude conhecidos baseados em casos reais

        Baseado em: Banco Master/REAG, Madoff, etc.
        """
        return {
            'shell_company_indicators': [
                'LTDA ME',  # Micro-empresa (muitas vezes shell)
                'EIRELI',  # Empresa Individual (fácil criar shell)
                'FICTICIA',
                'FANTASMA',
                'TESTE',
                'EXEMPLO'
            ],
            'suspicious_issuers': [
                'EMPRESA NAO IDENTIFICADA',
                'EMISSOR DESCONHECIDO',
                'SEM REGISTRO',
                'PRIVADO NAO REGISTRADO'
            ],
            'circular_flow_indicators': [
                'MASTER',  # Banco Master
                'REAG',
                'CBSF',
                'D MAIS',  # Fundos do esquema
                'BRAVO'
            ]
        }

    def classify_asset_type(self, asset_code: str) -> dict[str, Any]:
        """
        Classifica tipo de ativo e determina método de validação

        Returns:
            Dict com: type, should_be_public, validation_method, confidence
        """
        asset_code = str(asset_code).strip().upper()

        # Ações (públicas - DEVEM estar na B3)
        if re.match(r'^[A-Z]{4}[3-8]$', asset_code):
            return {
                'type': 'STOCK',
                'should_be_public': True,
                'validation_method': 'B3_REGISTRY',
                'confidence': 'HIGH',
                'liquidity_expectation': 'HIGH'
            }

        # ETFs (públicos - DEVEM estar na B3)
        if asset_code.endswith('11'):
            return {
                'type': 'ETF',
                'should_be_public': True,
                'validation_method': 'B3_REGISTRY',
                'confidence': 'HIGH',
                'liquidity_expectation': 'HIGH'
            }

        # BDRs (públicos - DEVEM estar na B3)
        if asset_code.endswith('34'):
            return {
                'type': 'BDR',
                'should_be_public': True,
                'validation_method': 'B3_REGISTRY',
                'confidence': 'HIGH',
                'liquidity_expectation': 'MEDIUM'
            }

        # Debêntures (privadas - podem não estar em registro público)
        if 'DEB' in asset_code or 'DEBENTURE' in asset_code:
            return {
                'type': 'DEBENTURE',
                'should_be_public': False,
                'validation_method': 'ISSUER_CHECK',
                'confidence': 'MEDIUM',
                'liquidity_expectation': 'LOW'
            }

        # CRI (privado - ilíquido)
        if 'CRI' in asset_code:
            return {
                'type': 'CRI',
                'should_be_public': False,
                'validation_method': 'ISSUER_CHECK',
                'confidence': 'MEDIUM',
                'liquidity_expectation': 'VERY_LOW'
            }

        # CRA (privado - ilíquido)
        if 'CRA' in asset_code:
            return {
                'type': 'CRA',
                'should_be_public': False,
                'validation_method': 'ISSUER_CHECK',
                'confidence': 'MEDIUM',
                'liquidity_expectation': 'VERY_LOW'
            }

        # CDB (privado)
        if 'CDB' in asset_code:
            return {
                'type': 'CDB',
                'should_be_public': False,
                'validation_method': 'ISSUER_CHECK',
                'confidence': 'MEDIUM',
                'liquidity_expectation': 'LOW'
            }

        # CNPJ (fundo de investimento)
        if len(asset_code.replace('.', '').replace('/', '').replace('-', '')) == 14:
            return {
                'type': 'FUND',
                'should_be_public': True,
                'validation_method': 'CVM_REGISTRY',
                'confidence': 'HIGH',
                'liquidity_expectation': 'MEDIUM'
            }

        # Desconhecido
        return {
            'type': 'UNKNOWN',
            'should_be_public': None,
            'validation_method': 'MANUAL_REVIEW',
            'confidence': 'VERY_LOW',
            'liquidity_expectation': 'UNKNOWN'
        }

    def validate_private_asset(self, asset_code: str, asset_info: dict) -> dict:
        """
        Valida ativos privados (debêntures, CRI, CRA, CDB)

        Para ativos privados, não podemos dizer que são "phantom" apenas
        por não estarem em registros públicos. Precisamos verificar:
        1. Emissor existe?
        2. Padrões suspeitos?
        3. Valores razoáveis?
        """
        # Extrair emissor do código ou descrição
        issuer = self._extract_issuer(asset_code, asset_info)

        red_flags = []
        confidence = 'MEDIUM'

        # Red Flag 1: Emissor desconhecido ou suspeito
        if issuer:
            if any(pattern in issuer.upper() for pattern in self.suspicious_patterns['suspicious_issuers']):
                red_flags.append('SUSPICIOUS_ISSUER_NAME')
                confidence = 'HIGH'

            if any(pattern in issuer.upper() for pattern in self.suspicious_patterns['shell_company_indicators']):
                red_flags.append('POSSIBLE_SHELL_COMPANY')
                confidence = 'HIGH'

            if any(pattern in issuer.upper() for pattern in self.suspicious_patterns['circular_flow_indicators']):
                red_flags.append('CIRCULAR_FLOW_ENTITY')
                confidence = 'CRITICAL'
        else:
            red_flags.append('NO_ISSUER_IDENTIFIED')
            confidence = 'HIGH'

        # Red Flag 2: Valor irrealisticamente alto para ativo ilíquido
        if 'VL_MERCADO' in asset_info and asset_info['VL_MERCADO'] > 100_000_000:  # > R$ 100M
            if asset_info.get('liquidity_expectation') == 'VERY_LOW':
                red_flags.append('LARGE_ILLIQUID_POSITION')
                confidence = 'MEDIUM'

        return {
            'is_valid': len(red_flags) == 0,
            'confidence': confidence,
            'issuer': issuer,
            'red_flags': red_flags,
            'validation_status': 'NEEDS_MANUAL_REVIEW' if red_flags else 'LIKELY_LEGITIMATE',
            'fraud_risk': 'HIGH' if confidence in ['HIGH', 'CRITICAL'] else 'MEDIUM'
        }

    def _extract_issuer(self, asset_code: str, asset_info: dict) -> str | None:
        """
        Extrai nome do emissor do código ou informações do ativo
        """
        # Tentar pegar da coluna EMISSOR se disponível
        if 'EMISSOR' in asset_info and asset_info['EMISSOR']:
            return str(asset_info['EMISSOR']).strip()

        # Tentar extrair do código
        # Exemplo: "DEB_PETROBRAS_2025" -> "PETROBRAS"
        parts = asset_code.split('_')
        if len(parts) > 1:
            return parts[1]

        return None

    def enhanced_validate_asset(self, asset_code: str, asset_info: dict = None) -> dict:
        """
        Validação aprimorada que distingue ativos públicos vs privados

        Args:
            asset_code: Código do ativo
            asset_info: Informações adicionais (opcional)

        Returns:
            Dict com resultado detalhado
        """
        if asset_info is None:
            asset_info = {}

        # Classificar ativo
        classification = self.classify_asset_type(asset_code)

        result = {
            'asset_code': asset_code,
            'asset_type': classification['type'],
            'should_be_public': classification['should_be_public'],
            'validation_method': classification['validation_method'],
            'liquidity_expectation': classification['liquidity_expectation']
        }

        # Validação para ativos PÚBLICOS
        if classification['should_be_public']:
            is_valid = False

            if classification['type'] == 'STOCK':
                is_valid = asset_code in self.valid_stocks
            elif classification['type'] == 'ETF':
                is_valid = asset_code in self.valid_etfs
            elif classification['type'] == 'BDR':
                is_valid = asset_code in self.valid_bdrs
            elif classification['type'] == 'FUND':
                is_valid = asset_code in self.valid_funds

            result.update({
                'is_valid': is_valid,
                'status': 'VALID' if is_valid else 'PHANTOM',
                'confidence': 'HIGH',
                'fraud_risk': 'CRITICAL' if not is_valid else 'NONE',
                'reason': 'Not found in public registry' if not is_valid else 'Found in registry'
            })

        # Validação para ativos PRIVADOS
        elif not classification['should_be_public']:
            private_validation = self.validate_private_asset(asset_code, asset_info)

            result.update({
                'is_valid': private_validation['is_valid'],
                'status': private_validation['validation_status'],
                'confidence': private_validation['confidence'],
                'fraud_risk': private_validation['fraud_risk'],
                'issuer': private_validation.get('issuer'),
                'red_flags': private_validation.get('red_flags', []),
                'reason': 'Private asset - requires manual verification'
            })

        # Desconhecido
        else:
            result.update({
                'is_valid': None,
                'status': 'UNKNOWN',
                'confidence': 'VERY_LOW',
                'fraud_risk': 'MEDIUM',
                'reason': 'Asset type cannot be determined'
            })

        return result

    def detect_enhanced_phantom_assets(self, cda_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta ativos com diferentes níveis de suspeita

        Returns:
            DataFrame com categorias:
            - PHANTOM (públicos que não existem)
            - SUSPICIOUS_PRIVATE (privados com red flags)
            - NEEDS_REVIEW (privados que precisam verificação manual)
        """
        logger.info("Detectando ativos suspeitos (enhanced)...")

        if 'CD_ATIVO' not in cda_df.columns:
            raise ValueError("DataFrame deve conter coluna 'CD_ATIVO'")

        results = []
        unique_assets = cda_df['CD_ATIVO'].unique()

        logger.info(f"Analisando {len(unique_assets):,} ativos unicos...")

        for asset_code in unique_assets:
            # Pegar informações adicionais
            asset_data = cda_df[cda_df['CD_ATIVO'] == asset_code].iloc[0].to_dict()

            # Validar
            validation = self.enhanced_validate_asset(asset_code, asset_data)

            # Categorizar por risco
            if validation['fraud_risk'] in ['CRITICAL', 'HIGH']:
                # Agregar informações
                holdings = cda_df[cda_df['CD_ATIVO'] == asset_code]

                results.append({
                    'asset_code': asset_code,
                    'asset_type': validation['asset_type'],
                    'status': validation['status'],
                    'fraud_risk': validation['fraud_risk'],
                    'confidence': validation['confidence'],
                    'liquidity_expectation': validation['liquidity_expectation'],
                    'issuer': validation.get('issuer'),
                    'red_flags': ', '.join(validation.get('red_flags', [])),
                    'reason': validation['reason'],
                    'total_value': holdings['VL_MERCADO'].sum() if 'VL_MERCADO' in holdings.columns else 0,
                    'num_funds_holding': holdings['CNPJ_FUNDO'].nunique() if 'CNPJ_FUNDO' in holdings.columns else 0,
                    'validation_method': validation['validation_method']
                })

        result_df = pd.DataFrame(results)

        if not result_df.empty:
            result_df = result_df.sort_values('fraud_risk', ascending=False)

        logger.warning(f"{len(result_df)} ativos suspeitos detectados!")

        # Breakdown por categoria
        if not result_df.empty:
            logger.info(f"Breakdown por tipo de risco:\n{result_df['fraud_risk'].value_counts()}")
            logger.info(f"Breakdown por status:\n{result_df['status'].value_counts()}")

        return result_df

    def _load_registries(self):
        """Carrega registros (mantido para compatibilidade)"""
        cache_file = self.cache_dir / 'asset_registries.json'
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                self.valid_stocks = set(data.get('stocks', []))
                self.valid_etfs = set(data.get('etfs', []))
                self.valid_bdrs = set(data.get('bdrs', []))
                self.valid_funds = set(data.get('funds', []))

    def update_registries(self):
        """Atualiza registros (simplificado para exemplo)"""
        # Lista expandida de ações
        common_stocks = {
            'PETR3', 'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'B3SA3', 'BBAS3', 'WEGE3', 'RENT3', 'SUZB3', 'RAIL3',
            'JBSS3', 'MGLU3', 'VIIA3', 'GGBR4', 'USIM5', 'CSNA3',
            # Adicionar mais conforme necessário
        }
        self.valid_stocks = common_stocks

        cache_file = self.cache_dir / 'asset_registries.json'
        with open(cache_file, 'w') as f:
            json.dump({
                'stocks': list(self.valid_stocks),
                'etfs': list(self.valid_etfs),
                'bdrs': list(self.valid_bdrs),
                'funds': list(self.valid_funds)
            }, f, indent=2)

    def load_funds_from_cadastro(self, cadastro_path: Path):
        """Carrega fundos do cadastro CVM"""
        df = pd.read_csv(cadastro_path, encoding='latin1', sep=';')
        if 'CNPJ_FUNDO' in df.columns:
            self.valid_funds = set(df['CNPJ_FUNDO'].dropna().astype(str))
            logger.info(f"{len(self.valid_funds):,} fundos carregados")
