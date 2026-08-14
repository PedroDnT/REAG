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
                'BANCO MASTER',
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
        digits = re.sub(r"\D", "", asset_code)

        # A 14-digit identifier is a fund CNPJ. Check this before ticker suffix
        # heuristics: thousands of valid fund CNPJs end in 11 or 34 and were
        # previously misclassified as ETFs/BDRs.
        if len(digits) == 14:
            return {
                'type': 'FUND',
                'should_be_public': True,
                'validation_method': 'CVM_REGISTRY',
                'confidence': 'HIGH',
                'liquidity_expectation': 'MEDIUM'
            }

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

            if self._issuer_matches_any(issuer, self.suspicious_patterns['circular_flow_indicators']):
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

    def _issuer_matches_any(self, issuer: str, patterns: list[str]) -> bool:
        """Match known-scheme tokens as whole words, not substrings.

        ``MASTER`` used to fire on every 'BlackRock Master' feeder, and
        ``BRAVO`` on Rio Bravo CRIs.
        """
        text = issuer.upper()
        return any(
            re.search(rf"(?<![A-Z0-9]){re.escape(pattern.upper())}(?![A-Z0-9])", text)
            for pattern in patterns
        )

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
        if classification['should_be_public'] is True:
            is_valid = False
            registry_complete = False

            if classification['type'] == 'STOCK':
                is_valid = asset_code in self.valid_stocks
            elif classification['type'] == 'ETF':
                is_valid = asset_code in self.valid_etfs
            elif classification['type'] == 'BDR':
                is_valid = asset_code in self.valid_bdrs
            elif classification['type'] == 'FUND':
                normalized = re.sub(r"\D", "", str(asset_code))
                is_valid = normalized in self.valid_funds
                registry_complete = bool(self.valid_funds)

            if is_valid:
                result.update({
                    'is_valid': True,
                    'status': 'VALID',
                    'confidence': 'HIGH',
                    'fraud_risk': 'NONE',
                    'reason': 'Found in registry'
                })
            else:
                # A cache miss is not positive evidence that an asset is
                # fictitious. The bundled B3 lists are deliberately incomplete,
                # and even the CVM cadastro is a current snapshot.
                result.update({
                    'is_valid': None,
                    'status': 'NEEDS_VERIFICATION',
                    'confidence': 'LOW' if not registry_complete else 'MEDIUM',
                    'fraud_risk': 'LOW',
                    'reason': 'Not found in the available registry snapshot'
                })

        # Validação para ativos PRIVADOS
        elif classification['should_be_public'] is False:
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
        # Posicoes sem codigo de ativo nao sao analisaveis por ativo, e um NA
        # aqui e pior que inutil: `cda_df['CD_ATIVO'] == NA` nao casa com nada,
        # entao o .iloc[0] abaixo estourava IndexError.
        coded = cda_df[cda_df['CD_ATIVO'].notna()]
        logger.info(f"Analisando {coded['CD_ATIVO'].nunique():,} ativos unicos...")

        # Uma passagem agrupada, nao duas varreduras por ativo. O laco anterior
        # filtrava o frame inteiro duas vezes para cada codigo distinto: com
        # 152 mil ativos sobre 582 mil linhas isso e da ordem de 88 bilhoes de
        # comparacoes, e um mes completo da CVM simplesmente nunca terminava.
        # drop_duplicates(keep='first') reproduz exatamente o .iloc[0] antigo.
        first_rows = coded.drop_duplicates(subset='CD_ATIVO', keep='first').set_index('CD_ATIVO')
        grouped = coded.groupby('CD_ATIVO', sort=False)
        totals = (grouped['VL_MERCADO'].sum() if 'VL_MERCADO' in coded.columns
                  else pd.Series(dtype=float))
        holders = (grouped['CNPJ_FUNDO'].nunique() if 'CNPJ_FUNDO' in coded.columns
                   else pd.Series(dtype=int))

        for asset_code, row in first_rows.iterrows():
            asset_data = row.to_dict()
            asset_data['CD_ATIVO'] = asset_code

            # Validar
            validation = self.enhanced_validate_asset(asset_code, asset_data)

            if not self._should_report_asset(validation):
                continue

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
                'total_value': float(totals.get(asset_code, 0) or 0),
                'num_funds_holding': int(holders.get(asset_code, 0) or 0),
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

    def _should_report_asset(self, validation: dict) -> bool:
        """Persist leads, including fund-registry misses, but not cache noise."""
        if validation.get("status") == "VALID" or validation.get("fraud_risk") == "NONE":
            return False
        if validation.get("status") == "NEEDS_VERIFICATION":
            return validation.get("asset_type") == "FUND" and bool(self.valid_funds)
        return validation.get("fraud_risk") in ("HIGH", "CRITICAL")

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
            self.valid_funds = {
                re.sub(r"\D", "", value)
                for value in df['CNPJ_FUNDO'].dropna().astype(str)
                if len(re.sub(r"\D", "", value)) == 14
            }
            logger.info(f"{len(self.valid_funds):,} fundos carregados")
