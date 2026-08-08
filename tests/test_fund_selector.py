"""Tests for FundSelector and its wiring into the investigation pipeline.

FundSelector shipped with zero callers and zero coverage: the pipeline was still
hardcoded to one investigation. These cover both the selector itself and
run_investigation.resolve_fund_scope, which is what makes --fund-mode work.
"""

import argparse

import pandas as pd
import pytest

from scripts.run_investigation import resolve_fund_scope
from src.utils.fund_selector import (
    FundSelector,
    select_all_funds,
    select_funds_by_administrator,
    select_funds_by_cnpj_list,
    select_funds_by_manager,
)


@pytest.fixture
def cadastro():
    return pd.DataFrame({
        "CNPJ_FUNDO": [
            "12345678000190",
            "98765432000110",
            "11222333000181",
            "44555666000177",
        ],
        "CNPJ_ADMIN": [
            "99999999000101",
            "99999999000101",
            "88888888000102",
            "88888888000102",
        ],
        "DENOM_SOCIAL": [
            "ACME CAPITAL FI MULTIMERCADO",
            "ACME CREDITO FI RENDA FIXA",
            "BOREAL FI ACOES",
            "BOREAL FI CAMBIAL",
        ],
        "ADMIN": [
            "ACME DTVM",
            "ACME DTVM",
            "BOREAL ADMINISTRADORA",
            "BOREAL ADMINISTRADORA",
        ],
        "GESTOR": [
            "ACME GESTORA",
            "OUTRA GESTORA",
            "BOREAL GESTORA",
            "BOREAL GESTORA",
        ],
        "SIT": [
            "EM FUNCIONAMENTO NORMAL",
            "CANCELADA",
            "EM FUNCIONAMENTO NORMAL",
            "EM FUNCIONAMENTO NORMAL",
        ],
    })


class TestSelectByAdministrator:

    def test_matches_partial_name_case_insensitively(self, cadastro):
        result = FundSelector(cadastro).select_by_administrator("acme")
        assert set(result["CNPJ_FUNDO"]) == {"12345678000190", "98765432000110"}

    def test_case_sensitive_matching_can_be_requested(self, cadastro):
        selector = FundSelector(cadastro)
        assert selector.select_by_administrator("acme", case_sensitive=True).empty
        assert len(selector.select_by_administrator("ACME", case_sensitive=True)) == 2

    def test_no_match_returns_empty(self, cadastro):
        assert FundSelector(cadastro).select_by_administrator("NONEXISTENT").empty

    def test_falls_back_to_denom_social_without_admin_column(self, cadastro):
        result = FundSelector(cadastro.drop(columns=["ADMIN"])).select_by_administrator("BOREAL")
        assert len(result) == 2


class TestSelectByAdministratorCnpj:

    def test_selects_funds_under_the_given_admins(self, cadastro):
        result = FundSelector(cadastro).select_by_administrator_cnpj(["88888888000102"])
        assert set(result["CNPJ_FUNDO"]) == {"11222333000181", "44555666000177"}

    def test_accepts_formatted_input(self, cadastro):
        result = FundSelector(cadastro).select_by_administrator_cnpj(["88.888.888/0001-02"])
        assert len(result) == 2

    def test_missing_column_returns_empty(self, cadastro):
        selector = FundSelector(cadastro.drop(columns=["CNPJ_ADMIN"]))
        assert selector.select_by_administrator_cnpj(["88888888000102"]).empty


class TestSelectByManager:

    def test_matches_manager_name(self, cadastro):
        result = FundSelector(cadastro).select_by_manager("BOREAL")
        assert set(result["CNPJ_FUNDO"]) == {"11222333000181", "44555666000177"}

    def test_missing_column_returns_empty(self, cadastro):
        selector = FundSelector(cadastro.drop(columns=["GESTOR"]))
        assert selector.select_by_manager("BOREAL").empty


class TestSelectByCnpjList:

    def test_selects_the_listed_funds(self, cadastro):
        result = FundSelector(cadastro).select_by_cnpj_list(
            ["12345678000190", "11222333000181"]
        )
        assert len(result) == 2

    def test_normalizes_formatted_input(self, cadastro):
        result = FundSelector(cadastro).select_by_cnpj_list(["12.345.678/0001-90"])
        assert len(result) == 1

    def test_unknown_cnpjs_are_warned_about_not_fatal(self, cadastro, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            result = FundSelector(cadastro).select_by_cnpj_list(
                ["12345678000190", "00000000000191"]
            )

        assert len(result) == 1
        assert any("not found" in r.message for r in caplog.records)


class TestSelectAllAndActive:

    def test_select_all_returns_every_fund(self, cadastro):
        assert len(FundSelector(cadastro).select_all()) == 4

    def test_select_all_returns_a_copy(self, cadastro):
        result = FundSelector(cadastro).select_all()
        result.loc[0, "DENOM_SOCIAL"] = "MUTATED"
        assert cadastro.loc[0, "DENOM_SOCIAL"] != "MUTATED"

    def test_active_only_drops_cancelled_funds(self, cadastro):
        selector = FundSelector(cadastro)
        result = selector.select_active_only(selector.select_all())
        assert len(result) == 3
        assert "98765432000110" not in set(result["CNPJ_FUNDO"])

    def test_missing_status_column_keeps_everything(self, cadastro):
        stripped = cadastro.drop(columns=["SIT"])
        selector = FundSelector(stripped)
        assert len(selector.select_active_only(stripped)) == 4


class TestNormalizationOnConstruction:

    def test_cnpjs_are_normalized(self):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["12.345.678/0001-90"],
            "CNPJ_ADMIN": ["99.999.999/0001-01"],
            "DENOM_SOCIAL": ["FUND"],
        })
        selector = FundSelector(cadastro)
        assert selector.cadastro_df["CNPJ_FUNDO"].iloc[0] == "12345678000190"
        assert selector.cadastro_df["CNPJ_ADMIN"].iloc[0] == "99999999000101"

    def test_input_frame_is_not_mutated(self):
        cadastro = pd.DataFrame({
            "CNPJ_FUNDO": ["12.345.678/0001-90"],
            "DENOM_SOCIAL": ["FUND"],
        })
        FundSelector(cadastro)
        assert cadastro["CNPJ_FUNDO"].iloc[0] == "12.345.678/0001-90"

    def test_missing_required_columns_warn_but_do_not_raise(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            FundSelector(pd.DataFrame({"SOMETHING_ELSE": [1]}))

        assert any("Missing required columns" in r.message for r in caplog.records)


class TestSelectionSummary:

    def test_summarizes_the_selection(self, cadastro):
        selector = FundSelector(cadastro)
        summary = selector.get_selection_summary(selector.select_all())

        assert summary["total_funds"] == 4
        assert summary["unique_cnpjs"] == 4
        assert summary["unique_administrators"] == 2
        assert summary["unique_managers"] == 3
        assert summary["active_funds"] == 3


class TestConvenienceFunctions:

    def test_by_administrator_filters_to_active_by_default(self, cadastro):
        result = select_funds_by_administrator(cadastro, "ACME")
        assert set(result["CNPJ_FUNDO"]) == {"12345678000190"}

    def test_by_administrator_can_include_inactive(self, cadastro):
        result = select_funds_by_administrator(cadastro, "ACME", active_only=False)
        assert len(result) == 2

    def test_by_manager(self, cadastro):
        assert len(select_funds_by_manager(cadastro, "BOREAL")) == 2

    def test_by_cnpj_list(self, cadastro):
        result = select_funds_by_cnpj_list(cadastro, ["12345678000190"])
        assert len(result) == 1

    def test_select_all_funds(self, cadastro):
        assert len(select_all_funds(cadastro)) == 4


# ---------------------------------------------------------------------------
# Pipeline wiring
# ---------------------------------------------------------------------------

def _args(**overrides):
    defaults = {
        "fund_mode": None,
        "fund_identifier": None,
        "active_funds_only": False,
        "selected_cnpjs": [],
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestResolveFundScope:

    def test_no_mode_means_no_filter(self, cadastro):
        assert resolve_fund_scope(_args(), cadastro) == []

    def test_mode_all_means_no_filter(self, cadastro):
        assert resolve_fund_scope(_args(fund_mode="all"), cadastro) == []

    def test_administrator_mode_resolves_names_to_cnpjs(self, cadastro):
        scope = resolve_fund_scope(
            _args(fund_mode="administrator", fund_identifier="ACME"), cadastro
        )
        assert set(scope) == {"12345678000190", "98765432000110"}

    def test_manager_mode_resolves_names_to_cnpjs(self, cadastro):
        scope = resolve_fund_scope(
            _args(fund_mode="manager", fund_identifier="BOREAL"), cadastro
        )
        assert set(scope) == {"11222333000181", "44555666000177"}

    def test_active_only_narrows_the_scope(self, cadastro):
        scope = resolve_fund_scope(
            _args(fund_mode="administrator", fund_identifier="ACME", active_funds_only=True),
            cadastro,
        )
        assert scope == ["12345678000190"]

    def test_cnpj_list_mode_parses_comma_separated_values(self, cadastro):
        scope = resolve_fund_scope(
            _args(
                fund_mode="cnpj_list",
                fund_identifier="12.345.678/0001-90, 11222333000181",
            ),
            cadastro,
        )
        assert scope == ["12345678000190", "11222333000181"]

    def test_cnpj_list_mode_does_not_need_a_cadastro(self):
        scope = resolve_fund_scope(
            _args(fund_mode="cnpj_list", fund_identifier="12345678000190"), None
        )
        assert scope == ["12345678000190"]

    def test_explicit_cnpjs_are_unioned_with_the_mode(self, cadastro):
        scope = resolve_fund_scope(
            _args(
                fund_mode="administrator",
                fund_identifier="ACME",
                selected_cnpjs=["11222333000181"],
            ),
            cadastro,
        )
        assert scope[0] == "11222333000181"
        assert set(scope) == {"11222333000181", "12345678000190", "98765432000110"}

    def test_duplicates_are_collapsed(self, cadastro):
        scope = resolve_fund_scope(
            _args(
                fund_mode="administrator",
                fund_identifier="ACME",
                selected_cnpjs=["12345678000190"],
            ),
            cadastro,
        )
        assert len(scope) == len(set(scope)) == 2

    def test_missing_identifier_is_warned_and_ignored(self, cadastro, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            scope = resolve_fund_scope(_args(fund_mode="administrator"), cadastro)

        assert scope == []
        assert any("requires --fund-identifier" in r.message for r in caplog.records)

    def test_missing_cadastro_is_warned_and_ignored(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            scope = resolve_fund_scope(
                _args(fund_mode="administrator", fund_identifier="ACME"), None
            )

        assert scope == []
        assert any("needs a cadastro" in r.message for r in caplog.records)

    def test_no_match_is_warned_and_falls_back_to_explicit(self, cadastro, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            scope = resolve_fund_scope(
                _args(
                    fund_mode="administrator",
                    fund_identifier="NONEXISTENT",
                    selected_cnpjs=["12345678000190"],
                ),
                cadastro,
            )

        assert scope == ["12345678000190"]
        assert any("No funds matched" in r.message for r in caplog.records)


class TestCliSurface:

    def test_flags_are_exposed(self):
        from scripts.run_investigation import build_parser

        args = build_parser().parse_args([
            "--fund-mode", "administrator",
            "--fund-identifier", "ACME DTVM",
            "--active-funds-only",
        ])
        assert args.fund_mode == "administrator"
        assert args.fund_identifier == "ACME DTVM"
        assert args.active_funds_only is True

    def test_fund_mode_rejects_unknown_values(self):
        from scripts.run_investigation import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(["--fund-mode", "nonsense"])

    def test_defaults_apply_no_filter(self):
        from scripts.run_investigation import build_parser

        args = build_parser().parse_args([])
        assert args.fund_mode is None
        assert resolve_fund_scope(args, None) == []
