"""A mock ORCID server implementation. It just plays along with signin process."""

from typing import Optional

from fastapi import APIRouter, Form, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from typing_extensions import Final

from ..log import log
from .auth import OrcidBearerToken
from .util import MOCK_ORCID_PREF

routes = APIRouter(prefix=MOCK_ORCID_PREF, tags=["orcid-server-mock"])
"""Routes to be added to application for Mock ORCID authentication (for development)."""

MOCK_TOKEN: Final[OrcidBearerToken] = OrcidBearerToken(
    token_type="bearer",
    scope="/authenticate",
    access_token="my-access-token",
    refresh_token="my-refresh-token",
    expires_in=10000,
    name="Doctor Who",
    orcid="0123-4567-8910-1337",
)


@routes.get(
    "/dummy",
    status_code=status.HTTP_418_IM_A_TEAPOT,
    response_class=PlainTextResponse,
)
async def mock_redir_dummy():
    """Return 418 with text "dummy". Endpoint to test that redirection works correctly."""
    return Response("dummy", status_code=status.HTTP_418_IM_A_TEAPOT)


@routes.get(
    "/authorize",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
async def mock_orcid_authorize(redirect_uri: str, state: Optional[str] = None):
    """Redirect back to given URI with a dummy code added as query parameter."""
    st_param = "" if not state else f"&state={state}"
    code = "123456"
    if state:
        st = state.split(":")
        if st[0] == "code":
            code = st[1]
    redir_url = redirect_uri + f"?code={code}{st_param}"
    log.debug(f"Redirect to {redir_url}")
    return RedirectResponse(url=redir_url)


@routes.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def mock_orcid_revoke():
    """Do nothing."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routes.post("/token", response_model=OrcidBearerToken)
async def mock_orcid_token(code: str = Form(...)) -> OrcidBearerToken:
    """Return dummy token to sign in as a dummy user."""
    if code == "123456":
        return MOCK_TOKEN

    # invalid code -> auth as other user
    tok = OrcidBearerToken.parse_obj(MOCK_TOKEN.dict())
    tok.orcid = "0000-0000-0000-0000"
    return tok


# must come last
@routes.get("/{anything_else:path}")
async def mock_catch_all():
    """Catch-all redirect."""
    return Response(
        "Endpoint not found", status_code=status.HTTP_405_METHOD_NOT_ALLOWED
    )
