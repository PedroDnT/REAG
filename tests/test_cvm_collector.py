import pytest
from datetime import date
from src.collectors.cvm_collector import CVMCollector


def test_collector_initialization():
    collector = CVMCollector()
    assert collector is not None


def test_informe_diario_url_format():
    collector = CVMCollector()
    url = collector.get_informe_diario_url(year=2024, month=1)
    assert "inf_diario_fi_202401" in url.lower()
    assert url.endswith('.zip')


def test_cda_url_format():
    collector = CVMCollector()
    url = collector.get_cda_url(year=2024, month=1)
    assert "cda_fi_202401" in url.lower()
    assert url.endswith('.zip')
