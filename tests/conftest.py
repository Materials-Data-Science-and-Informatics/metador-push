"""
Shared fixture for a test environment.
"""

import secrets
from pathlib import Path
from typing import Optional

import pytest

import metador.config as config
import metador.log
from metador import pkg_res
from metador.config import LogLevel, conf
from metador.profile import Profile


def random_hex(length: int) -> str:
    return secrets.token_hex(int(length / 2))


@pytest.fixture(scope="session")
def test_config(tmp_path_factory):
    """Initialize config for test environment."""

    # just sanity-check that this is only loaded once
    undef = False
    try:
        config._conf
    except AttributeError:
        undef = True
    if not undef:
        exit(1)

    config.init_conf()
    conf().orcid.enabled = True
    conf().orcid.use_fake = True

    conf().metador.log.level = LogLevel.DEBUG
    conf().metador.log.file = Path("test_metador.log")
    metador.log.init_logger(conf().metador.log.level.value, conf().metador.log.file)

    conf().metador.profile_dir = pkg_res("profiles")
    conf().metador.data_dir = tmp_path_factory.mktemp("metador_test_datadir")
    yield conf()

    del config._conf


DUMMYFILE_NAMELEN = 8
DUMMYFILE_SIZE = 1024


@pytest.fixture
def dummy_file(tmp_path_factory):
    """A dummy file factory. Creates dummy files and cleans them up in the end."""

    dummy_base = tmp_path_factory.mktemp("dummy_files")
    files = []

    def _dummy_file(name: Optional[str] = None, content: Optional[str] = None):
        if name in files:
            raise RuntimeError(f"Dummy file {name} already exists!")

        filename = name if name else random_hex(DUMMYFILE_NAMELEN)
        while filename in files:
            filename = random_hex(DUMMYFILE_NAMELEN)
        filepath = dummy_base / filename

        if content is None:
            content = random_hex(DUMMYFILE_SIZE)

        with open(filepath, "w") as file:
            file.write(content)
            file.flush()
        return filepath

    yield _dummy_file

    for file in files:
        if file.is_file():
            file.unlink()


@pytest.fixture(scope="session")
def test_profiles(test_config):
    """Initialize config and profiles for test environment."""

    if len(Profile.get_profiles()) != 0:
        # something is wrong. this should only be run once
        # and no profiles were loaded before
        exit(1)

    Profile.load_profiles(test_config.metador.profile_dir)
