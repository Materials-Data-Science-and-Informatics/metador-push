"""Shared fixtures and helpers for a test environment."""

import asyncio
import asyncio.subprocess
import os
import secrets
from pathlib import Path
from typing import Optional

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import metador_push.config as config
import metador_push.log
import metador_push.server as server
from metador_push import pkg_res
from metador_push.config import LogLevel, conf
from metador_push.dataset import Dataset
from metador_push.orcid.mock import MOCK_TOKEN
from metador_push.postprocessing import DatasetNotification
from metador_push.profile import Profile
from metador_push.upload import TUSD_HOOK_ROUTE

from .testutil import (
    AsyncLiveStream,
    UvicornTestServer,
    can_connect,
    get_free_tcp_port,
    wait_until,
)


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

    tmpdir = tmp_path_factory.mktemp("metador_push.test_datadir")

    conf().metador_push.log.level = LogLevel.DEBUG
    conf().metador_push.log.file = Path("test_metador_push.log")
    metador_push.log.init_logger(
        conf().metador_push.log.level.value, conf().metador_push.log.file
    )

    conf().metador_push.profile_dir = pkg_res("profiles")
    conf().metador_push.data_dir = tmpdir

    conf().orcid.enabled = True
    conf().orcid.use_fake = True

    # use different port than default for testing
    # to not interfere with possibly running actual dev instance
    conf().uvicorn.port = get_free_tcp_port()
    conf().metador_push.site = f"http://localhost:{conf().uvicorn.port}"

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
    Profile.load_profiles(test_config.metador_push.profile_dir)


@pytest.fixture
def test_datasets(test_profiles):
    """Initialize config and datasets for test environment, clean up datasets afterwards."""
    Dataset.load_datasets()
    yield
    for ds in Dataset.get_datasets():
        Dataset.get_dataset(ds).delete()
    assert len(Dataset.get_datasets()) == 0


@pytest.fixture
async def async_client(test_config):
    """Return an automatically closed async http client."""
    async with AsyncClient(
        app=server.app, base_url=test_config.metador_push.site
    ) as ac:
        yield ac


@pytest.fixture
async def tus_server(test_config, tmp_path_factory):
    """Launch a tusd instance in the background for running tests."""
    cmd = ["tusd", "-hooks-http", test_config.metador_push.site + TUSD_HOOK_ROUTE]

    # create directory where tusd is run and adapt the session test_config
    tusd_cwd = tmp_path_factory.mktemp("tusd_test_dir")
    test_config.metador_push.tusd_datadir = (tusd_cwd / "data").resolve()

    tusd_proc = await asyncio.subprocess.create_subprocess_exec(
        *cmd,
        cwd=tusd_cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert tusd_proc.stdout is not None
    outreader = AsyncLiveStream(tusd_proc.stdout)

    # wait until server is up
    await outreader.readlines_until(lambda x: x.find("now upload files to:") >= 0, 5)

    # without this delay, apparently there is a race condition in CI tests...
    # do 12 retries, 0.25 second delay between, waiting for server to listen
    await wait_until(lambda: can_connect("localhost", 1080), 12, 0.25)

    yield outreader

    outreader.t.cancel()  # Cancel stream reader task
    tusd_proc.terminate()  # Shut it down at the end of the pytest session
    await tusd_proc.wait()  # Wait for termination to complete


@pytest.fixture
async def mock_http_postproc(test_config):
    """Mock postprocessing http hook endpoint that just collects events."""
    q: asyncio.Queue = asyncio.Queue()

    async def notify(notif: DatasetNotification):
        await q.put(notif)

    app = FastAPI()
    app.post("/notify")(notify)

    port = get_free_tcp_port()
    server = UvicornTestServer(app, host=test_config.uvicorn.host, port=port)

    await server.up()
    yield (f"http://localhost:{port}/notify", q)
    await server.down()
