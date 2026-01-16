import pytest
from config.settings import Config


def test_config_has_cvm_base_url():
    config = Config()
    assert config.CVM_BASE_URL is not None
    assert "cvm.gov.br" in config.CVM_BASE_URL


def test_config_has_data_directory():
    config = Config()
    assert config.DATA_DIR is not None
    assert str(config.DATA_DIR)
