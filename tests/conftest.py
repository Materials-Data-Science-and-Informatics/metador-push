"""Shared fixtures and helpers for a test environment."""

import asyncio.subprocess
import os
import secrets
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

import metador.config as config
import metador.log
import metador.server as server
from metador import pkg_res
from metador.config import LogLevel, conf
from metador.orcid import get_auth, init_auth
from metador.orcid.mock import MOCK_TOKEN
from metador.profile import Profile
from metador.upload import TUSD_HOOK_ROUTE

from .testutil import AsyncLiveStream, get_free_tcp_port


class UtilFuncs:
    """Helpers used in tests."""

    @staticmethod
    def random_hex(length: int) -> str:
        """Return hex string of given length."""
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
    return UtilFuncs


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

    # use different port than default for testing
    # to not interfere with possibly running actual dev instance
    conf().uvicorn.port = get_free_tcp_port()
    conf().metador.site = f"http://localhost:{conf().uvicorn.port}"

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
    """Create dummy files and clean them up in the end."""
    dummy_base: Path = tmp_path_factory.mktemp("dummy_files")
    files = []

    def _dummy_file(name: Optional[str] = None, content: Optional[str] = None) -> Path:
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
    Profile.load_profiles(test_config.metador.profile_dir)


@pytest.fixture
async def async_client(test_config):
    """Return an automatically closed async http client."""
    async with AsyncClient(app=server.app, base_url=test_config.metador.site) as ac:
        yield ac


@pytest.fixture
def sync_client():
    """Return a client instance to access the backend."""
    with TestClient(server.app) as client:
        yield client


@pytest.fixture
def auth_cookie(test_config, sync_client):
    """Initialize auth if necessary, fake-auth as a user, return cookie."""
    try:
        get_auth()
    except RuntimeError:
        init_auth(
            test_config.metador.site, test_config.orcid, test_config.metador.data_dir
        )

    cookies = {}
    cookies["session_id"] = get_auth().new_session(MOCK_TOKEN)
    return cookies


@pytest.fixture
async def tus_server(test_config, tmp_path_factory):
    """Launch a tusd instance in the background for running tests."""
    cmd = ["tusd", "-hooks-http", test_config.metador.site + TUSD_HOOK_ROUTE]
    tusd_proc = await asyncio.subprocess.create_subprocess_exec(
        *cmd,
        cwd=tmp_path_factory.mktemp("tusd_test_dir"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert tusd_proc.stdout is not None
    outreader = AsyncLiveStream(tusd_proc.stdout)
    yield outreader

    outreader.t.cancel()  # Cancel stream reader task
    tusd_proc.terminate()  # Shut it down at the end of the pytest session
    await tusd_proc.wait()  # Wait for termination to complete
