import asyncio
from uuid import uuid1

import aiotus
import pytest

from metador.dataset import Dataset
from metador.profile import Profile
from metador.server import app

from .testutil import UvicornTestServer


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

    # TODO: if aiotus is fixed to throw, also check http status codes

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

    # upload a file into it
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(ds.id), "Filename": file.name}
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is not None
        await asyncio.sleep(0.2)  # otherwise post_finish hook is not sent yet
        # TODO: more elegant: check live tusd stdout to see the event was triggered
        # this is complicated and probably not worth it right now.

    # now file is in dataset
    assert file.name in ds.files
    # and the checksum should also be computed by now
    assert ds.files[file.name].checksum is not None

    # try to upload a file with the same name again
    file.touch()
    with open(file, "rb") as f:
        hdrs = {"Dataset": str(ds.id), "Filename": file.name}
        location = await aiotus.upload(tusd_url, f, headers=hdrs)
        assert location is None  # name conflict, rejected
