"""Tests for the ORCID authentication."""

from datetime import datetime, timedelta
from urllib import parse

import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import URL, AsyncClient

import metador_push.orcid
import metador_push.orcid.mock
from metador_push.orcid import get_auth, get_session, init_auth
from metador_push.orcid.api import AuthStatus
from metador_push.orcid.auth import OrcidBearerToken, SessionID
from metador_push.orcid.mock import MOCK_TOKEN
from metador_push.orcid.util import (
    AUTH_PREF,
    MOCK_ORCID_PREF,
    ORCID_ENDPOINT,
    orcid_server_pref,
)
from metador_push.server import app

from .testutil import UvicornTestServer


@pytest.fixture
async def mock_orcid_server(test_config):
    """Start server as test fixture and tear down after test."""
    app = FastAPI()
    app.include_router(metador_push.orcid.mock.routes)
    server = UvicornTestServer(
        app, host=test_config.uvicorn.host, port=test_config.uvicorn.port
    )
    await server.up()
    yield
    await server.down()


# dummy orcids
SOME_ORCID = MOCK_TOKEN.orcid  # this one is on the allowlist
OTHER_ORCID = "0123-4567-8910-1338"  # this one is NOT on the allowlist


def query_params(url: URL):
    """Return query params from URL as dict."""
    return dict(parse.parse_qsl(parse.urlsplit(str(url)).query))


def test_orcid_server_pref(test_config):
    """Test the helper function returning the ORCID server to use."""
    site = test_config.metador_push.site
    assert orcid_server_pref(True, site) == site + MOCK_ORCID_PREF
    assert orcid_server_pref(False, site) == site + MOCK_ORCID_PREF
    assert orcid_server_pref(True) == "https://sandbox.orcid.org/oauth"
    assert orcid_server_pref(False) == "https://orcid.org/oauth"


@pytest.mark.asyncio
async def test_mock_auth(test_config):
    """Test the mock routes imitating the ORCID servers."""
    pref = test_config.metador_push.site + MOCK_ORCID_PREF
    async with AsyncClient(app=app, base_url=pref) as ac:

        req = "/authorize?redirect_uri=" + MOCK_ORCID_PREF + "/dummy"
        res = await ac.get(req)
        assert res.history[0].status_code == 307
        assert res.status_code == 418
        assert res.text == "dummy"
        assert res.url is not None
        assert query_params(res.url)["code"] == "123456"

        res = await ac.get(req + "&state=something")
        assert res.url is not None
        assert query_params(res.url)["state"] == "something"

        res = await ac.get(req + "&state=code:forbid")
        assert res.url is not None
        assert query_params(res.url)["code"] == "forbid"

        res = await ac.post("/revoke")
        assert res.status_code == 204

        res = await ac.post("/token", data={"code": "123456"})
        tok = OrcidBearerToken.parse_obj(res.json())
        assert tok == MOCK_TOKEN
        assert res.status_code == 200

        res = await ac.post("/token", data={"code": "forbid"})
        tok = OrcidBearerToken.parse_obj(res.json())
        assert tok.orcid == "0000-0000-0000-0000"

        # test invalid sub-routes
        res = await ac.post("/invalid")  # no such route
        assert res.status_code == 405

        res = await ac.get("/revoke")  # get not defined, correct is post
        assert res.status_code == 405


@pytest.mark.asyncio
async def test_orcid_flow(test_config, tmp_path, mock_orcid_server):
    """Test the ORCID flow (using the mock server)."""
    # no auth configured yet -> exception
    metador_push.orcid._auth = None
    with pytest.raises(RuntimeError):
        get_auth()

    allowlist = test_config.orcid.allowlist_file

    # create invalid file (contains not proper orcid)
    bad_allowlistfile = tmp_path / "invalid.txt"
    with open(bad_allowlistfile, "w") as file:
        file.write("invalid\n")
        file.flush()

    # test with invalid allowlist -> should crash
    test_config.orcid.allowlist_file = bad_allowlistfile
    with pytest.raises(SystemExit):
        init_auth(test_config.metador_push.site, test_config.orcid)

    # restore good allowlist
    test_config.orcid.allowlist_file = allowlist

    # configure auth with serialization
    conf = test_config
    init_auth(conf.metador_push.site, conf.orcid, conf.metador_push.data_dir)
    assert get_auth().allow_list == [MOCK_TOKEN.orcid]

    pref = test_config.metador_push.site + AUTH_PREF
    async with AsyncClient(app=app, base_url=pref) as ac:
        # try invalid route
        res = await ac.get("invalid/route")
        assert res.status_code == 405

        # before login - no session
        res = await ac.get("/status")
        status = AuthStatus.parse_obj(res.json())
        assert status.orcid_enabled
        assert status.session is None

        # try login with a not whitelisted ORCID
        params = {"state": "code:forbid"}  # query params
        res = await ac.get(ORCID_ENDPOINT, params=params)
        assert res.status_code == 403

        # try with a whitelisted ORCID (from the default MOCK_TOKEN)
        target_redir = MOCK_ORCID_PREF + "/dummy"
        params = {"state": target_redir}
        res = await ac.get(ORCID_ENDPOINT, params=params)
        # the cookie has been set before redirecting
        assert res.history[-1].cookies["session_id"]
        # we arrive where we expect to (the route passed to state)
        assert parse.urlparse(str(res.url)).path == target_redir
        assert res.status_code == 418  # I am a teapot

        # the session creation must have been successful.
        # now serialize + re-init (test persistence)
        get_auth().dump_sessions()
        init_auth(conf.metador_push.site, conf.orcid, conf.metador_push.data_dir)

        # get session status (session should still be there)
        cookies = {"session_id": res.history[-1].cookies["session_id"]}
        res = await ac.get("/status", cookies=cookies)

        # check that we are authenticated as the dummy user
        status = AuthStatus.parse_obj(res.json())
        assert status.orcid_enabled
        assert status.session.orcid == MOCK_TOKEN.orcid

        # signout should redirect back to homepage
        res = await ac.get("/signout", cookies=cookies)
        assert res.history[0].status_code == 307
        assert res.url == conf.metador_push.site + "/"

        ########
        # restore the session again from file (it was not updated)
        init_auth(conf.metador_push.site, conf.orcid, conf.metador_push.data_dir)

        # try with invalid sessionid
        res = await ac.get("/status", cookies={"session_id": "invalid"})
        assert AuthStatus.parse_obj(res.json()).session is None

        # make it expired -> should not work anymore
        expiry = datetime.today() - timedelta(seconds=1)
        get_auth().sessions[cookies["session_id"]].expires = expiry
        res = await ac.get("/status", cookies=cookies)
        assert AuthStatus.parse_obj(res.json()).session is None

        ########
        # restore the session again from file again
        init_auth(conf.metador_push.site, conf.orcid, conf.metador_push.data_dir)

        # try getting the current session info, first with auth disabled
        get_auth().orcid_conf.enabled = False

        assert get_session(cookies["session_id"]) is None
        assert get_session(SessionID("invalid")) is None
        assert get_session(None) is None
        assert get_session() is None

        # re-enable auth to test whether exceptions work (-> return None unacceptable)
        get_auth().orcid_conf.enabled = True

        # try with invalid session
        with pytest.raises(HTTPException):
            get_session(SessionID("invalid"))
        with pytest.raises(HTTPException):
            get_session(None)

        # now try to look the real session up
        assert get_session(cookies["session_id"]).orcid == MOCK_TOKEN.orcid

        # make allowlist empty (to invalidate the session)
        alll = get_auth().allow_list
        get_auth().allow_list = []

        # the user session now became invalid
        with pytest.raises(HTTPException):
            get_session(cookies["session_id"])

        get_auth().allow_list = alll  # restore allow list
