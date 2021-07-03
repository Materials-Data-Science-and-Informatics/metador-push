from uuid import uuid1

import aiotus
import pytest

from metador.dataset import Dataset
from metador.profile import Profile
from metador.server import app

from .testutil import UvicornTestServer, wait_until


@pytest.fixture
async def mock_server(test_config):
    """Start server as test fixture and tear down after test"""

    server = UvicornTestServer(
        app, host=test_config.uvicorn.host, port=test_config.uvicorn.port
    )
    await server.up()
    yield
    await server.down()


@pytest.mark.asyncio
async def test_upload_tus(
    test_config, test_profiles, tus_server, mock_server, dummy_file
):
    file = dummy_file("testupload.txt")
    tusd_url = test_config.metador.tusd_endpoint

    # TODO: if aiotus is fixed to throw errors, also check http status codes

    # try without required fields
    with open(file, "rb") as f:
        hdrs = {"Filename": "some_file"}  # missing dataset
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(uuid1())}  # missing filename
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None

    # try with invalid header
    with open(file, "rb") as f:
        hdrs = {"Dataset": "invalid", "Filename": file.name}  # malformed ds id
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(uuid1()), "Filename": "invalid/filename"}  # bad filename
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None

    # try with invalid dataset id
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(uuid1()), "Filename": file.name}  # non-existing dataset
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None

    Dataset.load_datasets()
    assert len(Dataset.get_datasets()) == 0
    # create ownerless dataset (the upload does not care about owners)
    ds: Dataset = Dataset.create(Profile.get_profile("anything"))
    assert ds.id in Dataset.get_datasets()
    assert ds == Dataset.get_dataset(ds.id)

    lines = await tus_server.readlines_nonblock()  # we don't care about previous stuff

    # upload a file into it
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(ds.id), "Filename": file.name}
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is not None

    lines = await tus_server.readlines_until(lambda x: x.find("post-finish") >= 0, 1)
    assert lines[-1].find("post-finish") >= 0  # sanity-check: last line has the event

    # make sure the hook was completed (file in dataset, checksum is computed)
    success = await wait_until(
        lambda: file.name in ds.files and ds.files[file.name].checksum is not None
    )
    assert success

    # try to upload a file with the same name again
    file.touch()
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(ds.id), "Filename": file.name}
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None  # name conflict, rejected
