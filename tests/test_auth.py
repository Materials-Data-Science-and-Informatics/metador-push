from urllib import parse

import pytest
from httpx import URL, AsyncClient

from metador.orcid import get_auth, init_auth
from metador.orcid.auth import OrcidBearerToken
from metador.orcid.mock import MOCK_TOKEN
from metador.orcid.util import MOCK_ORCID_ENDPOINT
from metador.server import app


def query_params(url: URL):
    return dict(parse.parse_qsl(parse.urlsplit(str(url)).query))


@pytest.mark.asyncio
async def test_mock_auth(test_config):
    """Test the mock routes imitating the ORCID servers."""

    pref = test_config.metador.site + MOCK_ORCID_ENDPOINT
    async with AsyncClient(app=app, base_url=pref) as ac:

        req = "/authorize?redirect_uri=" + MOCK_ORCID_ENDPOINT + "/dummy"
        res = await ac.get(req)
        assert res.history[0].status_code == 307
        assert res.status_code == 418
        assert res.text == "dummy"
        assert res.url is not None
        assert query_params(res.url)["code"] == "123456"

        req += "&state=something"  # add the optional param
        res = await ac.get(req)
        assert res.url is not None
        assert query_params(res.url)["state"] == "something"

        res = await ac.post("/revoke")
        assert res.status_code == 204

        res = await ac.post("/token")
        tok = OrcidBearerToken.parse_obj(res.json())
        assert tok == MOCK_TOKEN
        assert res.status_code == 200

        # test invalid sub-routes
        res = await ac.post("/invalid")  # no such route
        assert res.status_code == 405

        res = await ac.get("/revoke")  # get not defined, correct is post
        assert res.status_code == 405


@pytest.mark.asyncio
async def test_orcid_flow(test_config):
    """Test the ORCID flow (using the mock server)."""

    conf = test_config

    # no auth configured yet
    with pytest.raises(RuntimeError):
        get_auth()

    # configure auth
    init_auth(conf.metador.site, conf.orcid, conf.metador.data_dir)
