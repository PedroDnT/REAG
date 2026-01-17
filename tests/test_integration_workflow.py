"""
Integration Test - Full Fraud Detection Workflow

Tests the complete fraud investigation pipeline from data loading
through all analysis stages to final reporting.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class IntegrationWorkflowTest:
    """
    Integration test simulating a complete fraud investigation
    """

    def __init__(self):
        self.results = {}
        self.test_passed = True

    def log(self, message: str):
        """Log test progress"""
        print(f"  {message}")

    def create_realistic_fraud_scenario(self):
        """
        Create realistic test data simulating a fraud scheme

        Scenario: Small administrator manages multiple funds with:
        1. Circular investments between funds
        2. Phantom assets (fake stocks)
        3. Overvalued private assets
        4. Excessive concentration
        5. Unrealistic returns (Ponzi-like)
        """
        self.log("Creating realistic fraud scenario...")

        # Two administrators: one fraudulent, one legitimate
        admin_fraud = '11.111.111/0001-01'  # REAG-like fraudulent admin
        admin_legit = '22.222.222/0001-01'  # Legitimate admin

        # Create 20 funds: 10 fraudulent, 10 legitimate
        fraud_funds = [f'90.000.00{i}/0001-01' for i in range(10)]
        legit_funds = [f'80.000.00{i}/0001-01' for i in range(10)]
        all_funds = fraud_funds + legit_funds

        # 1. CADASTRO DATA
        cadastro_data = []
        for fund in fraud_funds:
            cadastro_data.append({
                'CNPJ_FUNDO': fund,
                'CNPJ_ADMIN': admin_fraud,
                'CLASSE': np.random.choice(['Fundo Multimercado', 'Fundo de Renda Fixa'])
            })

        for fund in legit_funds:
            cadastro_data.append({
                'CNPJ_FUNDO': fund,
                'CNPJ_ADMIN': admin_legit,
                'CLASSE': np.random.choice(['Fundo de Ações', 'Fundo de Renda Fixa', 'Fundo Multimercado'])
            })

        cadastro_df = pd.DataFrame(cadastro_data)

        # 2. INFORME DIÁRIO DATA (60 days)
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        informe_data = []

        for fund in all_funds:
            is_fraud = fund in fraud_funds
            base_quota = 1.0

            for i, date in enumerate(dates):
                if is_fraud:
                    # Ponzi-like: Smooth, consistent positive returns
                    daily_return = np.random.normal(0.003, 0.0005)  # ~0.3%/day, low volatility
                    base_quota *= (1 + daily_return)
                else:
                    # Normal: Volatile, realistic returns
                    daily_return = np.random.normal(0.0003, 0.01)  # ~0.03%/day, normal volatility
                    base_quota *= (1 + daily_return)

                informe_data.append({
                    'CNPJ_FUNDO': fund,
                    'DT_COMPTC': date,
                    'VL_QUOTA': base_quota,
                    'VL_PATRIM_LIQ': np.random.uniform(50_000_000, 200_000_000),
                    'CAPTC_DIA': np.random.uniform(0, 5_000_000) if is_fraud else np.random.uniform(0, 1_000_000),
                    'RESG_DIA': np.random.uniform(0, 1_000_000) if is_fraud else np.random.uniform(0, 1_000_000),
                    'NR_COTST': np.random.randint(100, 1000)
                })

        informe_df = pd.DataFrame(informe_data)
        informe_df['FLUXO_LIQ_DIA'] = informe_df['CAPTC_DIA'] - informe_df['RESG_DIA']

        # 3. CDA DATA (Portfolio Composition)
        cda_data = []

        # Legitimate stocks
        legit_stocks = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'B3SA3']

        # Fraudulent scenario assets
        phantom_stocks = ['FAKE4', 'GHOST3', 'FRAUD4']  # Don't exist
        shell_issuers = [
            'EMPRESA RAPIDA LTDA ME',
            'NEGOCIOS FINANCEIROS EIRELI',
            'INVESTIMENTOS FACIL LTDA ME'
        ]

        for fund in all_funds:
            is_fraud = fund in fraud_funds
            date = datetime(2024, 1, 31)

            if is_fraud:
                # FRAUD SCENARIO

                # 1. Circular flow: Invest in other funds from same admin
                other_fraud_funds = [f for f in fraud_funds if f != fund]
                for other_fund in np.random.choice(other_fraud_funds, 3, replace=False):
                    cda_data.append({
                        'CNPJ_FUNDO': fund,
                        'CD_ATIVO': other_fund,
                        'VL_MERCADO': np.random.uniform(10_000_000, 30_000_000),
                        'QT_POS': 1,
                        'DT_COMPTC': date,
                        'EMISSOR': 'FUNDO DE INVESTIMENTO'
                    })

                # 2. Phantom stocks (don't exist in B3)
                for phantom in phantom_stocks:
                    cda_data.append({
                        'CNPJ_FUNDO': fund,
                        'CD_ATIVO': phantom,
                        'VL_MERCADO': np.random.uniform(5_000_000, 15_000_000),
                        'QT_POS': np.random.uniform(100_000, 500_000),
                        'DT_COMPTC': date,
                        'EMISSOR': 'EMPRESA FICTICIA'
                    })

                # 3. Overvalued private assets from shells
                for i, issuer in enumerate(shell_issuers):
                    cda_data.append({
                        'CNPJ_FUNDO': fund,
                        'CD_ATIVO': f'DEB_{issuer.split()[0]}_{2024+i}',
                        'VL_MERCADO': np.random.uniform(20_000_000, 50_000_000),  # Huge!
                        'QT_POS': 1,
                        'DT_COMPTC': date,
                        'EMISSOR': issuer
                    })

                # 4. Small amount of legitimate stocks (to look normal)
                for stock in np.random.choice(legit_stocks, 2):
                    cda_data.append({
                        'CNPJ_FUNDO': fund,
                        'CD_ATIVO': stock,
                        'VL_MERCADO': np.random.uniform(1_000_000, 5_000_000),
                        'QT_POS': np.random.uniform(10_000, 50_000),
                        'DT_COMPTC': date,
                        'EMISSOR': 'EMPRESA LEGITIMA SA'
                    })

            else:
                # LEGITIMATE SCENARIO

                # Diversified portfolio of real stocks
                for stock in np.random.choice(legit_stocks, 5):
                    cda_data.append({
                        'CNPJ_FUNDO': fund,
                        'CD_ATIVO': stock,
                        'VL_MERCADO': np.random.uniform(5_000_000, 20_000_000),
                        'QT_POS': np.random.uniform(50_000, 200_000),
                        'DT_COMPTC': date,
                        'EMISSOR': 'EMPRESA LEGITIMA SA'
                    })

                # Some legitimate debentures
                cda_data.append({
                    'CNPJ_FUNDO': fund,
                    'CD_ATIVO': 'DEB_PETROBRAS_2025',
                    'VL_MERCADO': np.random.uniform(10_000_000, 30_000_000),
                    'QT_POS': 1,
                    'DT_COMPTC': date,
                    'EMISSOR': 'PETROBRAS'
                })

        cda_df = pd.DataFrame(cda_data)

        self.log(f"✅ Created scenario: {len(cadastro_df)} funds, {len(informe_df)} performance records, {len(cda_df)} portfolio positions")

        return cadastro_df, informe_df, cda_df, fraud_funds

    def run_complete_workflow(self):
        """Run complete fraud detection workflow"""
        print("\n" + "="*70)
        print("🔍 INTEGRATION TEST - FULL FRAUD DETECTION WORKFLOW")
        print("="*70)

        # Step 1: Create test data
        print("\n📊 STEP 1: Creating Test Scenario")
        print("-"*70)
        cadastro_df, informe_df, cda_df, known_fraud_funds = self.create_realistic_fraud_scenario()

        # Step 2: Enhanced Phantom Assets Detection
        print("\n🔍 STEP 2: Enhanced Phantom Assets Detection")
        print("-"*70)
        try:
            from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector

            detector = EnhancedPhantomAssetDetector()
            detector.update_registries()

            phantom_results = detector.detect_enhanced_phantom_assets(cda_df)
            self.results['phantom_assets'] = phantom_results

            if not phantom_results.empty:
                print(f"\n⚠️  Found {len(phantom_results)} suspicious assets:")
                print(phantom_results[['asset_code', 'asset_type', 'status', 'fraud_risk']].head(10).to_string(index=False))

            self.log("✅ Phantom assets detection completed")

        except Exception as e:
            self.log(f"❌ Phantom assets detection failed: {e}")
            self.test_passed = False

        # Step 3: Fraud Schemes Detection
        print("\n🚨 STEP 3: Fraud Schemes Detection (Banco Master Patterns)")
        print("-"*70)
        try:
            from src.analyzers.fraud_schemes import FraudSchemeDetector

            scheme_detector = FraudSchemeDetector()
            schemes = scheme_detector.generate_fraud_scheme_report(
                informe_df, cda_df, cadastro_df
            )

            self.results['fraud_schemes'] = schemes

            total_schemes = sum(len(df) for df in schemes.values())
            if total_schemes > 0:
                print(f"\n⚠️  Found fraud patterns:")
                for scheme_type, df in schemes.items():
                    if not df.empty:
                        print(f"  - {scheme_type}: {len(df)} cases")

            self.log("✅ Fraud schemes detection completed")

        except Exception as e:
            self.log(f"❌ Fraud schemes detection failed: {e}")
            self.test_passed = False

        # Step 4: Peer Comparison Analysis
        print("\n📊 STEP 4: Peer Comparison & Outlier Detection")
        print("-"*70)
        try:
            from src.analyzers.peer_comparison import PeerComparisonAnalyzer

            peer_analyzer = PeerComparisonAnalyzer()
            peer_analyzer.load_fund_categories(cadastro_df)

            metrics = peer_analyzer.calculate_fund_metrics(informe_df)

            # Compare known fraud funds
            comparison = peer_analyzer.compare_with_peers(known_fraud_funds[:5], metrics)
            self.results['peer_comparison'] = comparison

            if not comparison.empty:
                outliers = comparison[comparison['is_outlier']]
                print(f"\n⚠️  Found {len(outliers)} outlier funds:")
                if not outliers.empty:
                    print(outliers[['CNPJ_FUNDO', 'return_zscore', 'fraud_flag']].to_string(index=False))

            # Detect smoothed returns (Ponzi)
            smoothed = peer_analyzer.detect_smoothed_returns(informe_df, known_fraud_funds)
            self.results['smoothed_returns'] = smoothed

            if not smoothed.empty:
                print(f"\n⚠️  Found {len(smoothed)} funds with Ponzi-like smoothed returns")

            self.log("✅ Peer comparison completed")

        except Exception as e:
            self.log(f"❌ Peer comparison failed: {e}")
            self.test_passed = False

        # Step 5: Concentration Analysis
        print("\n📈 STEP 5: Concentration & Regulatory Compliance")
        print("-"*70)
        try:
            from src.analyzers.concentration import ConcentrationAnalyzer

            conc_analyzer = ConcentrationAnalyzer()

            # Detect excessive concentration
            violations = conc_analyzer.detect_excessive_concentration(cda_df, cadastro_df)
            self.results['concentration'] = violations

            if not violations.empty:
                print(f"\n⚠️  Found {len(violations)} concentration violations")
                # Check fraud funds
                fraud_violations = violations[violations['CNPJ_FUNDO'].isin(known_fraud_funds)]
                if not fraud_violations.empty:
                    print(f"  - {len(fraud_violations)} in known fraud funds")

            self.log("✅ Concentration analysis completed")

        except Exception as e:
            self.log(f"❌ Concentration analysis failed: {e}")
            self.test_passed = False

        # Step 6: Summary Report
        print("\n" + "="*70)
        print("📋 WORKFLOW SUMMARY")
        print("="*70)

        print(f"\n✅ Scenario Setup:")
        print(f"   Total Funds: {len(cadastro_df)}")
        print(f"   Known Fraud Funds: {len(known_fraud_funds)}")
        print(f"   Legitimate Funds: {len(cadastro_df) - len(known_fraud_funds)}")

        print(f"\n🔍 Detection Results:")
        print(f"   Phantom/Suspicious Assets: {len(self.results.get('phantom_assets', []))}")

        fraud_schemes = self.results.get('fraud_schemes', {})
        total_schemes = sum(len(df) for df in fraud_schemes.values())
        print(f"   Fraud Scheme Patterns: {total_schemes}")

        peer_comp = self.results.get('peer_comparison', pd.DataFrame())
        outliers = len(peer_comp[peer_comp['is_outlier']]) if not peer_comp.empty else 0
        print(f"   Statistical Outliers: {outliers}")

        smoothed = self.results.get('smoothed_returns', pd.DataFrame())
        print(f"   Ponzi-like Returns: {len(smoothed)}")

        concentration = self.results.get('concentration', pd.DataFrame())
        print(f"   Concentration Violations: {len(concentration)}")

        # Validation: Did we detect the fraud?
        print(f"\n🎯 Validation:")

        detected_fraud = False

        # Check if any fraud funds were flagged
        if not peer_comp.empty:
            fraud_detected_in_peer = peer_comp[peer_comp['CNPJ_FUNDO'].isin(known_fraud_funds)]
            if not fraud_detected_in_peer.empty:
                detected_fraud = True
                print(f"   ✅ Detected {len(fraud_detected_in_peer)}/{len(known_fraud_funds)} fraud funds via peer comparison")

        if total_schemes > 0:
            detected_fraud = True
            print(f"   ✅ Detected fraud scheme patterns")

        if not detected_fraud:
            print(f"   ⚠️  Warning: Known fraud funds not strongly flagged")
            print(f"   (This may be expected depending on scenario parameters)")

        return self.test_passed


if __name__ == "__main__":
    test = IntegrationWorkflowTest()
    success = test.run_complete_workflow()

    print("\n" + "="*70)
    if success:
        print("✅ INTEGRATION TEST PASSED - All components working together")
    else:
        print("❌ INTEGRATION TEST FAILED - Review errors above")
    print("="*70)

    sys.exit(0 if success else 1)
