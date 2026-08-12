"""Tests for CrossFundIssuerAnalyzer."""

import pandas as pd
import pytest

from src.analyzers.cross_fund_issuer import CrossFundIssuerAnalyzer, _jaro_winkler_similarity


@pytest.fixture
def analyzer():
    return CrossFundIssuerAnalyzer()


class TestCrossFundIssuer:
    def test_missing_cda_columns_raises(self, analyzer):
        cda = pd.DataFrame({"CNPJ_FUNDO": ["123"]})
        cadastro = pd.DataFrame({"CNPJ_FUNDO": ["123"], "CNPJ_ADMIN": ["admin"]})
        with pytest.raises(ValueError, match="missing required columns"):
            analyzer.analyze(cda, cadastro)

    def test_empty_dataframes(self, analyzer):
        cda = pd.DataFrame(columns=["CNPJ_FUNDO", "CD_ATIVO", "VL_MERCADO", "EMISSOR"])
        cadastro = pd.DataFrame(columns=["CNPJ_FUNDO", "CNPJ_ADMIN"])
        result = analyzer.analyze(cda, cadastro)
        assert result.empty

    def test_captive_issuer_detected(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2", "fund3", "fund4"],
            "CD_ATIVO": ["a1", "a2", "a3", "a4"],
            "VL_MERCADO": [100_000, 200_000, 300_000, 400_000],
            "EMISSOR": ["CAPTIVE_CO", "CAPTIVE_CO", "CAPTIVE_CO", "NORMAL_CO"],
        })
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2", "fund3", "fund4"],
            "CNPJ_ADMIN": ["admin1", "admin1", "admin1", "admin2"],
        })
        result = analyzer.analyze(cda, cadastro)
        captive = result[result["signal_type"] == "captive_issuer"]
        assert len(captive) == 1
        assert captive.iloc[0]["EMISSOR"] == "CAPTIVE_CO"
        assert captive.iloc[0]["captive_admin"] == "admin1"

    def test_universe_concentration_detected(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2", "fund3"],
            "CD_ATIVO": ["a1", "a2", "a3"],
            "VL_MERCADO": [500_000, 400_000, 100_000],  # issuer1 = 90% of admin
            "EMISSOR": ["issuer1", "issuer1", "issuer2"],
        })
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2", "fund3"],
            "CNPJ_ADMIN": ["admin1", "admin1", "admin1"],
        })
        result = analyzer.analyze(cda, cadastro)
        concentrated = result[result["signal_type"] == "universe_concentration"]
        assert len(concentrated) >= 1

    def test_name_similarity(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CD_ATIVO": ["a1", "a2"],
            "VL_MERCADO": [100_000, 100_000],
            "EMISSOR": ["EMPRESA ABC LTDA", "EMPRESA ABD LTDA"],
        })
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CNPJ_ADMIN": ["admin1", "admin1"],
        })
        result = analyzer.analyze(cda, cadastro)
        similar = result[result["signal_type"] == "name_similarity_cluster"]
        assert len(similar) >= 1

    def test_name_similarity_reports_how_alike_the_names_are(self, analyzer):
        """The score was computed and discarded, so the brief quoted only nulls.

        Every other column on this signal type is null by construction -- there
        is no exposure or fund count to report for a pair of names -- which left
        38 lines of a real run's briefs reading "total_exposure: nan".
        """
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CD_ATIVO": ["a1", "a2"],
            "VL_MERCADO": [100_000, 100_000],
            "EMISSOR": ["EMPRESA ABC LTDA", "EMPRESA ABD LTDA"],
        })
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CNPJ_ADMIN": ["admin1", "admin1"],
        })
        similar = analyzer.analyze(cda, cadastro).query(
            "signal_type == 'name_similarity_cluster'"
        )
        assert similar["similarity"].notna().all()
        assert (similar["similarity"] < 1.0).all(), "identical names are not a cluster"
        assert (similar["similarity"] >= 0.85).all()

    def test_no_signals_for_diverse_issuers(self, analyzer):
        cda = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CD_ATIVO": ["a1", "a2"],
            "VL_MERCADO": [100_000, 100_000],
            "EMISSOR": ["ISSUER_A", "ISSUER_B"],
        })
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["fund1", "fund2"],
            "CNPJ_ADMIN": ["admin1", "admin2"],
        })
        result = analyzer.analyze(cda, cadastro)
        # No captive issuers (each appears in only 1 fund, below threshold)
        captive = result[result["signal_type"] == "captive_issuer"] if not result.empty else pd.DataFrame()
        assert captive.empty


class TestJaroWinkler:
    def test_identical_strings(self):
        assert _jaro_winkler_similarity("hello", "hello") == 1.0

    def test_empty_string(self):
        assert _jaro_winkler_similarity("", "hello") == 0.0

    def test_similar_strings(self):
        sim = _jaro_winkler_similarity("EMPRESA ABC LTDA", "EMPRESA ABD LTDA")
        assert sim > 0.9

    def test_different_strings(self):
        sim = _jaro_winkler_similarity("ABC", "XYZ")
        assert sim < 0.5
