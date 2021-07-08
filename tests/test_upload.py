"""Test uploads via tus protocol."""

from uuid import uuid1

import aiohttp
import aiotus
import pytest
from aiotus.common import ProtocolError

from metador.dataset import Dataset
from metador.profile import Profile
from metador.server import app

from .testutil import UvicornTestServer, wait_until


@pytest.fixture
async def mock_server(test_config):
    """Start server as test fixture and tear down after test."""
    server = UvicornTestServer(
        app, host=test_config.uvicorn.host, port=test_config.uvicorn.port
    )
    await server.up()
    yield
    await server.down()


async def aiotus_upload(filename, url, headers):
    """Upload using aiotus, but this function raises exceptions on failure."""
    with open(filename, "rb") as fd:
        async with aiohttp.ClientSession() as session:
            location = await aiotus.creation.create(
                session, url, file=fd, metadata={}, headers=headers
            )
            await aiotus.core.upload_buffer(session, location, fd, headers=headers)


def aiotus_error_http_status_is(e, code: int) -> bool:
    """
    Check status code returned from the tusd server.

    In case of errors, it must be the one passed from our backend.

    Input: ExceptionInfo and a status code.
    Output: Whether the exception contains the code.
    """
    return str(e.value).find(f"Wrong status code {code}") >= 0


async def assert_failed_upload(file, url, hdrs, status_code):
    """Try to upload. Expect it to fail with specific HTTP status code."""
    with pytest.raises(ProtocolError) as e:
        await aiotus_upload(file, url, hdrs)
    assert aiotus_error_http_status_is(e, status_code)


@pytest.mark.asyncio
async def test_upload_tus(
    test_config, test_datasets, tus_server, mock_server, dummy_file
):
    """Try uploading files with valid and invalid metadata."""
    file = dummy_file("testupload.txt")
    tusd_url = test_config.metador.tusd_endpoint

    # try without required fields
    hdrs = {"Filename": "some_file"}  # missing dataset
    await assert_failed_upload(file, tusd_url, hdrs, 400)

    hdrs = {"Dataset": str(uuid1())}  # missing filename
    await assert_failed_upload(file, tusd_url, hdrs, 400)

    # try with invalid header
    hdrs = {"Dataset": "invalid", "Filename": file.name}  # malformed ds id
    await assert_failed_upload(file, tusd_url, hdrs, 422)

    hdrs = {"Dataset": str(uuid1()), "Filename": "invalid/filename"}  # bad filename
    await assert_failed_upload(file, tusd_url, hdrs, 422)

    # try with invalid dataset id
    hdrs = {"Dataset": str(uuid1()), "Filename": file.name}  # non-existing dataset
    await assert_failed_upload(file, tusd_url, hdrs, 404)

    # create ownerless dataset (the upload does not care about owners)
    ds: Dataset = Dataset.create(Profile.get_profile("anything"))
    assert ds.id in Dataset.get_datasets()
    assert ds == Dataset.get_dataset(ds.id)

    lines = await tus_server.readlines_nonblock()  # we don't care about previous stuff

    # upload a file into it

    hdrs = {"Dataset": str(ds.id), "Filename": file.name}
    await aiotus_upload(file, tusd_url, hdrs)

    lines = await tus_server.readlines_until(lambda x: x.find("post-finish") >= 0, 1)
    assert lines[-1].find("post-finish") >= 0  # sanity-check: last line has the event

    # make sure the hook was completed (file in dataset, checksum is computed)
    assert await wait_until(
        lambda: file.name in ds.files and ds.files[file.name].checksum is not None
    )

    # try to upload a file with the same name again
    file.touch()
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(ds.id), "Filename": file.name}
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None  # name conflict, rejected

    # try uploading file that is not allowed (matches "false" schema)
    # in "example" profile only *.[txt|jpg|mp4] is allowed
    badfile = dummy_file("testupload.bmp")
    ds2: Dataset = Dataset.create(Profile.get_profile("example"))
    hdrs = {"Dataset": str(ds2.id), "Filename": badfile.name}
    await assert_failed_upload(file, tusd_url, hdrs, 422)
