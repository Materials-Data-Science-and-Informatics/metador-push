import aiotus
import pytest

from metador.server import app

from .util import UvicornTestServer


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
async def test_upload_tus(test_config, tus_server, mock_server, tmp_path):
    filename = tmp_path / "testupload.txt"
    with open(filename, "w") as file:
        file.write("this is a test")
        file.flush()

    tusd_url = test_config.metador.tusd_endpoint

    # try without headers
    with pytest.raises(AssertionError) as e:
        with open(filename, "rb") as file:
            location = await aiotus.upload(tusd_url, file, headers={})
            assert location is not None
        assert str(e).find("Wrong status code 400") < 0

    # try with invalid header
    with pytest.raises(AssertionError) as e:
        with open(filename, "rb") as file:
            location = await aiotus.upload(
                tusd_url, file, headers={"Dataset": "invalid"}
            )
            assert location is not None
        assert str(e).find("Wrong status code 422") < 0

    # TODO valid upload to a dataset
