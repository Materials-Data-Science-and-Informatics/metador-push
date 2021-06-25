"""
Shared fixture for a test environment.
"""

import pytest

import metador.config as config
from metador import pkg_res
from metador.config import conf


@pytest.fixture(scope="session")
def test_config(tmp_path_factory):
    """Initialize config for test environment"""

    config.init_conf(pkg_res("tests/test_conf.toml"))
    conf().metador.profile_dir = pkg_res("profiles")
    conf().metador.data_dir = tmp_path_factory.mktemp("metador_test_rundir")
