"""
Shared fixtures and helpers for a test environment.
"""

import os
import secrets
from pathlib import Path
from typing import Optional

import pytest

import metador.config as config
import metador.log
from metador import pkg_res
from metador.config import LogLevel, conf
from metador.orcid.mock import MOCK_TOKEN
from metador.profile import Profile


class Util:
    """Helpers used in tests."""

    @staticmethod
    def random_hex(length: int) -> str:
        return secrets.token_hex(int(length / 2))

    @staticmethod
    def reset_conf() -> None:
        """Unload config (useful for testing)."""

        global _conf

        if config.CONFFILE_ENVVAR in os.environ:
            del os.environ[config.CONFFILE_ENVVAR]

        try:
            del config._conf
        except NameError:
            pass


@pytest.fixture(scope="session")
def testutils():
    """Fixture giving access to helper functions anywhere in test suite."""
    return Util


@pytest.fixture(scope="session")
def test_config(testutils, tmp_path_factory):
    """Initialize config for test environment."""

    config.init_conf()

    tmpdir = tmp_path_factory.mktemp("metador_test_datadir")

    conf().metador.log.level = LogLevel.DEBUG
    conf().metador.log.file = Path("test_metador.log")
    metador.log.init_logger(conf().metador.log.level.value, conf().metador.log.file)

    conf().metador.profile_dir = pkg_res("profiles")
    conf().metador.data_dir = tmpdir

    conf().orcid.enabled = True
    conf().orcid.use_fake = True

    allowlistfile = tmpdir / "allowlist.txt"
    with open(allowlistfile, "w") as file:
        file.write(MOCK_TOKEN.orcid + "\n")
        file.flush()
    conf().orcid.allowlist_file = allowlistfile

    yield conf()

    testutils.reset_conf()


DUMMYFILE_NAMELEN = 8
DUMMYFILE_SIZE = 1024


@pytest.fixture(scope="session")
def dummy_file(testutils, tmp_path_factory):
    """A dummy file factory. Creates dummy files and cleans them up in the end."""

    dummy_base = tmp_path_factory.mktemp("dummy_files")
    files = []

    def _dummy_file(name: Optional[str] = None, content: Optional[str] = None):
        if name in files:
            raise RuntimeError(f"Dummy file {name} already exists!")

        filename = name if name else testutils.random_hex(DUMMYFILE_NAMELEN)
        while filename in files:
            filename = testutils.random_hex(DUMMYFILE_NAMELEN)
        filepath = dummy_base / filename

        content = content if content else testutils.random_hex(DUMMYFILE_SIZE)

        with open(filepath, "w") as file:
            assert content is not None
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
