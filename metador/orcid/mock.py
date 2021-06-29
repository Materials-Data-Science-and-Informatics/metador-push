"""
A mock ORCID server implementation. It just plays along with signin process.
"""

from typing import Final, Optional

from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from .auth import OrcidBearerToken
from .util import MOCK_ORCID_ENDPOINT

routes = APIRouter(prefix=MOCK_ORCID_ENDPOINT, tags=["orcid-server-mock"])
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
    """Endpoint to test that redirection works correctly. Returns 418 with text "dummy"."""

    return Response("dummy", status_code=status.HTTP_418_IM_A_TEAPOT)


@routes.get(
    "/authorize",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
)
async def mock_orcid_authorize(redirect_uri: str, state: Optional[str] = None):
    """Redirects back to given URI with a dummy code added as query parameter."""

    st_param = "" if not state else f"&state={state}"
    return RedirectResponse(url=redirect_uri + f"?code=123456{st_param}")


@routes.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def mock_orcid_revoke():
    """Does nothing."""

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@routes.post("/token", response_model=OrcidBearerToken)
async def mock_orcid_token():
    """Returns dummy token to sign in as a dummy user."""

    return MOCK_TOKEN


# must come last
@routes.get("/{anything_else:path}")
async def mock_catch_all():
    """Catch-all redirect."""

    return Response(
        "Endpoint not found", status_code=status.HTTP_405_METHOD_NOT_ALLOWED
    )
