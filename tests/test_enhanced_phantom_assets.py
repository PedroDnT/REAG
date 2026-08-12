

class TestAssetScanScalesLinearly:
    """The per-asset scan must not re-filter the whole frame for each code.

    The original loop ran `cda_df[cda_df['CD_ATIVO'] == code]` twice for every
    distinct asset. On one real CVM month -- 152k distinct codes over 582k rows
    -- that is roughly 88 billion row comparisons and the run never finished.
    Replaced by a single grouped pass; these pin the semantics that replacement
    has to preserve.
    """

    def _detector(self):
        from src.analyzers.enhanced_phantom_assets import EnhancedPhantomAssetDetector
        return EnhancedPhantomAssetDetector()

    def test_aggregates_across_every_row_of_an_asset(self):
        """total_value sums all holders and num_funds_holding counts them."""
        import pandas as pd

        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["111", "222", "333"],
            "CD_ATIVO": ["FANTASMA_X"] * 3,
            "VL_MERCADO": [100.0, 250.0, 400.0],
            "EMISSOR": ["OFFSHORE SPE LTDA"] * 3,
        })
        detector = self._detector()
        # Force the verdict so this test measures aggregation, not the registry.
        detector.enhanced_validate_asset = lambda code, data: {
            "asset_type": "UNKNOWN", "status": "NOT_FOUND", "fraud_risk": "CRITICAL",
            "confidence": 1.0, "liquidity_expectation": "NONE", "issuer": data.get("EMISSOR"),
            "red_flags": [], "reason": "forced", "validation_method": "test",
        }
        result = detector.detect_enhanced_phantom_assets(cda)
        assert len(result) == 1, "one row per distinct asset code"
        row = result.iloc[0]
        assert row["total_value"] == 750.0
        assert row["num_funds_holding"] == 3

    def test_uses_the_first_row_of_each_asset_for_its_attributes(self):
        """Matches the old `.iloc[0]`, so classification cannot silently shift."""
        import pandas as pd

        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["111", "222"],
            "CD_ATIVO": ["DUP_ASSET", "DUP_ASSET"],
            "VL_MERCADO": [10.0, 20.0],
            "EMISSOR": ["FIRST ISSUER", "SECOND ISSUER"],
        })
        detector = self._detector()
        seen = {}
        original = detector.enhanced_validate_asset

        def spy(code, data):
            seen[code] = data.get("EMISSOR")
            return original(code, data)

        detector.enhanced_validate_asset = spy
        detector.detect_enhanced_phantom_assets(cda)
        assert seen["DUP_ASSET"] == "FIRST ISSUER"

    def test_rows_without_an_asset_code_are_skipped(self):
        import pandas as pd

        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["111", "222"],
            "CD_ATIVO": [pd.NA, "REAL_CODE"],
            "VL_MERCADO": [10.0, 20.0],
        })
        result = self._detector().detect_enhanced_phantom_assets(cda)
        assert "asset_code" not in result.columns or result["asset_code"].notna().all()
