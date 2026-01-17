"""
Comprehensive Test Suite for Advanced Fraud Detection Analyzers

Tests all modules with synthetic data to ensure:
1. Data format compatibility
2. Module integration
3. Error handling
4. Output validity
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import traceback


class AnalyzerTestSuite:
    """Comprehensive test suite for all fraud detection analyzers"""

    def __init__(self):
        self.test_results = []
        self.errors = []

    def log_test(self, test_name: str, status: str, message: str = ""):
        """Log test result"""
        self.test_results.append({
            'test': test_name,
            'status': status,
            'message': message
        })

        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {test_name}: {status}")
        if message:
            print(f"   {message}")

    def create_sample_cda(self, num_records: int = 100) -> pd.DataFrame:
        """Create sample CDA data with various asset types"""
        np.random.seed(42)

        # Mix of asset types
        stocks = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3'] * 10
        etfs = ['BOVA11', 'SMAL11', 'IVVB11'] * 5
        private_assets = [
            'DEB_PETROBRAS_2025', 'CRI_ABC_2024', 'CRA_AGRO_2026',
            'CDB_BANCO_XYZ', 'DEB_EMPRESA_ME_2024'
        ] * 5
        phantom_stocks = ['FAKE4', 'GHOST3', 'NOPE4'] * 5

        all_assets = stocks + etfs + private_assets + phantom_stocks

        # Create emissor list and truncate to exact length
        emissor_options = ['PETROBRAS', 'VALE', 'ITAU', 'BRADESCO', 'AMBEV',
                          'Construtora ABC Ltda', 'Agro Brasil SA',
                          'Banco XYZ SA', 'Empresa Fast LTDA ME']
        emissor_list = (emissor_options * (num_records // len(emissor_options) + 1))[:num_records]

        data = {
            'CNPJ_FUNDO': [f'12.345.678/0001-{i:02d}' for i in range(num_records)],
            'CD_ATIVO': np.random.choice(all_assets, num_records),
            'VL_MERCADO': np.random.uniform(100000, 50000000, num_records),
            'QT_POS': np.random.uniform(1000, 100000, num_records),
            'DT_COMPTC': [datetime(2024, 1, 31) for _ in range(num_records)],
            'EMISSOR': emissor_list
        }

        df = pd.DataFrame(data)
        return df

    def create_sample_informe(self, num_records: int = 100) -> pd.DataFrame:
        """Create sample Informe Diário data"""
        np.random.seed(42)

        # Create 30 days of data to ensure at least 20 returns after pct_change
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        # Create 18 funds (6 per category × 3 categories) for peer comparison
        funds = [f'12.345.678/0001-{i:02d}' for i in range(18)]

        data = []
        for fund in funds:
            for date in dates:
                data.append({
                    'CNPJ_FUNDO': fund,
                    'DT_COMPTC': date,
                    'VL_QUOTA': 1.0 + np.random.normal(0, 0.01),
                    'VL_PATRIM_LIQ': np.random.uniform(10000000, 100000000),
                    'CAPTC_DIA': np.random.uniform(0, 1000000),
                    'RESG_DIA': np.random.uniform(0, 1000000),
                    'NR_COTST': np.random.randint(10, 1000)
                })

        df = pd.DataFrame(data)
        df['FLUXO_LIQ_DIA'] = df['CAPTC_DIA'] - df['RESG_DIA']
        return df

    def create_sample_cadastro(self, num_records: int = 50) -> pd.DataFrame:
        """Create sample Cadastro data"""
        # Create lists and truncate to exact length
        admin_options = ['99.999.999/0001-01', '88.888.888/0001-01']
        admin_list = (admin_options * (num_records // len(admin_options) + 1))[:num_records]

        classe_options = ['Fundo de Renda Fixa', 'Fundo Multimercado', 'Fundo de Ações']
        classe_list = (classe_options * (num_records // len(classe_options) + 1))[:num_records]

        data = {
            'CNPJ_FUNDO': [f'12.345.678/0001-{i:02d}' for i in range(num_records)],
            'CNPJ_ADMIN': admin_list,
            'CLASSE': classe_list
        }

        df = pd.DataFrame(data)
        return df

    def test_enhanced_phantom_detector(self):
        """Test Enhanced Phantom Assets Detector"""
        print("\n" + "="*70)
        print("🔍 TESTING: Enhanced Phantom Assets Detector")
        print("="*70)

        try:
            from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector

            # Initialize
            detector = EnhancedPhantomAssetDetector()
            detector.update_registries()
            self.log_test("Enhanced Phantom: Import & Init", "PASS")

            # Create sample data
            cda_df = self.create_sample_cda(50)
            self.log_test("Enhanced Phantom: Sample Data Creation", "PASS",
                         f"Created {len(cda_df)} CDA records")

            # Test classification
            test_assets = ['PETR4', 'BOVA11', 'AAPL34', 'DEB_ABC_2025', 'CRI_XYZ_2024']
            for asset in test_assets:
                classification = detector.classify_asset_type(asset)
                assert 'type' in classification
                assert 'should_be_public' in classification
            self.log_test("Enhanced Phantom: Asset Classification", "PASS",
                         f"Classified {len(test_assets)} asset types")

            # Test detection
            results = detector.detect_enhanced_phantom_assets(cda_df)
            assert isinstance(results, pd.DataFrame)
            self.log_test("Enhanced Phantom: Detection Execution", "PASS",
                         f"Detected {len(results)} suspicious assets")

            # Validate output columns
            expected_cols = ['asset_code', 'asset_type', 'status', 'fraud_risk']
            for col in expected_cols:
                assert col in results.columns, f"Missing column: {col}"
            self.log_test("Enhanced Phantom: Output Format", "PASS",
                         "All expected columns present")

        except Exception as e:
            self.log_test("Enhanced Phantom: Overall", "FAIL", str(e))
            self.errors.append(('Enhanced Phantom', traceback.format_exc()))

    def test_fraud_schemes_detector(self):
        """Test Fraud Schemes Detector"""
        print("\n" + "="*70)
        print("🔍 TESTING: Fraud Schemes Detector")
        print("="*70)

        try:
            from src.analyzers.fraud_schemes import FraudSchemeDetector

            # Initialize
            detector = FraudSchemeDetector()
            self.log_test("Fraud Schemes: Import & Init", "PASS")

            # Create sample data
            informe_df = self.create_sample_informe(100)
            cda_df = self.create_sample_cda(100)
            cadastro_df = self.create_sample_cadastro(50)
            self.log_test("Fraud Schemes: Sample Data Creation", "PASS")

            # Test circular flow detection
            circular = detector.detect_circular_flow(informe_df, cda_df, cadastro_df)
            assert isinstance(circular, pd.DataFrame)
            self.log_test("Fraud Schemes: Circular Flow Detection", "PASS",
                         f"Result: {len(circular)} cases")

            # Test layered funds detection
            layered = detector.detect_layered_funds(cda_df, informe_df, cadastro_df)
            assert isinstance(layered, pd.DataFrame)
            self.log_test("Fraud Schemes: Layered Funds Detection", "PASS",
                         f"Result: {len(layered)} cases")

            # Test asset inflation detection
            inflation = detector.detect_asset_inflation(cda_df, informe_df)
            assert isinstance(inflation, pd.DataFrame)
            self.log_test("Fraud Schemes: Asset Inflation Detection", "PASS",
                         f"Result: {len(inflation)} cases")

            # Test shell network detection
            shells = detector.detect_shell_company_network(cda_df, cadastro_df)
            assert isinstance(shells, pd.DataFrame)
            self.log_test("Fraud Schemes: Shell Network Detection", "PASS",
                         f"Result: {len(shells)} cases")

            # Test full report generation
            report = detector.generate_fraud_scheme_report(
                informe_df, cda_df, cadastro_df
            )
            assert 'circular_flow' in report
            assert 'layered_funds' in report
            assert 'asset_inflation' in report
            assert 'shell_networks' in report
            self.log_test("Fraud Schemes: Full Report Generation", "PASS")

        except Exception as e:
            self.log_test("Fraud Schemes: Overall", "FAIL", str(e))
            self.errors.append(('Fraud Schemes', traceback.format_exc()))

    def test_peer_comparison_analyzer(self):
        """Test Peer Comparison Analyzer"""
        print("\n" + "="*70)
        print("🔍 TESTING: Peer Comparison Analyzer")
        print("="*70)

        try:
            from src.analyzers.peer_comparison import PeerComparisonAnalyzer

            # Initialize
            analyzer = PeerComparisonAnalyzer()
            self.log_test("Peer Comparison: Import & Init", "PASS")

            # Create sample data
            cadastro_df = self.create_sample_cadastro(50)
            informe_df = self.create_sample_informe(100)

            # Load categories
            analyzer.load_fund_categories(cadastro_df)
            self.log_test("Peer Comparison: Load Categories", "PASS",
                         f"Loaded {len(analyzer.fund_categories)} fund categories")

            # Calculate metrics
            metrics = analyzer.calculate_fund_metrics(informe_df)
            assert isinstance(metrics, pd.DataFrame)
            assert len(metrics) > 0
            self.log_test("Peer Comparison: Calculate Metrics", "PASS",
                         f"Calculated metrics for {len(metrics)} funds")

            # Compare with peers
            target_funds = informe_df['CNPJ_FUNDO'].unique()[:5].tolist()
            comparison = analyzer.compare_with_peers(target_funds, metrics)
            assert isinstance(comparison, pd.DataFrame)
            self.log_test("Peer Comparison: Peer Comparison", "PASS",
                         f"Compared {len(comparison)} funds")

            # Detect smoothed returns
            smoothed = analyzer.detect_smoothed_returns(informe_df, target_funds)
            assert isinstance(smoothed, pd.DataFrame)
            self.log_test("Peer Comparison: Smoothed Returns Detection", "PASS",
                         f"Result: {len(smoothed)} cases")

        except Exception as e:
            self.log_test("Peer Comparison: Overall", "FAIL", str(e))
            self.errors.append(('Peer Comparison', traceback.format_exc()))

    def test_concentration_analyzer(self):
        """Test Concentration Analyzer"""
        print("\n" + "="*70)
        print("🔍 TESTING: Concentration Analyzer")
        print("="*70)

        try:
            from src.analyzers.concentration import ConcentrationAnalyzer

            # Initialize
            analyzer = ConcentrationAnalyzer()
            self.log_test("Concentration: Import & Init", "PASS")

            # Create sample data
            cda_df = self.create_sample_cda(100)

            # Test HHI calculation
            portfolio = cda_df.head(10)
            hhi = analyzer.calculate_herfindahl_index(portfolio)
            assert isinstance(hhi, float)
            assert 0 <= hhi <= 1
            self.log_test("Concentration: HHI Calculation", "PASS",
                         f"HHI = {hhi:.4f}")

            # Test fund analysis
            fund_cnpj = cda_df['CNPJ_FUNDO'].iloc[0]
            metrics = analyzer.analyze_fund_concentration(cda_df, fund_cnpj)
            assert isinstance(metrics, dict)
            assert 'hhi' in metrics
            assert 'top1_pct' in metrics
            self.log_test("Concentration: Fund Analysis", "PASS")

            # Test excessive concentration detection
            violations = analyzer.detect_excessive_concentration(cda_df)
            assert isinstance(violations, pd.DataFrame)
            self.log_test("Concentration: Excessive Detection", "PASS",
                         f"Result: {len(violations)} violations")

        except Exception as e:
            self.log_test("Concentration: Overall", "FAIL", str(e))
            self.errors.append(('Concentration', traceback.format_exc()))

    def test_market_data_validator(self):
        """Test Market Data Validator"""
        print("\n" + "="*70)
        print("🔍 TESTING: Market Data Validator")
        print("="*70)

        try:
            from src.analyzers.market_data import MarketDataValidator

            # Initialize
            validator = MarketDataValidator()
            self.log_test("Market Data: Import & Init", "PASS")

            # Test cache operations
            cache_file = validator.cache_dir / 'price_cache.csv'
            validator._save_cache()
            self.log_test("Market Data: Cache Operations", "PASS",
                         f"Cache dir: {validator.cache_dir}")

            # Note: Skip actual market data fetching in tests
            # (would require internet + API calls)
            self.log_test("Market Data: API Integration", "SKIP",
                         "Requires internet connection - tested manually")

        except Exception as e:
            self.log_test("Market Data: Overall", "FAIL", str(e))
            self.errors.append(('Market Data', traceback.format_exc()))

    def test_data_format_compatibility(self):
        """Test data format compatibility across modules"""
        print("\n" + "="*70)
        print("🔍 TESTING: Data Format Compatibility")
        print("="*70)

        try:
            # Create datasets
            cda_df = self.create_sample_cda(50)
            informe_df = self.create_sample_informe(50)
            cadastro_df = self.create_sample_cadastro(25)

            # Test column presence
            required_cda_cols = ['CNPJ_FUNDO', 'CD_ATIVO', 'VL_MERCADO', 'QT_POS', 'DT_COMPTC']
            for col in required_cda_cols:
                assert col in cda_df.columns
            self.log_test("Data Format: CDA Columns", "PASS")

            required_informe_cols = ['CNPJ_FUNDO', 'DT_COMPTC', 'VL_QUOTA', 'VL_PATRIM_LIQ']
            for col in required_informe_cols:
                assert col in informe_df.columns
            self.log_test("Data Format: Informe Columns", "PASS")

            required_cadastro_cols = ['CNPJ_FUNDO', 'CNPJ_ADMIN']
            for col in required_cadastro_cols:
                assert col in cadastro_df.columns
            self.log_test("Data Format: Cadastro Columns", "PASS")

            # Test data types
            assert pd.api.types.is_datetime64_any_dtype(cda_df['DT_COMPTC']) or \
                   isinstance(cda_df['DT_COMPTC'].iloc[0], (datetime, pd.Timestamp))
            self.log_test("Data Format: Date Types", "PASS")

            assert pd.api.types.is_numeric_dtype(cda_df['VL_MERCADO'])
            assert pd.api.types.is_numeric_dtype(informe_df['VL_QUOTA'])
            self.log_test("Data Format: Numeric Types", "PASS")

        except Exception as e:
            self.log_test("Data Format: Overall", "FAIL", str(e))
            self.errors.append(('Data Format', traceback.format_exc()))

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("🚀 COMPREHENSIVE ANALYZER TEST SUITE")
        print("="*70)
        print(f"Start time: {datetime.now()}")

        # Run each test suite
        self.test_data_format_compatibility()
        self.test_enhanced_phantom_detector()
        self.test_fraud_schemes_detector()
        self.test_peer_comparison_analyzer()
        self.test_concentration_analyzer()
        self.test_market_data_validator()

        # Summary
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)

        df_results = pd.DataFrame(self.test_results)

        total_tests = len(df_results)
        passed = len(df_results[df_results['status'] == 'PASS'])
        failed = len(df_results[df_results['status'] == 'FAIL'])
        skipped = len(df_results[df_results['status'] == 'SKIP'])

        print(f"\n📈 Results:")
        print(f"   Total Tests:  {total_tests}")
        print(f"   ✅ Passed:     {passed} ({passed/total_tests*100:.1f}%)")
        print(f"   ❌ Failed:     {failed} ({failed/total_tests*100:.1f}%)")
        print(f"   ⏭️  Skipped:    {skipped} ({skipped/total_tests*100:.1f}%)")

        if failed > 0:
            print("\n❌ FAILED TESTS:")
            failed_tests = df_results[df_results['status'] == 'FAIL']
            for _, row in failed_tests.iterrows():
                print(f"   - {row['test']}: {row['message']}")

        if self.errors:
            print("\n🔍 ERROR DETAILS:")
            for module, error in self.errors:
                print(f"\n{'='*70}")
                print(f"Module: {module}")
                print(f"{'='*70}")
                print(error)

        print(f"\nEnd time: {datetime.now()}")
        print("="*70)

        return passed == total_tests - skipped


def main():
    """Run test suite"""
    suite = AnalyzerTestSuite()
    success = suite.run_all_tests()

    if success:
        print("\n✅ ALL TESTS PASSED! System ready for deployment.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Review errors above.")
        return 1


if __name__ == '__main__':
    exit(main())
